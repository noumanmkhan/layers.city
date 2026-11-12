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
| Where to vote (state election, November 28, 2026): early and election day voting centres | Victorian Electoral Commission, venues spreadsheet linked from vec.vic.gov.au/voting/2026-state-election/voting-locations (daily, `fetch-melbourne-voting.yml`) | CC BY 4.0 (© Victorian Electoral Commission) | `fetch_voting.py`, `voting.py` |
| Where each voting centre is | Vicmap Address, via the Vicmap open data WFS (each venue's address looked up; kept in `raw/voting/sites.json`) | CC BY 4.0 | `fetch_voting.py` |
| Trams and metropolitan buses (card's Transit nearby, bus layer) | Transport Victoria GTFS Schedule, folders 3 and 4 (`surface.json` "inner") | CC BY 4.0 | `engine/fetch_surface.py` |
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
