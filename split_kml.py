"""Split the Lands and Surveys boundary file into one KML per unit.

Reads source/Administrative_Boundaries_All_August2024.zip and writes
kml/<layer>/<NAME>.kml for districts, the post-2024 municipalities and
community clusters, the municipalities and communities, and the parishes.
Every folder gets a manifest.csv. A file of 1 MB or more also gets a copy
simplified to fit under 1 MB, for services that cap uploads there.
Run with `python3 split_kml.py`; the script deletes and rewrites kml/.
"""

from __future__ import annotations

import csv
import html
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from simplify import simplify

KML_NS = "http://www.opengis.net/kml/2.2"
NS = {"k": KML_NS}
HERE = Path(__file__).parent
SOURCE_ZIP = HERE / "source" / "Administrative_Boundaries_All_August2024.zip"
OUT = HERE / "kml"

SIZE_LIMIT_BYTES = 1_000_000
# Degrees. The first tolerance is about 10 cm at Cyprus latitudes; each step
# raises it by half until the file fits, so the copy stays as close to the
# original as the limit allows.
FIRST_TOLERANCE = 0.000001
TOLERANCE_STEP = 1.5

# Community clusters are lettered Α to Θ in Greek, the same letters in every
# district.
CLUSTER_LETTERS = {
    "Α": "A",
    "Β": "B",
    "Γ": "G",
    "Δ": "D",
    "Ε": "E",
    "ΣΤ": "ST",
    "Ζ": "Z",
    "Η": "H",
    "Θ": "TH",
}


@dataclass
class Unit:
    """One placemark to write out, with the attributes it carries."""

    placemark: ET.Element
    name: str
    stem: str
    attributes: dict[str, str] = field(default_factory=dict)


def file_stem(*, name: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


def kml_tag(*, name: str) -> str:
    return f"{{{KML_NS}}}{name}"


def centroid(*, placemark: ET.Element) -> tuple[float, float, int]:
    xs: list[float] = []
    ys: list[float] = []
    for coords in placemark.findall(".//k:coordinates", NS):
        for token in coords.text.split():
            x, y = token.split(",")[:2]
            xs.append(float(x))
            ys.append(float(y))
    return sum(xs) / len(xs), sum(ys) / len(ys), len(xs)


def description_fields(*, placemark: ET.Element) -> dict[str, str]:
    """Read the attribute table ArcGIS puts in a placemark description."""
    description = placemark.findtext("k:description", namespaces=NS) or ""
    cells = [
        html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()
        for cell in re.findall(r"<td>(.*?)</td>", description, re.S)
    ]
    # The first cell is a title row; the rest alternate name, value.
    return dict(zip(cells[1::2], cells[2::2]))


def folder_named(*, root: ET.Element, name: str) -> ET.Element:
    for folder in root.iter(kml_tag(name="Folder")):
        if folder.findtext("k:name", namespaces=NS) == name:
            return folder
    raise KeyError(name)


def write_kml(
    *, placemark: ET.Element, style: ET.Element, name: str, path: Path
) -> None:
    placemark.find("k:name", NS).text = name
    kml = ET.Element(kml_tag(name="kml"))
    doc = ET.SubElement(kml, kml_tag(name="Document"))
    ET.SubElement(doc, kml_tag(name="name")).text = name
    doc.append(style)
    doc.append(placemark)
    ET.indent(kml, space="\t")
    ET.ElementTree(kml).write(path, encoding="UTF-8", xml_declaration=True)


def simplified_copy(*, placemark: ET.Element, tolerance: float) -> ET.Element:
    copy = ET.fromstring(ET.tostring(placemark))
    for ring in copy.findall(".//k:LinearRing", NS):
        coords = ring.find("k:coordinates", NS)
        points = [tuple(map(float, t.split(",")[:2])) for t in coords.text.split()]
        kept = simplify(points=points, tolerance=tolerance)
        coords.text = " ".join(f"{x},{y},0" for x, y in kept)
    return copy


def write_under_limit(*, unit: Unit, style: ET.Element, path: Path) -> float:
    """Write a simplified copy under the size limit; return the tolerance used."""
    tolerance = FIRST_TOLERANCE
    while True:
        copy = simplified_copy(placemark=unit.placemark, tolerance=tolerance)
        write_kml(
            placemark=copy, style=style, name=f"{unit.name} (simplified)", path=path
        )
        if path.stat().st_size < SIZE_LIMIT_BYTES:
            return tolerance
        tolerance *= TOLERANCE_STEP


def write_layer(*, units: list[Unit], style: ET.Element, out_dir: Path) -> None:
    out_dir.mkdir(parents=True)
    stems = [unit.stem for unit in units]
    duplicates = {stem for stem in stems if stems.count(stem) > 1}
    if duplicates:
        raise ValueError(f"filename collision in {out_dir.name}: {sorted(duplicates)}")

    rows: list[dict[str, str | int | float]] = []
    for unit in units:
        path = out_dir / f"{unit.stem}.kml"
        write_kml(placemark=unit.placemark, style=style, name=unit.name, path=path)
        lon, lat, vertices = centroid(placemark=unit.placemark)
        row = {
            "file": path.name,
            "name": unit.name,
            **unit.attributes,
            "polygons": len(unit.placemark.findall(".//k:Polygon", NS)),
            "vertices": vertices,
            "centroid_lon": round(lon, 4),
            "centroid_lat": round(lat, 4),
            "bytes": path.stat().st_size,
            "simplified_tolerance_deg": "",
        }
        rows.append(row)
        if path.stat().st_size >= SIZE_LIMIT_BYTES:
            simplified_path = out_dir / f"{unit.stem}_simplified.kml"
            tolerance = write_under_limit(unit=unit, style=style, path=simplified_path)
            simplified = ET.parse(simplified_path).getroot().find(".//k:Placemark", NS)
            _, _, simplified_vertices = centroid(placemark=simplified)
            rows.append(
                {
                    **row,
                    "file": simplified_path.name,
                    "name": f"{unit.name} (simplified)",
                    "vertices": simplified_vertices,
                    "bytes": simplified_path.stat().st_size,
                    "simplified_tolerance_deg": tolerance,
                }
            )
            print(
                f"  {path.name} is {path.stat().st_size} bytes; wrote {simplified_path.name} at tolerance {tolerance}"
            )

    rows.sort(key=lambda row: row["file"])
    with (out_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} files to {out_dir.relative_to(HERE)}")


def read_units(
    *, root: ET.Element, folder: str
) -> list[tuple[ET.Element, dict[str, str]]]:
    placemarks = folder_named(root=root, name=folder).findall("k:Placemark", NS)
    return [(pm, description_fields(placemark=pm)) for pm in placemarks]


def main() -> None:
    ET.register_namespace("", KML_NS)
    if OUT.exists():
        shutil.rmtree(OUT)

    with zipfile.ZipFile(SOURCE_ZIP) as outer:
        kmz_name = next(n for n in outer.namelist() if n.endswith(".kmz"))
        with zipfile.ZipFile(outer.open(kmz_name)) as kmz, kmz.open("doc.kml") as doc:
            root = ET.parse(doc).getroot()
    styles = {s.get("id"): s for s in root.findall("k:Document/k:Style", NS)}

    def style_of(*, placemark: ET.Element) -> ET.Element:
        return styles[placemark.findtext("k:styleUrl", namespaces=NS).lstrip("#")]

    districts = read_units(root=root, folder="ΕΠΑΡΧΙΕΣ")
    district_english = {
        attrs["DIST_NM_G"]: attrs["DIST_NM_E"] for _, attrs in districts
    }
    district_by_code = {
        attrs["DIST_CODE"]: attrs["DIST_NM_E"] for _, attrs in districts
    }
    units = [
        Unit(
            placemark=pm,
            name=attrs["DIST_NM_E"],
            stem=file_stem(name=attrs["DIST_NM_E"]),
            attributes=attrs,
        )
        for pm, attrs in districts
    ]
    write_layer(
        units=units,
        style=style_of(placemark=districts[0][0]),
        out_dir=OUT / "districts",
    )

    # The same cluster letter is reused in every district, so the district
    # goes into the name.
    clusters = read_units(root=root, folder="ΔΗΜΟΙ_ΣΥΜΠΛΕΓΜΑΤΑ")
    units = []
    for pm, attrs in clusters:
        district = district_english[attrs["DISTRICT_N"]]
        match = re.fullmatch(r'Community Cluster "(\w+)"', attrs["NAME_ENG"])
        if match:
            name = f"{district} Community Cluster {CLUSTER_LETTERS[match.group(1)]}"
        else:
            name = attrs["NAME_ENG"]
        units.append(
            Unit(placemark=pm, name=name, stem=file_stem(name=name), attributes=attrs)
        )
    write_layer(
        units=units,
        style=style_of(placemark=clusters[0][0]),
        out_dir=OUT / "municipalities-2024",
    )

    # One English name is shared by two villages; add the district to both.
    communities = read_units(root=root, folder="ΔΗΜΟΙ_ΚΟΙΝΟΤΗΤΕΣ")
    name_counts: dict[str, int] = defaultdict(int)
    for _, attrs in communities:
        name_counts[attrs["VIL_NM_E"]] += 1
    units = []
    town_names: dict[str, str] = {}
    for pm, attrs in communities:
        name = attrs["VIL_NM_E"]
        if name_counts[name] > 1:
            name = f"{name} ({district_by_code[attrs['DIST_CODE']]})"
        town_names[attrs["VIL_CCD"]] = name
        units.append(
            Unit(placemark=pm, name=name, stem=file_stem(name=name), attributes=attrs)
        )
    write_layer(
        units=units,
        style=style_of(placemark=communities[0][0]),
        out_dir=OUT / "municipalities-communities",
    )

    parishes = read_units(root=root, folder="ΕΝΟΡΙΕΣ")
    units = []
    for pm, attrs in parishes:
        name = f"{town_names[attrs['VIL_CCD']]} {attrs['QRTR_NM_E']}"
        units.append(
            Unit(placemark=pm, name=name, stem=file_stem(name=name), attributes=attrs)
        )
    write_layer(
        units=units, style=style_of(placemark=parishes[0][0]), out_dir=OUT / "parishes"
    )


if __name__ == "__main__":
    main()
