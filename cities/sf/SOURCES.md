# San Francisco: sources and quirks

Everything is fetched in GitHub Actions (`.github/workflows/fetch-sf.yml`, by hand or when a `cities/sf/fetch*.py`
changes on main): the sandbox can't reach these hosts. Dataset ids were checked by `scouting/sf/scout.py` on
October 30, 2026 (report in `scouting/sf/out/`; notes in the project's sf-bay-data-scouting.md).

| Script | Writes (raw/) | Source |
|---|---|---|
| `fetch.py` | `analysis_neighborhoods`, `sffind`, `supervisors`, `historic_districts`, `cultural_districts` `.geojson` | DataSF (PDDL / CC0 / public domain): Analysis Neighborhoods p5b7-5n3h (41), SF Find Neighborhoods pty2-tcw4 (117), Supervisor Districts (2022) f2zs-jevy, Historic Districts 63x5-g3m4 (Planning; `a10`/`a11` = "Listed" for Article 10 landmark districts and Article 11 conservation districts), Cultural Districts 5xmc-5bjj. The map-type datasets answer only DataSF's v3 export (`/api/v3/views/<id>/query.geojson`) |
| | `an_tracts.json`, `tracts_2020.geojson` | Fallback for the 41 if the export fails: DataSF's 2020 tract crosswalk (sevw-6tgi) and the Census Bureau's 2024 cartographic tract boundaries |
| | `cities`, `bay_counties` `.geojson` | MTC/ABAG open data (ArcGIS `region_incorporatedplace_clp`, `region_county_clp`): the 101 incorporated cities and the 9 counties, clipped to the shoreline |
| | `states`, `counties`, `senate`, `assembly` `.geojson` | Census Bureau 2024 cartographic boundaries (500k): land beyond the region; California State Senate and Assembly districts (2021 Citizens Redistricting Commission lines) |
| | `congress.geojson` | California Department of Technology GIS: "AB 604 – California Congressional Districts 2027–2032 as enacted by Proposition 50" (used for the November 3, 2026 election; sitting members keep the 2021 lines until January 3, 2027). Fallback: the Statewide Database's AB604 zip |
| | `gtfs_rail.json` | GTFS, no key: BART (bart.gov), Caltrain (Trillium), Muni (`muni-gtfs.apps.sfmta.com/data/muni_gtfs-current.zip`: rail, streetcar and cable car routes only). Agency names, bullets and map styling aren't used: the map draws its own lines |
| | `osm_*.json` | OpenStreetMap via Overpass (ODbL): place names, highways across the region, SMART, ACE, Capitol Corridor and VTA light rail route relations and stations, landmark positions |
| `fetch_streets.py` | `osm_streets.json` | OpenStreetMap trunk, primary, secondary and tertiary roads in the city (tertiary kept only when on `names.py` MAJOR_STREETS) |
| `fetch_acs.py` | `acs_tracts.json`, `tracts.json` | ACS 5-year table-based summary files (the New York tables) for San Francisco's tracts; TIGERweb tract internal points |
| `fetch_representatives.py` | `representatives/ca.csv`, `house.xml`, `us_house_2021.geojson` | Open States' California legislators; the House Clerk's member list; Census 2024 cartographic congressional districts (the 2021 lines). Supervisors and the mayor are hand-kept in `representatives.py` |
| `fetch_closures.py` | `closures/events.json` | SFMTA Temporary Street Closures (DataSF 8x25-yybr): Special Event permits only, with their lines (fetch-closures.yml, daily) |
| `engine/fetch_changes.py` | `changes/pipeline.json` | Planning's Development Pipeline (DataSF 6jgi-cpb4, CC0, quarterly) via `changes.json` (fetch-changes.yml, weekly); no planner, sponsor or contact fields |
| `engine/fetch_skyscrapers.py`, `engine/fetch_heritage_buildings.py` | `skyscrapers/`, `heritage_buildings.json` | Wikipedia's tallest-buildings list (CC BY-SA); Planning's Article 10 landmarks (DataSF 97yj-54sx) |

## Quirks
- The Farallon Islands are part of the City and County but left off the map (`build.py` cuts the city to the mainland, Treasure Island and Yerba Buena Island).
- Golden Gate Park, McLaren Park and Lincoln Park are among the 41 Analysis Neighborhoods; they're park units with no Living here figures, so the lens ranks 38.
- "Parts of the city" (Downtown, Northside, West Side, Central, Southeast) is a hand grouping of the 41 (`names.py` SIDES), not an official division.
- BART's Grey Line (the Oakland Airport connector) is drawn in beige with an "OAK" badge; the E Embarcadero streetcar is in Muni's GTFS only when it's running.
- The 524 slivers of city land outside the 41 (MTC's shoreline vs the tracts') join the nearest part of the city.
