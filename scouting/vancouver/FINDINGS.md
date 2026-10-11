# Vancouver: scouting findings (October 11, 2026)

Run: `.github/workflows/scout-vancouver.yml` → `scouting/vancouver/out/`. Decisions with the user:
units are the City's 22 local areas; sides East / West / Downtown; skyscraper cut-off 100 m;
representatives wired after the October 17 civic and October 24 provincial elections; the map
will live at maps.noumankhan.ca/vancouver, with no hub card until the user says so.

## City portal (opendata.vancouver.ca, Opendatasoft)
- 200 datasets; 196 under the Open Government Licence – Vancouver (commercial use allowed), 4 with no licence field.
- Local areas: `local-area-boundary`, 22 areas, names as expected. Saved as out/local-areas.geojson.
- Census: the portal stops at 2016 (`census-local-area-profiles-2001…2016`, legacy files only).
  No 2021 local-area profile. Build 2021 rows from Statistics Canada dissemination areas
  aggregated to the 22 areas (StatCan Open Licence), as Chicago aggregates tracts.
- Heritage buildings: `heritage-sites`, 2,495 records (2,359 buildings; also monuments, trees,
  parks, archaeological sites, streetscapes), groups A 272 / B 1,173 / C 818, municipal
  designation 684, in a Heritage Conservation Area 85. Last updated March 2023. Has a building
  name field. A Toronto-style "designated only" cut would be the 684 municipally designated.
- Heritage districts: no boundary dataset. First Shaughnessy HCA only exists as a by-law map;
  Gastown and Chinatown as zoning districts (`zoning-districts-and-labels`, HA-1/HA-2 to check).
- What's changing: `issued-building-permits`, 52,337 since 2017, updated daily, with type of work
  (New Building 11,990; Demolition / Deconstruction 7,144), specific use (Single Detached House,
  Laneway House, Multiple Dwelling…), local area and a point. No rezoning or development
  application dataset: permits only, like Chicago. Applicant and contractor names are in the
  data; never keep them.
- Nearby: `libraries` 22 points, `community-centres` 27 points (both last updated 2020; check
  for renames), `parks`, `parks-facilities` (playgrounds 114, tennis 43, off-leash 37, field
  houses 56), `dog-off-leash-parks` 54. No hospital dataset: curate.
- Schools: `schools` 194 points (121 public, 54 independent, 19 StrongStart), 2023. Points only.
- Transit: `rapid-transit-lines` and `rapid-transit-stations` (22 stations in the city, 2023).
- Road closures: `road-ahead-current-road-closures` (23, with completion year),
  `road-ahead-projects-under-construction`, `road-ahead-upcoming-projects`. City projects, not
  transit-only; Broadway Subway work would need a filter.
- Trees: `public-trees` 184,377 (October 2026).
- Elections: `municipal-election-results`, `voting-places-*`; council is at large.
- Addresses and streets: `property-addresses`, `public-streets` 17,072, `street-intersections`,
  `one-way-streets`, `bikeways`, `shoreline-2002`.

## TransLink GTFS
- Downloads without a key from Actions (16 MB). One agency. 233 bus routes, 3 SkyTrain (type 1),
  1 West Coast Express (2), 1 SeaBus (4), 1 type 715 (on-demand). 8,927 stops. Calendar
  September 7, 2026 to January 3, 2027.

## DataBC
- Provincial electoral districts: 93. Municipalities: 160 province-wide (Metro Vancouver's
  subset to pick). WFS works from Actions.

## Old streams (UBC Dataverse)
- 7 files; the dataset's licence on Borealis is CC0 1.0. Open geometry, so a "Lost streams"
  layer meets the user's rule.

## Build order proposed
1. Base: local areas, sides, shoreline, regional municipalities, main streets, SkyTrain/SeaBus/WCE.
2. Census rows and lenses (DA → local area), facts.
3. Transit layers and Transit nearby (TransLink GTFS), transit-time lens "To Waterfront".
4. Heritage buildings, What's changing, Nearby, skyscrapers (100 m), canopy, addresses.
5. Representatives after October 24.
