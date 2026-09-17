"""Build map/index.html, a Leaflet page showing every split KML.

Reads kml/<layer>/ and writes the boundaries into the page as GeoJSON,
simplified to about 5 m so the page stays near 8 MB. Simplified copies of
oversize files are skipped; the page shows the originals.
Run `python3 split_kml.py` first, then `python3 build_map.py`.
"""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from simplify import Point, simplify

KML_NS = "http://www.opengis.net/kml/2.2"
NS = {"k": KML_NS}
HERE = Path(__file__).parent
KML = HERE / "kml"
MAP_DIR = HERE / "map"
TEMPLATE = MAP_DIR / "template.html"
OUTPUT = MAP_DIR / "index.html"

# Degrees; about 5 m at Cyprus latitudes, below what the page can show.
TOLERANCE = 0.00005
DECIMALS = 5

LAYERS = [
    ("districts", "Districts", "DIST_CODE"),
    (
        "municipalities-2024",
        "Municipalities and community clusters (from 1/7/2024)",
        "NAME_GR",
    ),
    (
        "municipalities-communities",
        "Municipalities and communities (until 30/6/2024)",
        "VIL_CCD",
    ),
    ("parishes", "Parishes", "QRTR_CCD"),
]


def ring_points(*, ring: ET.Element) -> list[Point]:
    tokens = ring.findtext("k:coordinates", namespaces=NS).split()
    return [(float(t.split(",")[0]), float(t.split(",")[1])) for t in tokens]


def placemark_geometry(*, placemark: ET.Element) -> dict:
    polygons = []
    for polygon in placemark.findall(".//k:Polygon", NS):
        rings = []
        for ring in polygon.findall(".//k:LinearRing", NS):
            points = simplify(points=ring_points(ring=ring), tolerance=TOLERANCE)
            if len(points) >= 4:
                rings.append(
                    [[round(x, DECIMALS), round(y, DECIMALS)] for x, y in points]
                )
        if rings:
            polygons.append(rings)
    return {"type": "MultiPolygon", "coordinates": polygons}


def layer_features(*, folder: Path, key: str) -> list[dict]:
    with (folder / "manifest.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    features = []
    for row in rows:
        if row["simplified_tolerance_deg"]:
            continue
        root = ET.parse(folder / row["file"]).getroot()
        placemark = root.find(".//k:Placemark", NS)
        properties = {
            k: v for k, v in row.items() if k not in ("centroid_lon", "centroid_lat")
        }
        properties["id"] = row[key]
        features.append(
            {
                "type": "Feature",
                "properties": properties,
                "geometry": placemark_geometry(placemark=placemark),
            }
        )
    return features


def main() -> None:
    layers = []
    for folder_name, label, key in LAYERS:
        features = layer_features(folder=KML / folder_name, key=key)
        vertices = sum(
            len(ring)
            for f in features
            for polygon in f["geometry"]["coordinates"]
            for ring in polygon
        )
        print(
            f"{folder_name}: {len(features)} features, {vertices} vertices after simplifying"
        )
        layers.append(
            {
                "id": folder_name,
                "label": label,
                "features": {"type": "FeatureCollection", "features": features},
            }
        )

    page = TEMPLATE.read_text(encoding="utf-8")
    page = page.replace(
        "/*DATA*/", json.dumps(layers, ensure_ascii=False, separators=(",", ":"))
    )
    OUTPUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(HERE)}, {OUTPUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
