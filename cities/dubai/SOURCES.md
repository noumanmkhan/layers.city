# Raw data: where each file in `raw/` came from

Fetched from the user's Mac on 2026-11-17 (see `scouting/dubai/FINDINGS.md`). Data Dubai and makani.ae answer only
UAE addresses, so GitHub Actions can't refresh them: those files are refreshed by hand from a UAE connection. The big
downloads (`raw/osm/`, `raw/datadubai/`, `raw/gtfs2026/`, `raw/pulse/`, `raw/probe/`) are gitignored.

| File | Source |
|---|---|
| `osm/gcc-states-latest.osm.pbf` (gitignored) | Geofabrik's GCC extract of OpenStreetMap (ODbL), data to 2026-11-16. `extract_osm.py` cuts everything below from it with osmium |
| `admin.geojson` | OpenStreetMap: the emirates (admin level 4) and the community and area polygons at levels 8–10. Dubai's communities are level 10 (and a few at 8: Business Bay, DIFC, Jumeirah Park…); Sharjah's and Ajman's areas are level 8 |
| `land.geojson` | OpenStreetMap's coastline closed against the frame (54.85–55.80 E, 24.70–25.55 N); the Creek and the lagoons are water |
| `roads.geojson` | OpenStreetMap: motorway, trunk, primary, secondary and tertiary roads and links. Highways are picked by `ref` (E11, E311, E611, E44, E66, E77, D68…) |
| `rail.geojson` | OpenStreetMap: rail, metro, tram and construction ways (the Blue Line, `construction=subway`) and stations |
| `places.json` | OpenStreetMap place nodes: to place the known-as names and, beyond the city, for search |
| `pois.geojson` | OpenStreetMap: hospitals, schools, campuses, libraries, places of worship, parks, beaches, sports, heritage, museums, malls, tall buildings, chargers (areas as a point with `_km2`; parks and beaches keep their outline) |
| `ajman/districts-area.geojson` | Ajman Open Data (data.ajman.ae, CC BY 4.0): Ajman's 79 districts, used as the areas of Ajman in the regional view |
| `ajman/*` (the rest) | Ajman Open Data (CC BY 4.0): bus lines and stops, marine stations, parks, the emirate's outline. Kept for later layers |
| `datadubai/` (gitignored) | Data Dubai (data.dubai, Dubai Open Data Licence): DM communities and sectors (**not used** until Dubai Municipality approves their use on a website, a GeoDubai request), parks and beaches X/Y, heritage visitor counts |
| `gtfs2026/` (gitignored) | Data Dubai dataset 464468: RTA's GTFS (Ops_GTFS_11-Sep-2026, valid to 2026-12-31): Metro, tram, buses, marine |

Hand-kept in this folder: `names.py` (the city's outline, the three sides and their rough lines, highway names, known-as
names, landmarks, labels beyond the region).

The city: Dubai's urban area from Jebel Ali to the Sharjah border, inland to just past Emirates Road (Dubai South,
Expo City and Dubailand in; the inland desert and Hatta out). Its communities are OpenStreetMap's, which leave gaps
(Dubai Marina, JLT, Al Barsha, Al Quoz, the Palm, Jebel Ali): the side fill covers the gaps and the known-as names name
them. Swap in DM's 224 communities once approved.
