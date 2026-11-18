# Melbourne: data sources

Fetched in GitHub Actions (`.github/workflows/fetch-melbourne.yml`): pushing a changed `cities/melbourne/fetch*.py`
to main runs it and commits what it writes under `raw/`. The sandbox can't reach these hosts. Scouting notes are in
the project's claude/australia-scouting.md.

| What | Source | Licence | Script |
|---|---|---|---|
| Suburbs and localities (the City's units; every other suburb in Greater Melbourne) | Australian Bureau of Statistics, ASGS Edition 3 (2021), Suburbs and Localities, via its map service (geo.abs.gov.au, ASGS2021/SAL) | CC BY 4.0 | `fetch.py` |
| Councils (LGAs), Greater Melbourne (GCCSA), Victoria (the land) | ABS ASGS Edition 3 (2021): LGA, GCCSA, STE | CC BY 4.0 | `fetch.py` |
| SA1s in the City | ABS ASGS Edition 3 (2021), SA1 | CC BY 4.0 | `fetch.py` |
| 2021 Census figures by SA1 | ABS 2021 Census General Community Profile DataPack, SA1, Victoria (short headers) | CC BY 4.0 | `fetch.py` |
| Metro trains, trams, V/Line trains | Transport Victoria Open Data Portal, GTFS Schedule (weekly; folders 1 V/Line, 2 metro trains, 3 trams) | CC BY 4.0 | `fetch.py` |
| Victorian Legislative Assembly districts (2021 redivision; the 2022 and 2026 elections) | Vicmap Admin State Assembly 2022, via the Vicmap open data WFS (opendata.maps.vic.gov.au, `open-data-platform:state_assembly_2022`) | CC BY 4.0 | `fetch_representatives.py` |
| Federal electoral divisions (2024 redistribution) | Australian Electoral Commission, GIS data (Vic-october-2024-esri.zip) | CC BY 4.0 | `fetch_representatives.py` |
| Federal members | Parliamentary Handbook API (handbookapi.aph.gov.au, current members), checked against the AEC's 2025 members elected | aph.gov.au; AEC (CC BY 4.0) | `fetch_representatives.py` |
| Lord Mayor, Deputy Lord Mayor, councillors | Hand-kept from the VEC's Melbourne City Council page and 2024 results (`council.json`) | Public information | — |
| Parks: outlines; Sports & rec; water play | OpenStreetMap via Overpass (`fetch_parks.py`) | ODbL | `parks.py` |
| Parks: playgrounds, public toilets, public barbecues | City of Melbourne open data (data.melbourne.vic.gov.au: playgrounds, public-toilets, public-barbecues) | CC BY 4.0 | `parks.py` |
| Skyscrapers | Wikipedia, "List of tallest buildings in Melbourne" (engine/fetch_skyscrapers.py) | CC BY-SA 4.0 | engine/skyscrapers.py |
| ERs (Greater Melbourne), universities and TAFE, libraries and community centres, places of worship, bike lanes | OpenStreetMap via Overpass (`fetch_more.py`) | ODbL | `places_more.py` |
| Schools | Department of Education, School Locations 2026 (DataVic) | CC BY 4.0 | `places_more.py` |
| New development | City of Melbourne, Development Activity Monitor | CC BY 4.0 | `places_more.py` |
| Public car parks | City of Melbourne, Off-street car parks with capacity and type (2024 census year, Commercial) | CC BY 4.0 | `parking.py` |
| Heritage buildings | Heritage Council of Victoria, Victorian Heritage Database API (Victorian Heritage Register places) | CC BY 4.0 | `heritage.py` |
| Transit under construction (Suburban Rail Loop East) | OpenStreetMap via Overpass (`fetch_more.py` step construction); facts from bigbuild.vic.gov.au in our own words | ODbL | `construction.py` |
| Events page and Happening nearby | What's On Melbourne (whatson.melbourne.vic.gov.au): its public MCP server (search_tool, sub-category events) and each event's page (sessions table, schema.org Event, meta tags) | © City of Melbourne; non-commercial reuse only (NONCOMMERCIAL.md) | `fetch_happening.py` |
| Address row | Vicmap Address (`fetch_addresses.py`) | CC BY 4.0 | `addresses.py` |
| Where to vote (state election, November 28, 2026): early and election day voting centres | Victorian Electoral Commission, venues spreadsheet linked from vec.vic.gov.au/voting/2026-state-election/voting-locations (daily, `fetch-melbourne-voting.yml`) | CC BY 4.0 (© Victorian Electoral Commission) | `fetch_voting.py`, `voting.py` |
| Where each voting centre is | Vicmap Address, via the Vicmap open data WFS (each venue's address looked up; kept in `raw/voting/sites.json`) | CC BY 4.0 | `fetch_voting.py` |
| Trams and metropolitan buses (card's Transit nearby, bus layer) | Transport Victoria GTFS Schedule, folders 3 and 4 (`surface.json` "inner") | CC BY 4.0 | `engine/fetch_surface.py` |
| V/Line trains and coaches (Routes page; V/Line coaches layer) | Transport Victoria GTFS Schedule, folders 1 and 5 (`surface.json` feed `vline`, November 15, 2026) | CC BY 4.0 | `engine/fetch_surface.py melbourne vline` |
| Main streets, freeways, the Yarra, place points, landmark positions | OpenStreetMap via Overpass | ODbL (© OpenStreetMap contributors) | `fetch.py` |

## Quirks
- The ABS map service answers GitHub's runners; its field names are lower case (`sal_name_2021`, `lga_name_2021`).
  ABS boundaries follow the coast, so the land is Victoria's outline and the bays are what's left of the frame.
- The DataPack for Victoria's SA1s is 100 MB zipped; `fetch.py` keeps the City box's SA1 rows and only the columns
  `profiles.py` reads (G01, G02, G36, G37, G10C, G13 persons), about 0.6 MB.
- The ABS locality "Melbourne" is both the CBD (3000) and the St Kilda Road precinct (3004). `build.py` splits it at the
  Yarra into "Melbourne CBD" and "St Kilda Road". OpenStreetMap names some stretches of the river "Yarra River
  (Birrarung)", so the river is fetched under either name (a gap past Birrarung Marr otherwise).
- The 2021 boundaries carry Moreland's old name; the map says Merri-bek (renamed September 2022). Macedon Ranges
  reaches into the ABS's Greater Melbourne but isn't one of the 31 metropolitan councils, so it's land beyond the region.
- The Census was taken on August 10, 2021, in Melbourne's sixth lockdown with the international border shut: the CBD's
  student population was low and travel to work meaningless, so there's no getting-to-work lens. Suburbs where the
  City has under 300 residents (its slivers of Port Melbourne, Carlton North and South Wharf) get no profile.
- Rent and mortgage figures are averages of SA1 medians weighted by renting or mortgaged households, not true medians.
- Transport Victoria's GTFS colours each metro line by its group (since the Metro Tunnel, Sandringham, Werribee and
  Williamstown share pink) and each tram route by its own colour; `transit.py` uses them and writes the CSS rules
  pasted into `city.css` (`tmp/tram_css.txt`) and the badge maps for `city.json` (`tmp/badges.json`).
  V/Line's "Pakenham Line (VLINE)" route (V/Line's listing of its trains on the Metro line) is left out.
- The VEC's venue spreadsheet has addresses but no coordinates: `fetch_voting.py` looks each up in Vicmap Address
  (the number on the street, else the street in that suburb) once and keeps the result. Joint centres (one venue
  serving two districts) appear once per district; `voting.py` keeps one. Every early voting centre is also an
  election day centre from this election.

## Discovery places (November 19, 2026, on dev, for Along the way)
`cities/melbourne/discover.json` and `viewpoints.json` → `engine/discover/build.py melbourne --fetch` → `docs/melbourne/data/discover.geojson`; raw CSVs in `raw/discover/`. Refreshed weekly by `.github/workflows/fetch-discover.yml`. Unlike the `fetch*.py` scripts above, these hosts answer from GitHub Actions and from the Mac.

| Source | Use |
|---|---|
| City of Melbourne Open Data, Outdoor artworks (`outdoor-artworks`, updated September 2026) | Public art (kind `art`) and memorials, monuments, busts and cairns (kind `history`): title, type, year, makers; the City's description quoted word for word (HTML line breaks kept as paragraphs) with the credit "City of Melbourne, Outdoor artworks". Drinking fountains and temporary works are left out. |
| City of Melbourne Open Data, Public artworks, fountains and monuments (`public-artworks-fountains-and-monuments`) | The same works and some more: structure, year, artist; no description. Rows naming a work the first list has merge into it. |
| City of Melbourne Open Data, Public memorials and sculptures (`public-memorials-and-sculptures`) | Title only; almost all merge into the lists above. Drinking fountains left out. |
| Victorian Heritage Register, as Vicmap publishes it (`open-data-platform:heritage_register` on opendata.maps.vic.gov.au, Greater Melbourne's box) | Registered places (kind `history`, "Victorian Heritage Register"), each linked to its Victorian Heritage Database page (`hermes_num`). Vicmap cuts names at 50 characters: those are looked up once in the Heritage Council's API (`raw/discover/vhr_names.json`). Registered objects, generic house names ("Residence", "Terrace") and places over 40 ha (water supply systems, headlands) are left out. No description: the Database's own summary opens from the link. |
| The Shrine of Remembrance's and the City of Port Phillip's own pages | Viewpoints (`viewpoints.json`): only places whose owner's page names the view or the lookout; our own one-line wording; `checked` dates. |

Licence: CC BY 4.0 for every source (City of Melbourne Open Data; Vicmap and the Heritage Council of Victoria, State of Victoria). Credit each with the text, as the page does.
