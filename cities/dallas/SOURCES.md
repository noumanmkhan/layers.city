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
| `fetch_more.py` | `representatives/tx.csv`, `house.xml`, `us_house_2021.geojson` | Open States (Texas legislators), Clerk of the House member list, Texas Legislative Council PLANC2193 (the lines today's members were elected on); weekly by `fetch-dallas-representatives.yml` |
| | `city/*.geojson`, `city/historical_markers.json` | City of Dallas ArcGIS Online (services2.arcgis.com/rwnOSbfKSwyTBcwN): Libraries, Recreation_Centers, Dallas_Parks_Source_File, Community_Pool_2023, Indoor_Pool_2023, Spray_Ground_2023, Dog_Parks, Hospitals, Dallas_Landmark_Historic_Districts, NEW_DAY_OF_SERVICE_ and CRMHostedLayers (days of service, brush routes), City_of_Dallas_School_Districts_2022, Dallas_Bike_Facilities_view, Dallas_Bike_Plan_2025, Dallas_Trails_Source_File, Public_Improvement_Districts; Dallas Open Data adn6-n59j (historical markers). Several services don't number their layer 0: the fetch reads the service and takes its layer |
| | `disd/trustees_2021.geojson` | Dallas ISD trustee single-member districts, adopted December 16, 2021 (services.arcgis.com/RfrtTbYxQ8YIhjWT) |
| | `institutions/` | IPEDS HD2024 (Texas), CMS Hospital General Information (Dallas, Collin, Denton counties, geocoded by the Census Bureau), OSM universities, colleges and hospitals |
| | `osm_landmarks.json`, `osm_playgrounds.json`, `osm_tennis.json` | OpenStreetMap via Overpass |
| `fetch_transit_downtown.py` | `transit_downtown.json` | DART GTFS and a Geofabrik Texas extract cut to the city, routed with r5py: weekday 8–9 am trips to Akard, St. Paul, West End or EBJ Union Station from a 400 m grid in each ZIP |
| `engine/fetch_*.py dallas` | `skyscrapers/`, `canopy/`, `surface/`, `drive_times.json`, `bikes.geojson` | Wikipedia's "List of tallest buildings in Dallas"; ESA WorldCover 2021; DART GTFS buses; OSRM drive times from `drive_points.json`; the City's bike facilities (completed) |

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
- Public improvement districts: the City's layer dates some districts' expiry to 2020; PIDs are renewed on the same
  lines, so the boundaries are kept, without the "Premium" extra-assessment zones.
- The landmark historic districts layer is a KML import: each district appears three times and Junius Heights in
  zones A to F; `build.py` merges them by name (21 districts).
- Sanitation: days of service give the weekday (garbage and recycling weekly); brush routes give the week of the
  month for brush and bulky trash. The City publishes no holiday changes as data, so the card's dates are worked
  out from the weekday.
- School districts: the City's 2022 layer (Census lines) covers every ISD reaching into Dallas; slivers under
  0.3 km² along the city line are dropped.
- DART's GTFS fare tables carry monthly-pass transfer times R5 rejects; the transit fetch leaves the fare files out.
- DART stop names come in capitals with direction codes ("ABRAMS @ LA VISTA - S - FS"); `surface.json`'s
  `stopNames` tidies them.
- Members of Congress sit for the 2021 lines (PLANC2193) until January 3, 2027; the map draws the 2025 lines
  (PLANC2333) the November 2026 election uses, and the card looks members up in `us_house_2021.geojson`.
- What isn't here, and why: `cities/dallas/PARKED.md`.
- Overpass often times out; `fetch_lib.overpass` retries across three servers.
