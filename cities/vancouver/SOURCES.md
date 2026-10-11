# Vancouver: data sources

Fetched in GitHub Actions (`.github/workflows/fetch-vancouver.yml`): pushing a changed `cities/vancouver/fetch*.py`
to main runs it and commits what it writes under `raw/`. The sandbox can't reach these hosts. Scouting notes are
in `scouting/vancouver/FINDINGS.md`.

| What | Source | Licence | Script |
|---|---|---|---|
| The 22 local areas | City of Vancouver Open Data, `local-area-boundary` | Open Government Licence – Vancouver | `fetch.py` |
| Municipalities and reserves of Metro Vancouver (census subdivisions, shoreline-clipped) | Statistics Canada, 2021 cartographic boundary files, via its map service (geo.statcan.gc.ca, layer CSD) | Statistics Canada Open Licence | `fetch.py` |
| Dissemination areas in the City | Statistics Canada, 2021 cartographic boundary files (layer DA) | Statistics Canada Open Licence | `fetch.py` |
| Land beyond the region (census divisions, coarse) | Statistics Canada, 2021 cartographic boundary files (layer CD) | Statistics Canada Open Licence | `fetch_land.py` |
| Washington State outline | U.S. Census Bureau, cartographic boundary file 1:500k (2023) | Public domain | `fetch.py` |
| 2021 Census figures by dissemination area | Statistics Canada, Census Profile web data service (STC_CP, DF_DA) | Statistics Canada Open Licence | `fetch_census.py` |
| Main streets, highways, place points, landmark positions | OpenStreetMap via Overpass | ODbL (© OpenStreetMap contributors) | `fetch.py`, `fetch_land.py` |
| SkyTrain, SeaBus, West Coast Express | TransLink GTFS (static, weekly) | TransLink's GTFS terms of use | `fetch.py` |

## Quirks
- www12.statcan.gc.ca (bulk boundary and profile downloads) answers GitHub's runners with 403 Forbidden, whatever
  the User-Agent (`raw/probe.json`). geo.statcan.gc.ca and api.statcan.gc.ca answer, so boundaries come from the
  map service and the profile from the web data service. The map service's layers carry no division or
  subdivision fields: subdivisions are picked by the start of their code (`5915…` is Metro Vancouver), dissemination
  areas by code and the City's box, and `profiles.py` keeps those whose inside point is in the City.
- The City publishes no 2021 local-area profiles (its portal stops at 2016), so dissemination areas are summed into
  local areas. The two medians (home value, rent) are averages of the areas' medians weighted by households, not
  true medians; the card says so.
- The local areas leave out Stanley Park (about 4 km²). It joins the units file as its own shape (code 23) with
  no census figures, and joins the Downtown side.
- The City of Vancouver census subdivision leaves out the Musqueam reserve (Musqueam 2), which the City's
  Dunbar-Southlands local area includes; it shows as a neighbour, "Musqueam 2 (reserve)".
- Overpass often times out on the regional queries; `fetch_lib.py` tries three servers six times, and a failed
  step keeps the last good file.
- TransLink GTFS: West Coast Express platforms are separate stops ("Moody Centre Station @ West Coast Express");
  the build merges them into one station each.

## Commercial use (check before any)
TransLink's terms let it ask who uses the data and charge commercial users who charge end users. OpenStreetMap's
ODbL is share-alike for the database. The City's and Statistics Canada's licences allow commercial use with
attribution.

## How addresses work
- `fetch_streets.py` fetches the City's `public-streets` blocks (OGL – Vancouver): each block of each public
  street with its hundred-block address ("2300 W 47TH AV"). `address_prep.py` takes the dividing streets (Ontario
  St, Carrall St) from them, the W/E main streets from OpenStreetMap, and fits how block numbers run south of
  False Creek (raw/address_axes.json). Downtown's grid is turned 45 degrees and numbered on its own, so the card's
  block readout stops at False Creek.
