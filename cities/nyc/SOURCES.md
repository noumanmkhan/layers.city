# New York City: sources and quirks

Everything is fetched in GitHub Actions (`.github/workflows/fetch-nyc.yml`, by hand or when a
`cities/nyc/fetch*.py` changes on main): the sandbox can't reach these hosts. Dataset ids were checked by
`scouting/nyc/scout.py` on October 18, 2026 (report in `scouting/nyc/out/`; notes in the project's nyc-data-scouting.md).

| Script | Writes (raw/) | Source |
|---|---|---|
| `fetch.py` | `boroughs`, `community_districts`, `ntas`, `council`, `assembly`, `senate`, `congress`, `school_districts` `.geojson` | NYC Open Data, Department of City Planning (quarterly): gthc-hcne, 5crt-au7u, 9nt8-h7nd, 872g-cjhh, 5yfv-9hkp, h4i2-acfi, j3u5-usz2, 8ugf-3d8u. All clipped to the shoreline. `community_districts` has 71 shapes: the 59 districts plus 12 joint interest areas (boro_cd 164, 226–228, 355–356, 480–484, 595) |
| | `historic_districts.geojson` | Landmarks Preservation Commission, Historic Districts (skyk-mpzq, quarterly). Kept: `current_` Yes and designated; extensions are joined to their district |
| | `bids.geojson` | Small Business Services, Business Improvement Districts (ejxk-d93y) |
| | `states`, `counties`, `cousubs` `.geojson` | Census Bureau 2024 cartographic boundaries (500k): states, counties, and county subdivisions of New York, New Jersey and Connecticut in the regional box. Connecticut's county-equivalents are its planning regions since 2022 |
| | `mta_rail.json` | MTA GTFS (rrgtfsfeeds.s3.amazonaws.com): `gtfs_subway.zip` (with the Staten Island Railway), `gtfslirr.zip`, `gtfsmnr.zip`. Free to use; MTA names, bullets and map styling need a licence, so the map draws its own lines |
| | `osm_*.json` | OpenStreetMap via Overpass (ODbL): place names and main streets in the city, highways across the region, NJ Transit, PATH and AirTrain route relations and stations, landmark positions |
| `fetch_acs.py` | `acs_tracts.json`, `tracts.json` | ACS 5-year table-based summary files (B25003, B08301, B25075, B25063, B25036, B25032, C16001, B01001, B05005) for the five counties' tracts; TIGERweb tract internal points |
| `engine/fetch_venue_events.py nyc`, `engine/fetch_venue_drives.py nyc` (refresh-venues.yml) | `venue_events.json`, `venue_tm_ids.json`, `venue_drives.json` | Ticketmaster Discovery API, venue by venue, for the Venues pages (`venues.json`: the curated list, origins, fares); OSRM for best-case drives from each origin. Venue facts and arrival notes were written from each venue's own pages on October 19, 2026; fares from the TLC taxi-fare page and mta.info |
| `fetch_marathon.py` (daily in fetch-closures.yml) | `closures/marathon_<year>.{txt,json}` | NYC Citywide Event Coordination and Management, the marathon's street closure and no-parking notice (a PDF at nyc.gov, usually posted in the last week of October). Its "Street Closed" rows are placed on NYC DOT's street centerline (inkn-q76z) and added to the special events by `fetch_closures.py`; `marathon.json` holds the race date and notice URLs, and a past year (`test`) to check the parser |
| `engine/fetch_skyscrapers.py` | `skyscrapers/wiki.json` | English Wikipedia, "List of tallest buildings in New York City" (CC BY-SA 4.0); cut at 650 ft (198 m), Wikipedia's own threshold |

## Quirks
- Community districts have numbers, not names: `names.py` gives each the neighborhood pair people use; joint interest areas are named after the 2020 NTA covering most of them and carry no figures.
- The subway is drawn by trunk line (the MTA's colour groups: A C E, B D F M, 1 2 3...), merging every service's main shapes; stations list services.
- NJ Transit and PATH come from OpenStreetMap: NJ Transit's GTFS needs a developer account and agreement (on the commercial re-check list).
- Towers under construction without Wikipedia coordinates (2 WTC, 70 Hudson Yards, 80 Flatbush...) are left out until placed by hand (`skyscrapers.json` coords).
- The marathon notice names streets loosely ("120th Street" for Manhattan's E and W 120 ST, "McGuiness"); `fetch_marathon.py` resolves them to centerline names. Central Park's drives and traverses, expressway ramps and a few Staten Island streets stay unplaced. NYRR publishes no course GPX, so no course line is drawn.
