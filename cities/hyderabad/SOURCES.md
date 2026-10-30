# Raw data: where each file in `raw/` came from

Everything in `raw/` is fetched in GitHub Actions (`.github/workflows/fetch-hyderabad.yml` runs `fetch_osm.py`, `fetch.py`
and, by hand, `fetch_reps.py`), because the sandbox these maps are built in can't reach the source servers.
Fetched on 2026-10-30 unless noted.

This map shows Hyderabad's **revenue** boundaries only: districts and mandals. The civic ones (the GHMC, Cyberabad and
Malkajgiri municipal corporations and their 300 wards, redrawn in December 2025 and February 2026) are published only as
images and a written notification; see `scouting/hyderabad/FINDINGS.md`. The 2027 census freezes districts, mandals
and villages from January 1, 2026 to March 31, 2027.

| File | Source |
|---|---|
| `admin.geojson` | OpenStreetMap (ODbL), from Geofabrik's daily southern India extract cut to the four districts with osmium (`fetch_osm.py`; the Overpass servers timed out on these queries): administrative boundaries at levels 5 (districts) and 6 (mandals) around Hyderabad. Telangana's are imported from the Government of Telangana's district and mandal shapefiles (GODL, 2023). Simplified to about 10 m in the fetch |
| `lakes.geojson` | OpenStreetMap: `natural=water` and `landuse=reservoir` polygons of 0.15 km² or more (rivers, canals and ponds left out); the build cuts those of 0.4 km² or more out of the land |
| `roads.geojson` | OpenStreetMap: motorway and trunk roads across the region (the Outer Ring Road, the PVNR Expressway, the national highways) and named primary and secondary roads around the ring road |
| `osm_rail.json` | OpenStreetMap: Hyderabad Metro route relations and the MMTS train routes, their stops, and railway stations |
| `osm_places.json` | OpenStreetMap: place nodes (city, town, suburb, quarter, neighbourhood, locality, village, hamlet) across the four districts. Used to place the known-as names and, beyond the city, for search |
| `osm_landmarks.json` | OpenStreetMap: positions for the curated landmarks in `names.py` |
| `pincodes.geojson` | OpenCity, "India Pincode Maps - 2025" (Department of Posts delivery areas, public domain): the Hyderabad and Secunderabad file, and the all-India file for the rest of the region. Where both have a PIN, the city file wins |
| `assembly.geojson`, `loksabha.geojson` | DataMeet (CC BY 4.0): assembly and simplified Lok Sabha constituencies (2008 delimitation). **Not drawn**: tested against well-known places they put 6 of 16 in the wrong assembly seat (Charminar in Goshamahal) |
| `oc_ac_telangana.geojson`, `oc_ac_hyd_rr.geojson`, `oc_pc_telangana.geojson`, `oc_ghmc_wards_2022.geojson` | OpenCity copies of the 2018 assembly and 2019 Lok Sabha constituency maps and GHMC's 2022 map of the old 150 wards. **Not drawn**: the 2018 map got 13 of 16 places right but splits 59 of the 155 old wards between seats (each ward lies wholly in one) |
| `reps/` | Wikipedia pages (wikitext) the hand-kept `representatives.json` was checked against: the Telangana Legislative Assembly's members, the 2023 assembly results (with its by-elections section: Secunderabad Cantonment, May 2024; Jubilee Hills, November 2025), the 2024 Lok Sabha results in Telangana and the 18th Lok Sabha members |

Hand-kept in this folder: `names.py` (districts, known-as names, landmarks, lake labels, district labels beyond) and
`representatives.json` (all 119 MLAs and 17 MPs, the party each was elected for, a link to each member's Wikipedia page;
Khairatabad vacant since its member's disqualification in September 2026). It isn't on the map yet (no accurate
constituency lines); keep it current after any by-election so it's ready.
