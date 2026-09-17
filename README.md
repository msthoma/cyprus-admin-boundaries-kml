# Cyprus administrative boundaries as KML

One KML file for each district, municipality, community and parish of Cyprus, covering the whole island, taken from the official administrative map of the Department of Lands and Surveys.

Browse them on a map: https://msthoma.github.io/cyprus-admin-boundaries-kml/

## Source

Dataset 187 on the National Open Data Portal of Cyprus: https://data.gov.cy/en/dataset/187, "Διοικητικά Όρια Δήμων και Κοινοτήτων - Διοικητικός Χάρτης", published by the Department of Lands and Surveys under the Creative Commons Attribution 4.0 licence, last modified 29 August 2024.

The file used is the resource "Διοικητικά Όρια - Όλα (Άπο 1/7/2024) (kmz)", kept as downloaded in `source/Administrative_Boundaries_All_August2024.zip` (13.6 MB, SHA-256 `95be307ab425539da6d0a747b52e727f95ea4a8c596a83959d9c61599c1aaae8`). It is a zip holding one KMZ, `ΔΙΟΙΚΗΤΙΚΑ_ΟΡΙΑ_ΟΛΑ_ΑΥΓΟΥΣΤΟΣ2024.kmz`, whose `doc.kml` has four polygon layers and a label point for each polygon.

## The files

- `kml/districts/` 6 files, the districts (επαρχίες): Lefkosia, Keryneia, Ammochostos, Larnaka, Lemesos, Pafos.
- `kml/municipalities-2024/` 50 files, the municipalities and community clusters (δήμοι και συμπλέγματα κοινοτήτων) in force since the local government reform of 1 July 2024.
- `kml/municipalities-communities/` 615 files, the municipalities and communities (δήμοι και κοινότητες) as they stood until 30 June 2024, over the whole island.
- `kml/parishes/` 159 files, the parishes (ενορίες) of the towns.

Each file holds one unit as a KML placemark with one or more polygons. The placemark's description keeps the attribute table from the source: district code (1 Lefkosia, 2 Keryneia, 3 Ammochostos, 4 Larnaka, 5 Lemesos, 6 Pafos), village code, `VIL_CCD` (district and village code joined, unique across the island) and the English and Greek names; parishes also carry their parish code and names. Each folder has a `manifest.csv` listing every file with its name, the attributes, polygon count, vertex count, centroid and size in bytes.

## File names

The file name is the unit's English name from the source in capitals, with every run of other characters replaced by one underscore: `KIOS(ISTINTZIO)` becomes `KIOS_ISTINTZIO.kml`. The name inside the file keeps its punctuation.

- Two villages are called AGIA VARVARA, so they are `AGIA_VARVARA_PAFOS.kml` and `AGIA_VARVARA_LEFKOSIA.kml`.
- Community clusters are lettered Α to Θ in Greek and the same letters recur in every district, so they are named by district and letter, `LEFKOSIA_COMMUNITY_CLUSTER_A.kml`, with Γ written G, ΣΤ written ST and Θ written TH. The new municipalities keep their name, for example `DIMOS_LEMESOU.kml`.
- Parishes are named by town and parish: `DIMOS_KERYNEIAS_AGIA_PARASKEVI.kml`.

## The Ammochostos district

`kml/districts/AMMOCHOSTOS.kml` is 1.21 MB, larger than the 1 MB that some services accept for an upload. Next to it is `AMMOCHOSTOS_simplified.kml` at 0.97 MB, made by dropping vertices that lie within 3.4 millionths of a degree (about 35 cm) of the line between their neighbours. It is marked "(simplified)" in its name and in `manifest.csv`, where the `simplified_tolerance_deg` column gives the tolerance; the original is unchanged. Every other file is under 1 MB.

## Regenerating

`python3 split_kml.py` reads the zip in `source/` and rewrites `kml/`, making a simplified copy of any file of 1 MB or more with `simplify.py`. `python3 build_map.py` reads `kml/` and writes `map/index.html`, the map page, with the outlines simplified to about 5 m for display; open it in a browser. Both need Python 3.12 and nothing else.

The map page is published with GitHub Pages: on every push to `master`, the workflow in `.github/workflows/pages.yml` runs `build_map.py` and deploys `map/`, so a rerun of `split_kml.py` that is committed and pushed updates the site.

## Licence

The data is CC BY 4.0 from the Department of Lands and Surveys; the scripts are MIT. See `LICENSE`.
