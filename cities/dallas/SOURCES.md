# Dallas: sources and quirks

Everything is fetched in GitHub Actions (`.github/workflows/fetch-dallas.yml`, by hand or when a
`cities/dallas/fetch*.py` changes on main): the sandbox can't reach these hosts.

| Script | Writes (raw/) | Source |
|---|---|---|
| `fetch.py` | `places.geojson`, `counties.geojson`, `states.geojson` | Census Bureau 2024 cartographic boundaries (500k), clipped to the frame |
| | `lakes.geojson` | Census TIGERweb Hydro, water areas over 0.4 km² |
| | `tx_house`, `tx_senate`, `us_house` `.geojson` | Texas Legislative Council, Capitol Data Portal: PLANH2316, PLANS2168, PLANC2333 (the plan's own `.zip`, not the `_All_Files` package) |
| | `dallas_council.geojson`, `fortworth_council.geojson` | egis.dallascityhall.com Basemap/CouncilAreas; mapit.fortworthtexas.gov CIVIC/OpenData_Boundaries/2 |
| | `osm_*.json` | OpenStreetMap via Overpass: place names, streets in Dallas, highways and rail across the region |
| `fetch_zips.py` | `zctas.geojson`, `acs_zcta.json` | Census 2020 ZCTAs; ACS 2020–2024 table-based summary file, ZCTA rows |
| `fetch_rail.py` | `dart_rail.json` | DART GTFS (light rail, Silver Line, TRE) |
| `fetch_voting.py` | `voting/centers.json`, `voting/*` | see below; also run daily by `fetch-dallas-voting.yml` |

## Voting (November 3, 2026)
- Dallas County: the public **Vote Center Finder** layer (services3.arcgis.com, `Vote_Center_Finder_view`, layer 4),
  active sites only: 444 election day vote centers and 84 early voting sites, the same as its PDF lists. Only
  codes, names, voting rooms, addresses and positions are kept. (The county's other, internal logistics layers
  are not used.)
- Tarrant County: the election day list `1126_Vote_Center_Locations.pdf` (223 sites, "as of September 2") and the
  early voting list `1126_EV_Sched.pdf` (47), read by column position (`voting_sources.py`), placed with the Census
  batch geocoder, then Nominatim for what it can't match (one site unplaced on October 15). Positions are reused
  on later runs.
- Collin County: `api.collincountytx.gov/Elections2APIProxy/elections/public`, the data behind its polling-locations
  map (90 election day, 42 early voting, with positions).
- Denton County: precincts on election day. Its `Polling_Locations_-_Election_3_` layer (each election day site
  with the precincts it serves, and early voting sites) and `Voter_Precincts`.
- Rockwall, Ellis, Johnson, Kaufman and Parker counties: not yet (no box shows there).

## Quirks
- The City of Dallas's Census place includes Lake Ray Hubbard and its other city lakes; those are water on the map.
  Highland Park, University Park and Cockrell Hill are their own towns inside Dallas.
- Dallas has no official neighbourhoods; units are ZCTAs clipped to the city. A ZCTA mostly outside Dallas
  (75019 Coppell, 75051/75052 Grand Prairie, 75134 Lancaster, 75205 Highland Park, 75234 Farmers Branch) has no
  figures: the ACS describes the whole ZIP.
- Nearly every Dallas ZIP drives to work (73–99%), so there is no getting-to-work lens.
- Overpass often times out; `fetch_lib.overpass` retries across three servers.
