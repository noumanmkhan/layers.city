# Layers.City data contract (schema 2)

> **Migration to schema 2 (October 18, 2026, on dev):** single-category `places` layers were merged into
> multi-category ones. Removed layer ids: `unis` and `colleges` (now one layer, `campus`), `churches`, `mosques`,
> `hindutemples`, `synagogues`, `buddhisttemples`, `gurdwaras` and `otherfaith` (now `worship`), `halal` and
> `kosher` (now `food`); in Toronto, `frschools` and `immersion` (now `schools`, as its `fr` and `imm` groups). A merged layer has `cats` instead of `cat` (see `places` in section 4); its `replaces`
> maps each old id to its category. Nearby rows (`card.nearby.nearest`) now name `"layer:category"`
> (`"worship:mosque"`) instead of the old layer id. The data files and feature `cat` values are unchanged.

> **October 28, 2026:** section 15 (transit: stops near a spot, routes, live arrivals) and `city.json` `transit`.
> Additive; schema stays 2.
> **October 30, 2026:** a transit lens may offer several hubs (`hubs` on the lens, `lens.hubLabel`; section 4 and the
> Living here rows): Toronto (Union or Bloor-Yonge), New York (Penn Station or Grand Central) and San Francisco (Montgomery St or 4th & King). Additive:
> the lens's own `key`, `minutes`, `short` and `note` still name the default hub.
> **October 28, 2026, later:** `transit.sched`, `transit.schedFiles` and the `sched/` files (section 15, "Scheduled times"): the next
> scheduled departure when there are no live times. Additive.

This is everything an app needs to rebuild the map's "What's here" card from the published
data, without reading the website's code. The website (this repo) is the only producer; an app is
a read-only consumer. Last updated October 18, 2026 (New York City on dev, unlisted: `docs/nyc/data/` has the same files as Toronto where it has the layer, with these differences: `schools.geojson` `b` is the community school district ("District 2") and `cat` `secondary` covers middle and high schools; `parks.geojson` amenities are `play`, `water` (spray shower) and `dog` (dog run), `u` the NYC Parks property number; `community.geojson` `centre` is an older adult center, and (since October 19, 2026) a third `cat`, `cc`, is a community center (NYC Parks recreation centers, NYCHA community centers and Beacon centers in schools; `sub` says which), also a `nearby.json` group `cc`; `nearby.json` adds bare-point groups `spray`, `dogrun` and `basketball`; no `er` (no open list of emergency departments). `evacuation.geojson` (hurricane evacuation zones 1 to 6, a `patches` layer `evac`: `zone` 1–6, `name`, `lp`; a card row "Evacuation zone" with `empty` when the spot is in none) and the `nearby.json` named group `evaccenter` (NYC Emergency Management's evacuation centers); `closures.geojson` (street closures for rapid transit construction from NYC DOT's closures by block, all `kind` `closed`, no `who` or hours), `events.geojson` (special-event street closures in Toronto's shape, from NYC's permitted events placed on the street centerline; `organizer` is the permit's event name), `changes.geojson` (New development, from DOB NOW job filings: kinds `building` and `demolition`, all four stages, `n` the DOB job number, no `u`; since October 19, 2026 also kind `rezoning` from City Planning's land-use applications (ZAP) with a zoning map amendment, stages `proposed` and `approved` only, `n` the ZAP project id, `u` its ZAP page, and for approved ones a new `dl` value, `decided`, the date City Planning closed the project; an area rezoning sits at the middle of its lots and its `d` starts with the lot count; additive), `crz.geojson` (the Congestion Relief Zone, one polygon, a `patches` layer `crz` and a card row "Congestion toll" shown only inside it), `ferry_lines`, `ferry_lines_inner` and `ferry_stations` (NYC Ferry and the Staten Island Ferry in the `rail` file shapes, a `rail` layer `ferry` with `pane: "transit"`, so lines on water draw above the city mask and landings are never marked outside); a `patches` layer may set `clsBy` (a property) to shade each feature by its value. `card.address.within` (`{layer, name, elsewhere: {name: text}}`) limits the Address row to one area of a layer (New York: the Manhattan borough); a spot elsewhere shows `elsewhere[its name]` as the row, or no row. `badges.json` and a `badges` layer under `cd` (13 drawings). `parking.geojson` and the `spots` layers `greenp` (Municipal parking) and `ev` in a Parking & Charging group. All additive. Before that, Toronto Sports & rec on dev: `sports.geojson`, a `places` layer `sports` in *Outdoors* whose features may list several categories in `cats`, and the layer options `narrow` and `search`; additive. Before that, layer panel reorganised on dev in every city: `groups` now run Places, Outdoors, Getting around, What's changing (the `live` layers), Education (universities, colleges, French schools), Parking & Charging, Representation, Faith & Community, Lenses (`lens`, `drive`); improvement areas (`bia`, `ssa`, `pid`) moved to Places; `under` changed on `badges` (now `nbhd`, Toronto), `unis`, `colleges`, `addr` and `closures` (now top level) and `events` (now `closures`); the `chg` layer's `name` is "New development"; Toronto opens with `boroughs`, `areas`, `cultural` and `tram` off. Ids, kinds and files unchanged; display only. Before that, Toronto Parks on dev: `parks.geojson` and the `parks` layer kind, in a new *Outdoors* group; additive. Before that, October 17, 2026: Toronto parking on dev: `parking.geojson` (Green P car parks and EV chargers, the `spots` layer kind), `permit_areas.geojson` (a `patches` layer), profile fields `permit` and `permitBand`, and a Permit parking row on the card with a `cover` line; all additive. Before that, October 16, 2026: Vancouver on dev reaches Toronto's features: `institutions`, `skyscrapers` (100 m cut-off), `heritage` districts (with a `kind` line: historic area or heritage conservation area), `heritage_buildings` (`t` is the Heritage Register's evaluation group, "Group A"), `french_schools`, `faith` (no halal or kosher shops), `collectors`, `bikes`, `bikeshare` (Mobi), `changes` (issued permits only, every item at stage `approved`), `construction`, `provincial.geojson` and `federal.geojson` (outline layers cut to the city line), `bia`, `nearby.json`, `representatives.json` (MPs only until the October 2026 elections), `voting.geojson` in Dallas's vote-centre shape with one area `k` `vancouver`, the suburban drive lens and a `canopy` profile field; Chicago on dev: Pace buses (`m` `pace` in `transit.json`, a `regional` layer `pace`, a Transit nearby row) and Faith & Community (`faith.geojson`, the nine `places` layers, Nearby rows); Dallas on dev reaches Toronto's features: `institutions`, `nearby.json`, `skyscrapers`, `heritage` landmark districts, public improvement districts (`pids.geojson`), a `school` boards file with ISDs and Dallas ISD trustee districts, `collection.geojson`, `bikes.geojson`, `transit.json`, the suburban drive lens, `canopy` and `downtown` profile fields, `representatives.json`, and an office `file` for seats on lines the map doesn't draw (`us_house_2021.geojson`); Bike Share stations on dev: `bikeshare.geojson` and the `docks` layer kind in Toronto, under Bike lanes, and a Bike Share row in Transit nearby (`card.transit.bikeshare`); Neighbourhood badges on dev: `badges.json` and the `badges` layer kind in Toronto, drawings only; Bike lanes: `bikes.geojson` and the `bikes` layer kind in Toronto and Chicago; French schools: `french_schools.geojson` and two more `places` layers in Toronto; Faith & Community: `faith.geojson`, nine more `places` layers in Toronto, Nearby rows that show only while a named layer is on; Skyscrapers: the `towers` layer kind, `skyscrapers.geojson` and a tower block on the card; campuses off the Landmarks file, their nicknames now on the Universities layer as `aliases`; `under` on layers nested under Landmarks; `distance` unit, Chicago in miles with a half-mile Nearby radius; Chicago's Schools section and `attendance.geojson`; Nearby section and `nearby.json`; institution points: the `places` layer kind and `institutions.geojson`; school boards in both cities: the `boards` layer kind, a School wards / School board row and trustee rows, with Chicago's leader and citywide president; earlier: map layers and `palette`, section 11; card title names the neighbourhood; profile facts; Chicago's To the Loop fields).

## 1. Ground rules

- **Read only from the published site**, never from GitHub:
  `https://layers.city/<city>/data/<file>`, where `<city>` is `toronto` or `chicago`.
- **Start with `city.json`** for each city. It says which files exist, which layers the card tests,
  what the card rows say and how lens tiers are labelled. Don't hard-code layer ids, file names or
  labels in the app; read them from `city.json` so a new city works without an app update.
- **Check `schema`.** `city.json` has `"schema": 1`. If an app sees a number it doesn't know, it
  should keep using its last good copy and ask the user to update, not crash.
  - Adding a field, a file, a layer or a card row is **not** a breaking change. Ignore unknown keys.
  - Renaming or removing a field or file, or changing a field's meaning or units, **is**, and bumps
    the number.
- **Caching.** Cloudflare Pages serves the files and browsers revalidate them on each request (no long-lived cache). The data changes rarely
  (representatives weekly at most, everything else on rebuilds), so caching for a day and
  refreshing in the background is fine. Bundle a copy in the app for offline use.
- **Sizes.** Each city is about 2 MB of JSON in all (largest: Chicago's `base.geojson`, 0.8 MB).

## 2. The rules the data comes with (not negotiable)

- **Describe, don't rank.** The card describes the place the user picked. Demographic fields
  (language at home, and anything similar added later) never feed rankings, colours, filters,
  "best/worst" lists, notifications or comparisons.
- The lens tiers (`cost`, `commute`, `tenure`, `unionBand`, `loopBand`) and the profile `facts`
  (section 7) are the only precomputed comparisons. Show tiers with their labels and notes from
  `city.json`, and facts with their own text. Don't compute other rankings or superlatives in the
  app; facts never use demographic fields, and the app shouldn't either.
- Always show the caveat lines from `city.json` (`card.living.caveat`, `footer`, the language
  `note`) wherever the figures appear, including widgets, even if shortened.
- Show `attribution` from `city.json` somewhere in the app (an About screen is fine).
- No crime, school scores or other evaluative data on the card.

## 3. Files

All coordinates are WGS84. GeoJSON positions are `[longitude, latitude]`; most other places in
`city.json` use `[latitude, longitude]` (noted below). Polygons may be `Polygon` or
`MultiPolygon` and may have holes.

| File | What it is |
|---|---|
| `city.json` | The city's config (section 4). |
| `base.geojson` | Outline shapes. `properties.kind`: `city` (the city itself), `neighbour` (each surrounding municipality, with `name`, `region`, `lp`, `drive`, and optional `minor`: true for a small town in a dense region, such as New Jersey's boroughs, whose name the site shows only from zoom 12), `outside` (land beyond the region), and optionally `annex`: land beyond the city limits that the map treats as part of the city view (Vancouver's University Endowment Lands): drawn shaded and outlined apart, never masked, and counted inside the footprint, so the card works there as in the city. The units file names it as a unit (Vancouver's code 24, with `park` saying it's beside the city, `aka`, `gov` and `votes`); its profile carries `apart: true` (tiers placed against the city's units; never in facts). Card facts rows may carry `skipEmpty` (no row when the text fills to nothing). Added October 16, 2026; additive. |
| `regions.geojson` | Label points for regions/counties. Not needed for the card. |
| Layer files | One per map layer, named by `file`/`files` in `city.json` `groups`. Section 5 lists the ones the card uses. |
| `city.json` `pageLinks` | Toronto (October 27, 2026). Links to the site's own pages that the web map's layer panel shows as rows in a group: `[{group, id, name, note, href}]`, `group` matching a `groups` title, `href` a site path (`/toronto/routes/`, the Where does this line or route go? page). Not a layer; an app may show them as links to layers.city or ignore them. Additive. |
| `nbhd_profiles.json` / `ca_profiles.json` / `la_profiles.json` | Census figures per neighbourhood / community area / local area (Vancouver, in progress). File name is `lens.file` in `city.json`. Section 7. A unit with no entry here (Vancouver's Stanley Park, code 23) has no Living here rows and takes no lens tier. |
| `representatives.json` | Who holds each seat. Section 8. |
| `drive_grid.json` | Free-flow drive minutes to the hub on a ~1.5 km grid, outside the city. Section 6. |
| `region_places.json` | Toronto only: ~470 named GTA communities. `[{name, muni, region, kind, at:[lon,lat]}]`. |
| `lakes.geojson` | Dallas only (config `maskWater`): lakes beyond the city inside the region, `water: true`. Map drawing only: the city view's mask paints them water so district lines don't show through. Not needed for the card. |
| `region_areas.geojson` | Region/county outlines for the regional view. Not needed for the card. |
| `community.geojson` | Every city (on dev; October 18, 2026). Public libraries and community centres (points) for the `community` `places` layer, written by `engine/community.py` from the same points as `nearby.json`'s `library` and `centre` groups. `properties`: `name`, `cat` (`library`, `centre`). Top level `count` {`library`, `centre`}. Additive. A `places` layer may also set `minZoom` (12–14): the web map shows its icons from that zoom. |
| `nearby.json` | Points for the card's Nearby section: `{groups: {key: [[lon, lat, name?], …]}}`. Keys and labels come from `card.nearby` (section 5). Named kinds (`library`, `centre`, `er`, and in Toronto `mosque`, `gurdwara`, `synagogue`, `hindu`, `buddhist`, `church`, `halal`, `kosher`) carry a name; counted kinds (`park`, `playground`, …) are bare points. |
| `attendance.geojson` | Chicago only: CPS attendance areas for the card's Schools section. One polygon per school and grade range, all levels in one file. `properties`: `level` (`es` elementary, `ms` middle, `hs` high), `grades` ("K–8", "7–8", "9–12"), `name` (the school's full name), `url` (its CPS profile page, may be empty), `x`, `y` (the building, lon/lat; absent when unknown, then `addr` may name the street). Top-level `year` ("2025–26"). **New York** (`cities/nyc/zones.py`, DOE school zones): the same fields, plus optional `note` (the DOE's remark on a shared or split zone, shown as a second subline); `name` may join a shared zone's schools with " or ", or say there is no zoned school (most middle and high school areas: choice by application); high schools have no `x`, `y`; since October 19, 2026 each feature also has `board` (the same value as `level`), so the web map's School zones layer (`zones`, kind `boards`, `file` `attendance`) can draw one level at a time (additive). Areas of one level don't overlap. Describe only: no ratings, scores or enrolment. |
| `voting.geojson` | Only around an election (Toronto, and Chicago in precinct-only form): the voting subdivisions with each one's election-day voting place, for the card's where-to-vote box (`card.vote`, section 5). Built by `cities/toronto/voting.py` from the City's voting subdivisions and voting places (fetched daily in October by `fetch-voting.yml`). One polygon per subdivision; they don't overlap. `properties`: `c` code (ward, 2 digits, + subdivision, 3), `w` ward number, `a` the place's address, `x`, `y` the place (lon/lat), and when known `n` building name, `e` preferred entrance (left out when just "Main Doors"), `ae` accessible entrance when different, `vat` true where a Voter Assist Terminal is set up. Top-level `asof` (the City's last edit) and `election` (date). Advance voting places are not included. Chicago's file has no polling places (the Board publishes none by precinct): each feature is a precinct with `c`, `w`, `p` (precinct number) and, since October 20, `k: "chicago"`; the top level carries Chicago's vote centers in the same `centers` / `counts` format as Dallas's (the county key is "chicago"; any Chicago voter can use any of them), and `asof` is the date the site list was fetched (before October 20, the date the precinct layout was approved). Built by `cities/chicago/voting.py` from `fetch_vote_centers.py` (daily to election day in *Fetch Chicago voting places*). Dallas's file covers four counties: Dallas, Tarrant and Collin as one feature each (`k`: county key), Denton as its precincts (`k`, `c`, and the polling place's `n`, `a`, `r` room, `x`, `y`); top level `centers` [[x, y, name, room, address, county key, kind (1 election day, 2 early voting, 3 both)], …], `counts` {county: {ed, ev}}, `asof`, `election`. Built by `cities/dallas/voting.py` from `fetch_voting.py` (daily until election day in *Fetch Dallas voting places*). **New York** (`cities/nyc/voting.py`): one feature per election district, `c` "AD-ED" ("75-014"), `s` (election day site) and `e` (its assigned early voting site) as indexes into a top-level `sites` list of `[name, address, x, y]` (no x, y when a site couldn't be placed). Readers expand them to `n`/`a`/`x`/`y` and `en`/`ea`/`ex`/`ey`, as the site does on load; `card.vote.earlyLead` and `assignedDay` word the early-voting box. |
| `skyscrapers.geojson` | Buildings 150 m and taller (points) for the `towers` layer, from each city's Wikipedia list (CC BY-SA 4.0; credit "Wikipedia"), built by `engine/skyscrapers.py`. Sorted tallest first. `properties`: `name`, `h` (height in metres, architectural: spires count, antennas don't), `ft` (feet), `floors` (may be null), `year` (completed, or expected when `uc`; null when unknown), `use` (`res`, `com` office or hotel, `mix`), `purpose` (display word: "Residential", "Office", "Hotel", "Mixed-use"), `uc` (true until open for occupancy, including topped-out towers), `super` (true at 300 m+), `rank` (by height in the city among towers built or topped out; a tower still under construction gets the rank it will have), `facts` (1–3 short sentences, most telling first), and optionally `aka` (a former or popular name), `address`, `wiki` (English Wikipedia article title). Top-level `source`. |
| `heritage_buildings.geojson` | Heritage buildings (layer kind `heritage`, id `hbld`), built by `engine/heritage_buildings.py` from `cities/<city>/raw/heritage_buildings.json` (fetched monthly by `engine/fetch_heritage_buildings.py`). Properties protected one by one: Toronto, Part IV designations from the City's Heritage Register (listed properties and district-only Part V properties left out); Chicago, the City's Individual Landmarks (a point inside each landmark's shape). Top-level `asof`. `Point` features: `n` name (always in Chicago; Toronto only when the register's description starts with one, about half), `a` address, `y` year built, `ar` architect, `d` year designated, and Toronto only `b` designation by-law(s), `t` building type, `hcd` the Heritage Conservation District it is also in; Chicago only `id` ("L-176"). Any field may be missing. |
| `bikes.geojson` | Bike lanes (layer kind `bikes`, id `bikes`, loaded when the layer is first turned on), built by `engine/bikes.py` from `cities/<city>/raw/bikes.geojson` (fetched monthly by `engine/fetch_bikes.py`): Toronto, the City's Cycling Network; Chicago, CDOT's Bike Routes (no off-street trails); Dallas, the City's bike facilities, completed only (a few `trail` segments; most park trails aren't in it). Top-level `asof` (the City's last update of the data), `fetched`, `counts` and `km` per class. `LineString`/`MultiLineString` features, one per segment, sorted trails and shared first, protected last: `t` class (`prot` separated from traffic, `paint` painted lane incl. buffered and contraflow, `shared` sharrows, signed routes, park roads, greenways, `trail` multi-use trails, Toronto only), `d` the City's type in plain words ("Two-way cycle track"), `n` street or trail, optional `fr` / `to` its ends, `y` year installed (Toronto). Shows lanes as built: it says nothing about closures. |
| `sports.geojson` | Sports & rec (layer kind `places`, id `sports`, under *Outdoors*; Toronto only), built by `cities/toronto/sports.py` from the City's recreation facilities list. Top-level `asof` (a display date, e.g. "October 15, 2026"), `count` and `counts` {sport: locations}. `Point` features, one per park or centre: `name`, `cat` its first sport in the layer's `cats` order (the pin's glyph), `cats` every sport there (`pool`, `rink`, `diamond`, `field`, `tennis`, `pickleball`, `basketball`, `skatepark`, `cricket`), `sub` "Park" or "Community centre" (may be empty), `has` a readable list ("3 ball diamonds, 8 tennis courts, pickleball courts"), `addr`, optional `u` its toronto.ca page (full URL). New: a `places` feature may carry `cats` (several categories); it shows while any is picked. The layer's `narrow` means no chip is picked at first and none picked shows every place. |
| `parks.geojson` | Parks (layer kind `parks`, id `parks`, loaded when the layer is first turned on; Toronto only), built by `cities/toronto/parks.py`: the City's park outlines (Green Spaces, AREA_CLASS "Park": 1,629 parks, no cemeteries or golf courses), simplified to 2-3 m. Top-level `asof` {`parks` the City's parks list, `outlines` Green Spaces, `water` the OpenStreetMap fetch} and `count`. `Polygon`/`MultiPolygon` features, biggest first: `n` name, optional `a` the amenities it has, a subset of the layer's `amenities` keys in that order (`play` playground, `water` splash pad or wading pool, `wc` washroom, `dog` dog off-leash area), optional `u` its LOCATIONID on toronto.ca (the layer's `linkUrl` with `{u}`), optional `w` `splash`, `wading` or `both`. Splash pads and wading pools come from OpenStreetMap (ODbL) and miss some. On the site the chips narrow it: a park must have every picked amenity; the rest fade. San Francisco (unlisted, October 30, 2026): Rec & Park properties, amenities `play` and `dog` only, `u` the property id, `t` the property type ("Regional Park"); additive. |
| `bikeshare.geojson` | Toronto and Vancouver (Mobi): bike share stations (layer kind `docks`, id `bikeshare`, loaded when the layer is first turned on), built by `engine/bikeshare.py` from `cities/<city>/raw/bikeshare.json` (fetched weekly by `engine/fetch_bikeshare.py` from the system's GBFS `station_information`; stations not installed are left out). Top-level `asof` (the feed's date when fetched), `fetched`, `system` ("Bike Share Toronto"), `count`, `docks` (total), `charging`. `Point` features, sorted by name: `n` station name (tidied: " - SMART" dropped), optional `d` number of docks, `e` 1 where e-bikes charge, `nc` 1 where the kiosk takes no credit card (unlock with the app or a member key). No live counts of bikes or free docks. |
| `badges.json` | Toronto, New York (a layer under `cd`, no `align`, so the drawings stand upright) and San Francisco (under `nb`, no `align`; 16 drawings, October 31, 2026): neighbourhood badges (layer kind `badges`, id `badges`, loaded when the layer is first turned on), built by `engine/badges.py` from the units file, the area fills and the drawings in `cities/<city>/badges/*.svg`. `{units: [{n, b, w, h, f, art, svg}]}`, one per unit: `n` the unit's name, `b` `[[south, west], [north, east]]` the box the badge fills (the largest box of its shape inside the unit), `w` / `h` its viewBox size, `f` the name's font size in viewBox units, `art` true for a drawn badge, `svg` the inner SVG markup. Only two classes occur (corrected October 21, 2026; earlier drafts listed more): `bd-m`, a filled shape, and `bd-ms`, a stroked line (no fill, round caps, its width set on the element). Both are drawn in `--accent` (the brand red, resolve it through `palette`); knockouts are SVG masks inside the markup (`<defs><mask>`), so no second colour is needed and the drawing works on any background. The website shows them at 45% opacity over the map; at full opacity on a plain background (an app's stamp) they read as solid brand marks. No text: the unit's name is `n`. Apps may ignore it. |
| `changes.geojson` | What's changing (layer kind `changes`, loaded after the map; card section `chg`), built by `engine/changes.py` from `cities/<city>/raw/changes/` (fetched weekly by `engine/fetch_changes.py`). Big changes only: new buildings that aren't single houses, demolitions of buildings that aren't houses and (Toronto) rezoning, site plan and subdivision applications. Top-level `asof` (fetch date), `window` (years). `Point` features, one per site (items within 35 m merged): `k` kind (`rezoning`, `siteplan`, `subdivision`, `building`, `demolition`), `s` stage (`proposed`, `approved`, `building` = under construction, `finished`), `date` (YYYY-MM-DD) and `dl` what that date is (`applied`, `issued`, `finished`), `a` address, `d` short description, optional `u` (the City's page: Toronto applications), `n` (application or permit number), `units` (homes created, when known), `status` (the source's own status), `also` (`[[kind, stage, "YYYY-MM", url]]`: other items on the same site). Withdrawn, refused, cancelled, expired and suspended items are left out; open items up to 6 years old; approved items by application date within 4 years (the data has no decision date); finished within 2 years. Chicago has no `proposed` (no proposals data) and no completion date (`dl` is `issued`). San Francisco (unlisted, since October 30, 2026): the Planning Department's Development Pipeline, all `k` `building`, no `finished`; `units` is net new homes; `dl` may also be `decided` (Planning approval) or `started` (the date construction began, stage `building`); `n` the Planning case or building permit number. Additive. |
| `addresses.geojson` | How addresses work (layer kind `addresses`), built by `engine/addresses.py` from the city's own `streets` and `collectors` files and `cities/<city>/addresses.json`. Top-level `kind`: `grid` (Chicago) or `divide` (Toronto). **grid**: `LineString` features with `role` (`base` for the two zero lines, `mile` for the rest), `axis` (`ns`: an east-west line carrying a north/south number; `ew`: a north-south line carrying an east/west number), `num`, `dir` (`N`, `S`, `E`, `W`, or empty for 0), `street` (the street on that line) and `label` ("2400 N"); each line is straight across the city, clipped to its outline. Top-level `axes`: `{ns: [[lat, signed number]…], ew: [[lon, signed number]…]}` sorted by position, north and east positive; interpolate linearly between neighbours (and carry the end stretch's pace beyond them) to read a spot's address numbers. **divide**: top-level `street` ("Yonge St"; Vancouver "Ontario St"); features with `role` `divide` (that street, and in Vancouver also Carrall St downtown, each with its own `street`) or `e` / `w` (a drawn street named … E or … W that meets it; in Vancouver W … or E …, e.g. "W Broadway"), `street` the name. Optional top-level `axes` (`{ns: [[lat, number]…], ew: [[lon, signed number]…]}`, as a grid city's, sorted by position; `ns` numbers have no direction: they rise going south) and `axesArea` (`[west, south, east, north]`, where the axes hold): interpolate to read a spot's block numbers (Vancouver, south of False Creek). Card text: `card.address.blocks` (`{ns}`, `{ew}` with W or E). |
| `construction.geojson` | Transit lines under construction (layer kind `construction`), built by `engine/construction.py` from OpenStreetMap (ODbL) and the curated `cities/<city>/construction.json`. Line features (`LineString` or `MultiLineString`): `id`, `name`, `short`, `mode` (`subway`, `lrt`), `color` (hex), and optionally `owner`, `opens` (only an owner-published estimate, as text), `length` (text), `about`, `link`. Station features (`Point`): `part: "station"`, `id` (the line's), `name`. Only lines with construction under way; a line opens → it leaves this file. |
| `closures.geojson` | Optional; may be missing or empty (load it so a failure doesn't stop the map). Road closures and lane restrictions caused by transit construction (layer kind `closures`), rebuilt daily just after midnight Eastern by `engine/closures.py` from Toronto's Road Restrictions feed and Chicago's CDOT permits. Top-level `asof` (local time of the fetch, "YYYY-MM-DDTHH:MM") and `today`. `LineString` (or `Point` when a permit has no stretch). `properties`: `proj` (a line `id` from `construction.geojson`, `up` for work on an existing line being upgraded, or `other`), `name` (the project, display text), `street`, `extent` (text), `kind` (`closed` or `narrowed`), `art` (true on a drawn arterial; false = a local street, shown only zoomed in; lane work on local streets is left out), `start`, `end` (permit dates, "YYYY-MM-DD" or with time; not a reopening forecast), `hours` ("24h", "21:00–05:00" or null), `days` (`daily`, `weekdays`, `weekends`, `some days` or null), `both` (both directions), `who` (permit holder), `desc` (up to 220 characters). Includes permits starting within 7 days; hide those whose `end` is before today in the city's time zone (`tz` on the layer in `city.json`). |
| `events.geojson` | Optional (Toronto; may be missing or empty). Road closures for special events (layer kind `events`, id `events`), rebuilt daily with `closures.geojson` by `engine/events.py` from the Road Restrictions feed's records flagged as special events. Top-level `asof`, `today`, and `events`: one object per event with `id`, `name`, `short`, `organizer`, `start` and `end` (city time, "YYYY-MM-DDTHH:MM", first closure to last), `closures` (count), `bounds` ([[south, west], [north, east]], to frame it), `banner` (a big event the website announces), `bannerFrom` ("YYYY-MM-DD", when its banner and view start), optional `link` (organizer's site), `notice` (organizer's closure notice) and `courses` (race routes the organizer publishes, while the event is on: each with `name`, `km` (official distance), `line` ([lon, lat] points in running order), `marks` (one [lon, lat] per whole kilometre, `marks[0]` is km 1), `start` and `finish` ([lon, lat]) and `source`). Features: `LineString` (or `Point`), `properties`: `ev` (an event `id`), `street`, `extent`, `kind` (`closed`, or `narrowed` for a curb lane only), `both`, `start`, `end` (each closure's own times, city time; race closures open in waves), `desc`. Includes closures that haven't ended and start within 14 days; hide those whose `end` has passed in the layer's `tz`, and treat those whose `start` is later as upcoming. The layer's config carries the website's text and `viewLayers` (the layers its event view shows). |
| `collection.geojson` (Toronto), `sweeping.geojson` (Chicago) | Optional "pickup" files for the card's pickup row (`card.pickup.file`; October 14, 2026), loaded after the map. Top-level `kind: "pickup"`, `year`, `asof` (fetch date) and `sched` {key: [["YYYY-MM-DD", [item, ...]], ...]}: every date of the year, sorted. Polygon/MultiPolygon features, one per area, `properties.k` = the key into `sched`. Toronto: curbside collection areas (key = calendar, e.g. "Wednesday1"; items `green`, `garbage`, `recycling`, `yard`, `tree`), from the City's GIS layer and the yearly pickup calendar (fetch-toronto-collection.yml, monthly). Chicago: street sweeping ward sections (key "0101", plus `w` ward and `s` section; item `sweep`), April to November. Dallas: garbage and recycling day areas (key the weekday, "wednesday"; items `garbage`, `recycling`, every week of this year and next, worked out from the day), each split by brush route with `bw` (1–4, the week of the month brush and bulky trash is picked up) where the route has one. |
| `transit.json` | Streetcar and bus routes and stops, built by `engine/surface.py` from the agency's GTFS (TTC, CTA), refreshed monthly. Top-level `asof` (fetch date, "YYYY-MM-DD") and `week` (the Monday of the week the schedule was read for). `routes`: `[{r, n, m, f, day, h, b}]`: `r` route number (text: "29", "J14", "X9"), `n` name ("Dufferin"), `m` mode (`tram` streetcar, `bus`; in Toronto also `go`, below), `f` families (any of `freq`, `exp`, `reg`, `night`; below), `day` (false for a route that runs only overnight, e.g. Toronto's 300-series), `h` (typical wait in minutes on weekday middays, 10 am–3 pm, in the busier direction; null under one trip an hour), `b` bounds `[west, south, east, north]`. `stops`: `[[lon, lat, name, [route index, …]]]`, indexes into `routes`. Families describe the service and are never a ranking: `freq` = at least 6 trips an hour each way, averaged over every 3-hour block from 7 am to 7 pm on a weekday; `exp` = the agency names the route express; `night` = at least one trip each way in every hour from 2 to 4 am on a weeknight; `reg` = every other route with daytime service (neither `freq` nor `exp`). Other agencies (Toronto: GO buses, from Metrolinx's GO GTFS, refreshed with the TTC's; Chicago: Pace, from OpenStreetMap's route relations, because Pace offers its GTFS for non-commercial use only) join the same lists with their own `m` (`go`, `pace`), `r` prefixed so numbers never collide ("GO 41", not "41"; "Pace 270", with Pace's Pulse lines by name: "Pulse Dempster"), `f: []` (the families describe the city's own network), and `in: true` on routes with a stop inside the city. Pace routes have no schedule: `day` is true and `h` null for all of them. Top-level `feeds` (only when there are any): `{go: {asof, week, routes, in}}` (for Pace, `asof` and `week` are both the OSM fetch date). Apps that don't show GO or Pace buses can skip routes whose `m` isn't `tram` or `bus` (and stops served only by them). |
| `transit_routes.geojson` | One feature per route in `transit.json` (`MultiLineString`, simplified ~8 m: the route's busiest pattern, plus stretches of its other patterns and direction that run more than ~35 m from it, such as branches and one-way pairs). `properties`: `r`, `n`, `m`, `f`, `day`, `h` (and `in` for other agencies' routes) as in `transit.json`. Top-level `asof`, `week`, `feeds`. The website loads it only when the Bus routes layer is on or a route is picked. |
| `streetcars.geojson` | Toronto only: the features of `transit_routes.geojson` with `m: "tram"` and `day: true` (the 11 daytime streetcar routes), for the `streetcars` layer. |
| `collectors.geojson` | Collector streets (layer `coll`, kind `streets`, `under: "streets"`): one feature per street name (`LineString` or `MultiLineString`), `properties`: `name`, `cls` (`"coll"`), `len`. Toronto from the City's Collector road class; Chicago from OpenStreetMap `tertiary` roads. Stretches on a main street are left out. Drawn thinner than `minor` from zoom 13; `labelZoom` (15) is the zoom names start at; `yieldLabels` means its names give way to the main streets'. |
| `us_house_2021.geojson` | Dallas and San Francisco (unlisted): the congressional districts current members were elected on (Dallas: PLANC2193, clipped to the nine counties; San Francisco: California's 2021 map, cut to the city). `properties.num`. Not a map layer: the card's U.S. representative row looks the seat up in it (section 5, step 9). Dropped once the new members take office (January 2027). |
| `pids.geojson` | Dallas's public improvement districts (layer kind `patches`, id `pid`), like Chicago's SSAs: `name`, `lp`. From the City's layer; the "Premium" extra-assessment zones inside SouthSide and Vickery Meadow are left out. |
| `school.geojson` | Dallas's `boards` file: board `isd` (the independent school districts inside the city: `num` and `name` both the district's short name, "Richardson ISD") and board `disd` (Dallas ISD's nine trustee districts: `num` 1–9, `name` "Trustee district 4"). Clipped to the city. |
| `institutions.geojson` | Universities, colleges and hospitals (points) for the `places` layers. `properties`: `name`, `cat` (`university`, `college`, `hospital`), `sub` (campus, network or ownership, optional), `ed` (true for a hospital with an emergency department). Curated by fixed rules (public or nonprofit only; see each city's `institutions.py`). Describe only: no ratings. |
| `schools.geojson` | Toronto only (on dev; October 18, 2026). Every publicly funded school (TDSB, TCDSB, Viamonde, MonAvenir) inside the City, from the Ontario Ministry of Education's school list (Open Government Licence – Ontario; credit it), for the `schools` `places` layer. Built by `cities/toronto/schools.py`. Top level `asof` (school year, "2024–25") and `count`. `Point` features: `name`, `cat` (`elementary`, `secondary`), `g` grade range ("JK–8"), `b` board (`TDSB`, `TCDSB`, `Viamonde`, `MonAvenir`), `a` street address, `sub` (board, grades and program, display text), optional `grp` (`fr` French-language, `imm` French immersion) and `u` (the school's website). Describe only: no attendance areas, so never present a school as the one a home goes to. `nearby.json` gains bare-point groups `school_e` and `school_s`, counted on the card (`card.nearby.counts`). A `places` layer may have `popup` (`{rows: [[property, label]…], linkText, fine}` with `{asof}`): the web map shows those details on tap. San Francisco (unlisted, October 30, 2026): SFUSD's district-run schools from the State's directory; `g` grades ("K–5"), `b` the kind of school ("K–8 school"), not a district or board. |
| `french_schools.geojson` | Toronto only. French-language and French immersion schools (points) for two `places` layers. `properties`: `name`, `cat` (`frschool`: Conseil scolaire Viamonde and Conseil scolaire catholique MonAvenir, taught in French; `immersion`: TDSB and TCDSB French immersion schools), `sub` (board, then level for `frschool` or program for `immersion`: "Early immersion", "Middle immersion", "Early and middle immersion", "Immersion from JK", "Secondary immersion"). Positions from the City's school locations; lists from the boards. |
| `faith.geojson` | Toronto and Chicago. Places of worship and certified food shops (points) for the Faith & Community `places` layers. `properties`: `name`, `cat` (`mosque`, `gurdwara`, `synagogue`, `hindu`, `buddhist`, `church`, `otherfaith`, `halal`, `kosher`), `sub` (what it is, with denomination where known; for shops, branch, roles and certifier). Churches carry `grp` where the OSM denomination or the name gives one: Toronto `catholic`, `anglican`, `baptist`, `united`, `presbyterian`, `orthodox`, `evangelical`, `other`; Chicago `catholic`, `baptist`, `methodist`, `lutheran`, `episcopal`, `presbyterian`, `orthodox`, `evangelical`, `other` (the Churches layer's `groups` list them). Shops also carry `roles` (any of `grocer`, `butcher`, `bakery`; New York also `fish market`) and `cert` (Toronto `HMA`, `COR`; Chicago `HMS`, `cRc`, `OU`; New York, since October 19, 2026, free text from the State registry: "certified by …" or "self-certified"). Chicago's churches are those inside the city; its other places of worship and its shops cover Chicagoland. Places of worship from OpenStreetMap plus hand-kept additions; shops from the certifiers' lists. Facilities only: nothing in the data describes who lives anywhere. |
| `parking.geojson` | Toronto (October 17, 2026) and New York (October 19). Green P car parks and public EV chargers (points) for two layers of kind `spots` (ids `greenp`, `ev`), loaded when either is first turned on. Built by `cities/toronto/parking.py` from `cities/toronto/raw/parking/` (fetched monthly by `fetch_parking.py`). Top level `asof` {`gp`: the Green P list's date, `ev`: the charger fetch date} and `count` {`greenp`, `spaces`, `ev`, `l2`, `dc`}. Every feature has `c` (`gp` or `ev`, the layer's `cat`) and `n` (its name). **Green P** (`c: "gp"`): the City's 2019 list (its latest; not refreshed since, so lots may have closed or opened): `n` the address, `t` `g` garage or `s` surface lot, `cap` spaces, `h` clearance in metres (garages that list one), `ttc` 1 for a TTC commuter lot, `id` Green P's car park number. No rates: they've changed since 2019. **EV chargers** (`c: "ev"`): public stations from the Alternative Fuels Data Center (the listings behind Natural Resources Canada's locator), plus City-operated chargers it lacks; private and residents-, guests- or staff-only stations left out. One point per place: `n` name (an operator's name is moved to `op` and the address used), `a` address, `l2` Level 2 ports, `dc` DC fast ports, `l1` Level 1 ports (rare), `kw` the fastest DC charger's power, `net` network(s) joined with " · ", `op` operator, `h24` 1 for open 24 hours daily else `hrs` as listed, `fee` price as listed, `tes` 1 for Tesla only, `off` 1 when listed as temporarily unavailable, `conf` the date the listing was last confirmed, `city` 1 for a City-operated charger. Every count field is missing when zero. **New York** (`cities/nyc/parking.py`): `c: "gp"` is the city-run car park category, here NYC DOT's municipal garages and fields from its list (kept by hand in `cities/nyc/parking.json`): `n` the facility's name, `t` `g` garage or `s` field (surface lot), `cap` spaces, `h24` 1 for 24 hours, 7 days, else `hrs` as the City gives them, `a` where the City gives a block rather than an address, `note` a closure the City announces; `asof.gp` is the list's date. Chargers as Toronto's, from the Alternative Fuels Data Center only, no `city`. Lots in either city may now carry `a`, `h24`, `hrs` and `note` (additive). San Francisco (unlisted, October 30, 2026): `c` `gp` is SFMTA's off-street list (garages and lots of SFMTA, the Port, Rec & Park and Caltrans), with `own` (who owns it) and no hours; `permit_areas.geojson` holds the Residential Parking Permit areas (`name` the letter, "HV"). Additive. |
| `tsunami.geojson`, `seismic.geojson` | San Francisco only (unlisted, October 30, 2026): the State's tsunami hazard area and seismic hazard zones (liquefaction or landslide), one shape each, `patches` layers `tsunami` and `seismic` with card rows "Tsunami hazard area" and "Seismic hazard zone" (`empty` when the spot is in neither). San Francisco also has `ferry_lines`, `ferry_lines_inner` and `ferry_stations` in New York's shapes (a `rail` layer `ferry`), bike `shared` segments of type "Slow Street", and a `nearby.json` bare-point group `soft` (soft-story retrofit buildings, counted only). Additive. |
| `cbds.geojson` | San Francisco only (October 31, 2026): the City's Community Benefit Districts, its business improvement districts (16, from OEWD via DataSF), a `patches` layer `cbd` in Places: `name` ("Union Square", "Castro/Upper Market"), `kind` `CBD` or `BID`, `since` (the year it was set up, when known), `lp`. A card row "Benefit district" (`empty` "None") and a pill. The `cultural` patches layer now sets `cls` and `lcls` (own colour in `city.css`). Additive. |
| `tech_hq.geojson` | San Francisco only (unlisted, October 30, 2026): technology headquarters across the nine counties, a `places` layer `tech` (`cat` `chips`, `hardware`, `software`, `internet` or `ai`; `name`, `sub` "Chips · NVDA · Santa Clara", `a` the address, optional `y` year founded). The layer sets `wide: true`: its icons show from zoom 9 and names from 11 (other places layers: 11 and 14). Nothing about size or value is published; the inclusion rule is in `cities/sf/tech_hq.json`. Additive. |
| `permit_areas.geojson` | Toronto only (on dev). The City's on-street permit parking areas (a `patches` layer, id `permit`): `name` (the area code, "12B"), `lp`. Top level `asof`. A permit area is where residents may buy a permit for the signed streets inside it; not every street in an area has permit parking. |

Properties that appear on many features: `name`, `lp` (a label point, `[lon, lat]`), `code`
(a unit number), `num` (a ward or district number).

### Point layers used for search

- **Landmarks** (the `landmarks`-kind layer; file `landmarks.geojson`): ~40 curated points per
  city. Properties: `name`, `cat` (`park`, `music`, `culture`, `sports`, `civic`, `airport`;
  `campus` is no longer used: campuses are on the Universities layer), `catLabel` (display text, e.g. "Sports venue"), `tier` (display priority; 1 is
  most prominent), `aliases` (other names people search for, e.g. "Air Canada Centre" for
  Scotiabank Arena; may be empty).
- **Known-as names** (the `knownas`-kind layer; `cultural.geojson` in Toronto,
  `knownas.geojson` in Chicago): `name` and `kind` (`district`, `village`, `enclave`).
- **Units** (the `units`-kind layer): `name` and `code`. A unit that isn't one of the city's official units carries a text `park` (Vancouver's Stanley Park, code 23: "a park, not one of the 22"); it has no profile.
- **`region_places.json`** (Toronto only): see the table above; an entry may also have `alt`,
  a list of other names.
- **Institutions** (`places` layers): `name`, plus the layer's `aliases` for that name (U of T, UIC…).
- **Skyscrapers** (the `towers` layer): `name` and `aka`. The website skips a tower when a landmark
  suggested for the same words stands within 20 m of it (Willis Tower, 875 North Michigan).

How the website's search does it, for an app that wants to match:

- Searched locally as you type: landmarks (name and `aliases`), the names in `fill` layers
  (former cities, Old Toronto areas, Chicago's sides), units, known-as names, neighbouring
  municipalities (`base.geojson` `neighbour` features), and `region_places` (name and `alt`).
- Matching ignores case, spacing and punctuation ("Yonge-St. Clair" finds "Yonge-St.Clair").
  An exact match ranks above a prefix match, which ranks above a match at the start of any word.
  At most 6 results.
- A result found through an alias shows its canonical `name`, with "also called {alias}"
  beneath. Choosing it titles the card with the canonical name.
- Streetcar and bus routes (`transit.json`): "{r} {n}" and the bare number `r`; choosing one
  draws the route and frames it (`b`). Sub-line: `card.transit.kinds[m]`, plus `nightOnly`.
- Street addresses are looked up only when the user presses Find, never as they type.

## 4. city.json: the parts an app uses

- `id`, `schema`, `title` (the full name, e.g. "Toronto · Layers.City"; it was "Toronto Layers" before October 12, 2026), `heading` (optional: the short name for headings and city pickers, e.g. "Toronto"; fall back to `title`), `locale` (`en-CA` or `en-US`, for number and date formatting).
- `unlisted` (optional, `true`): the city is published but not announced yet (Vancouver, October 2026): the other cities' switchers and the maps hub leave it out. An app can skip it.
- `inSwitcher` (optional, `true`, only meaningful with `unlisted`): the city does appear in every map's city switcher (Vancouver and Dallas, October 16, 2026), but is still left off the maps hub and the sitemap. An app that builds its own city picker can treat it like any other city.
- `distance` (optional): the unit for distances shown on the card, `"km"` (the default when absent; Toronto) or `"mi"` (Chicago). Config values such as `card.nearby.radius` stay in metres either way.
- `units.singular` / `units.plural`: what the city calls its units ("Neighbourhood",
  "community areas").
- `footprint`: the id of the layer that outlines the city. A point outside it gets the
  "outside the city" card.
- `groups`: `[[groupName, [layer, …]], …]`. Each layer has `id`, `kind`, `name`, `note`, and
  `file` (one file, add `.geojson`) or `files` (several). Kinds the card tests a point against:
  `fill`, `units`, `outline`, `patches`, `districts`, and `boards` (below). The `knownas` kind is a
  point layer used by distance (step 4 below). Other kinds are map drawing only.
- An `outline` layer may have `party` (`{table, key}`; Toronto `prov` and `fed`, Chicago `house` and `congress`,
  Dallas `house` and `senate`): each seat can be coloured by its sitting member's party, the member being
  `representatives.json[table][feature[key]]`. Top-level `party` (optional): `label` ("Colour by party"), `note`,
  `vacant`, `other`, and `parties` `[[label, colour, [names]]…]` matching the member's `party` string to a colour id
  (`red`, `blue`, `orange`, `green`; anything unmatched is `other`). A seat with no entry in the table is left clear;
  a seat whose entry is `null` is vacant. Apps may ignore it.
- An `outline` layer may have `election` (Toronto `wards`, for October 26, 2026): `{table, key, date, until, tick,
  note, head, when, counting, incumbent, retiring, open, running, elected, acclaimed}`. Until `until` (`YYYY-MM-DD`,
  when the new members take office), the web map offers an *Election view* for that layer: every seat in one
  neutral violet (palette `--elect*`), shaded the same way as party colours (one layer at a time, standing in for
  the fills and the lens) and ranked above them when several come on together. Each seat's label becomes `head`
  (e.g. "Ward 19"), and zoomed in also: `when` with `{date}` (or `counting` from election day, or `elected` /
  `acclaimed` with `{winner}`), `incumbent` or `retiring` with `{name}` (the card office on that layer and key; `retiring`
  when `incumbentRunning` is false; `open` if there's no member), and `running` with `{n}`/`{s}` until there's a
  winner. When the member is running in another race (`incumbentElsewhere`, section 8), `elsewhere[office]` replaces
  `retiring`, filled with `{name}` and `{ward}`. `also` (`{table, key, text}`) is one line under the view's tick for a
  race on the same ballot that isn't drawn (the mayoral race): `text` with `{n}`/`{s}` from
  `representatives.json[table][key].candidates`, hidden once that race has a winner. The race is
  `representatives.json[table][feature[key]]` (section 8). Apps may ignore it.
- A `boards` layer (`school` in every city: Toronto's file `school_wards`, Chicago's `school_board`, Dallas's `school`) holds several overlapping sets of
  wards in one file, one set per school board. Each feature has `board` (an id), `num` (the
  board's ward number, a string), `area` (a ward name, French boards only, e.g. "Est"), `wards`
  (the City wards it is made of) and `lp`. The layer's `boards` lists `[id, short, long]` per board
  in display order (`["tdsb", "TDSB", "Toronto District School Board"]`); the first is the one the
  map shows by default. Chicago has one board (`cps`, the Chicago Board of Education; `num` "1a" …
  "10b"), so there is nothing to pick. Templates on this layer can use `{short}` and `{long}` as well as the
  feature's fields.
- A `places` layer draws the points of `file` whose `cat` equals the layer's `cat` (several layers
  share `institutions.geojson`). `place` names the kind of place ("Hospital", "City College"),
  `edText` the extra hover words for a feature with `ed`, and `aliases` (optional, Colleges & universities)
  maps a feature `name` to the nicknames search should also match. Not part of the card.
- Schema 2: a `places` layer may instead have `cats` (`[[cat, chip label, singular noun], …]`; `campus`,
  `worship`, `food`): it draws every feature whose `cat` is one of them, and the web map shows a chip per
  category to hide or show it (any mix, at least one on; in the link as `cats=layer:cat+cat`). The singular noun
  replaces `place` for that category's features. `icon` names the glyph for the layer's row; `catNote` is a line
  under the chips; `replaces` (`{old layer id: cat}`) lets links made before the merge still work.
- A `places` layer may have `groups` (`[[id, label], …]`; the churches on `worship`): chips under its row, `allText`
  first, pick one group at a time; only features whose `grp` equals the pick are drawn (features with no `grp`
  show only under All). `countText` (`{n}`), `allNote` and `groupNote` make the line under the chips. With
  `groupsFor` (a category, `church`), the groups narrow only that category's features, and the chips show only
  while that category is; `groupLabel` heads them ("Churches by denomination").
- A `towers` layer (id `towers`, file `skyscrapers`) draws every feature of `skyscrapers.geojson`.
  Its text: `place` ("Skyscraper", search sub-line), `key` (`res`, `com`, `mix`, `uc`, `sup`: the
  legend shown under the layer while it's on), `purpose` (card wording per `purpose`, e.g.
  "Office tower"), `supText`, `ucText`, `builtText`, `expectedText`, `akaText` (`{aka}`),
  `moreText` (the Wikipedia link), `sourceText` (shown when a tower has no article). Card: section 5,
  step 5a.
- A `streetcars` layer (Toronto, id `tram`, file `streetcars`) draws its routes in `--tram`, each numbered
  along the line; stops (from `transit.json`, those served by a daytime streetcar) from zoom 15.
- A `heritage` layer (both cities, id `hbld`, file `heritage_buildings`, off by default, after Heritage districts): a small diamond per property in `--hd` from zoom 15 (`minZoom`; only those in view are drawn), its name from zoom 16. Tap: name (or address), `place` and type, address, `builtText` (`{y}`), `byText` (`{ar}`), `designatedText` (`{d}`), and Toronto's `bylawText` and `hcdText` rows. Named ones are in search.
- A `badges` layer (Toronto, id `badges`, file `badges.json`, `lazy`, on at first load, after Neighbourhoods; `align` names the street the drawings run parallel to): each drawing from `badges.json` centred on `c`, turned by `angle`, at `scale` (default 0.7) of `wm`, faint (`opacity`, default 0.45), above the street lines and below the unit outlines and every label. Shown once it is `minWidth` px wide (default 60), up to `maxWidth` px (220). Taps go through to the map.
- A `bikes` layer (Toronto and Chicago, id `bikes`, file `bikes`, `lazy`, off by default, after Bus routes): one line per segment above the area outlines, by class: `prot` solid `--bike`, `paint` thinner solid `--bike-2`, `shared` dashed `--bike-2`, `trail` solid `--bike-trail`; protected and painted lanes on a thin `--city` casing. `classes` (`{id: [short, long]}`, the panel's chips with a line key, any mix), `default` (classes drawn at first; both cities `["prot", "paint"]`; links write `bike=prot+paint+shared` when it differs), `legend`, `asofText` (`{date}` = `asof`), `betweenText`, `yearText`, `fine`. Tap a stretch: street (or type), type and class, between `fr` – `to`, installed `y`, the `fine` line. Views may set `bike` like `bus`.
- A `docks` layer (Toronto, id `bikeshare`, indented `under` Bike lanes, file `bikeshare`, `lazy`, `optional`, off by default): a small dot per station from zoom `minZoom` (12), filled `--city` with a `--dock` ring, filled `--bike` where it charges e-bikes; only stations near the view are drawn. `countNote` replaces the row's note once the file is in (`{n}` stations, `{system}`). Tap a station: name, `kindText` (`{system}`), `docksLabel` / `d`, `chargeLabel` / `chargeText` when `e`, `payLabel` / `noCardText` when `nc`, then `fine` (`{date}` = `asof`).
- A `changes` layer (both cities, id `chg`, file `changes`, `lazy`, `optional`, off by default): a dot per site coloured by stage (`--chg-1` proposed, `--chg-2` approved, `--chg-3` under construction, `--chg-4` finished), demolitions as dashed rings; `stages` (`{id: [short, long]}`, the panel's chips, any mix; links write `chg=proposed+approved` when not all are on), `kinds` (labels), `dates` (`applied`, `issued`, `finished` templates with `{date}`), `unitsText`, `alsoText`, `linkText`, `legend`. Tap a dot: kind, stage and date, address and homes, description, the other items on the site, the link.
- An `addresses` layer (both cities, id `addr`, indented `under` Main streets, off by default, file `addresses`):
  grid cities draw each `base` line bold and each `mile` line dashed in `--ag`, labelled once at its west
  (`ns`) or north (`ew`) end ("2400 N"; a base line "Madison St · 0"); divided cities draw the `divide`
  street bold in `--ag` and the `e` / `w` streets in `--ag-e` / `--ag-w`, with "West · Yonge St · East"
  marks along it (`westText`, `eastText`). Name in the panel: "Address grid" (Chicago), "Yonge: East and
  West" (Toronto).
- A `regional` layer (Toronto: id `gobus`, "GO buses", indented `under` the GO trains; Chicago: id `pace`, "Pace buses",
  under Metra; file `transit_routes`, `lazy: true`) draws another agency's routes, those with `m` equal to the layer's
  `mode` (`go`, `pace`), in that mode's colour (`--gobus`, `--pace` in `city.css`), numbered like the others ("GO 41", "Pace 270"). Regional view: every route.
  City view: only routes with `in: true`, numbered mid-way along their stretch inside the city, and drawn
  under the city mask so the rest fades with the region. Stops (those served by the mode) from `stopZoom`
  (12); in the city view only those inside it. Off by default. Tapping a route shows it alone, as below.
- A `buses` layer (id `bus`, file `transit_routes`, `lazy: true`: load it only when needed) draws the
  routes in the families picked (only `m` `bus` and `tram`): `families` lists `[id, short, note]` (`freq`, `exp`, `reg`, `night`), the
  first being the default. Any mix may be on except the ids in `solo` (`["night"]`), which show alone.
  `allText` labels a chip that turns every non-solo family on (`allNote` is the note then); `default`
  (`"all"` or a family id) is what the layer starts with, both cities `"all"`; tapping one
  family while all are on narrows to that one. When a
  city has a `streetcars` layer, daytime streetcar routes (`m: "tram"`, `day: true`) are left to that
  layer; streetcars that run only overnight show in `night`. Routes are drawn in their mode's colour
  (`--bus`, `--tram`); with more than one family on, routes in `exp` are dashed (`comboText` says so).
  Toronto and Chicago style buses after their agency (city.css, website only): Toronto streetcar badges red
  with white numbers, bus badges white with a red outline, `exp` green, overnight (`night`, or any route
  while the overnight family shows) white with a blue outline; bus lines charcoal, `exp` green and dashed
  when mixed, overnight blue. Chicago (the CTA's bus map legend): local badges dark grey, `exp` red, X routes
  white with a green outline (green lines), Jump routes blue, Owl white with a blue outline (blue lines).
  In both, `freq` routes are drawn with a heavier line than the rest. Optional `card.transit.routeClasses`
  `[[pattern, class]]` (Chicago `[["^X", "xr"], ["^J", "jump"]]`) names extra route types by a regular
  expression on `r`; an app may ignore it or use it for its own styling.
  Stops from zoom 15. Text: `countText` (`{n}` routes), `hint`, `pickText`, `unpickText` (`{r}`),
  `clearText`. The website's links write the families as `bus=freq+exp`, or `bus=all`. Tapping a route's line or number badge shows that route
  alone (the rest of the route layers fade to 12% and their badges hide; only its stops show); the next tap
  anywhere else, or Escape, brings them back without opening the card. Not kept in links. Any route can also
  be picked (from the card, search or a link) and is then drawn in `--ink` over a `--city` casing with
  its stops, whichever layers are on.
- `under` (optional, any layer): the id of the layer it sits under in the panel (the institution
  toggles and Skyscrapers are `under: "landmarks"`). Indented in the panel; each still has its own
  toggle and default, all off.
- `live` (optional, any layer; October 14, 2026): `true` for layers refreshed from city feeds every day or
  week (Toronto and Chicago: `chg`, `build`, `closures`). The website's panel has three tabs, All, Basic
  (layers without `live`) and Live, which only filter the list; layers that are on stay on. `staleDays`
  (optional, default 3): a layer whose data `asof` is older than that many days shows its date in `--accent`.
  The freshness line ("As of Oct 14") comes from the layer file's `asof` (`closures.geojson`,
  `changes.geojson`) filled into `asofText` (default "as of {date}"). Optional top-level `panelTabs`
  (`all`, `basic`, `live`, `liveNote`) overrides the tab text. Apps may ignore all of it.
- `directions` (optional; October 14, 2026): text for the website's directions buttons (`title`, `google`,
  `apple`, `pick`). Website only: it links to Google Maps or Apple Maps directions to a place's coordinates.
  Apps may ignore it.
- `card`: `pills`, `facts`, `living`, `reps` (section 6).
- `card.appLocal` (added October 21, 2026; Toronto and Chicago `wards`, Dallas and New York `council`): the
  `reps` office `table` that is the spot's local representative, for the app's line under the title and its
  representative tile (New York's first office with a layer is the borough president). Absent (Vancouver,
  whose council is elected citywide): no local representative line.
- `card.appTitle` (Dallas and New York, October 21, 2026): `{"knownas": 650}`: when a known-as point is within that
  many metres, the app titles the spot with the nearest one's name ("Uptown") and moves the unit's name to
  the line beneath ("ZIP 75204"); otherwise the unit's name is the title. Dallas's units are ZIP codes.
  New York (October 21, 2026): `{"layer": "nta"}`: the app titles the spot with the name of the feature of that
  layer containing it (the neighborhood tabulation area, "East Village") and moves the community district's name
  beneath ("Lower East Side & Chinatown"); outside every feature, the unit's name is the title.
- `lens.file` (the profiles file) and `lens.lenses`: each has `key` (the profile field holding a
  tier id) and `tiers: [[tierId, label, colourVariable], …]`. Use the label; the colour variable
  resolves through `palette`.
- `hubs` (optional, since October 30, 2026; on the lens that has `minutes`): the trip-to-the-centre lens can end at
  more than one hub. `[{id, name, short, key, minutes, note, filter}]`, the default first; the lens's own `key`,
  `minutes`, `short` and `note` repeat the default. `name` labels the choice ("Grand Central"), `short` the lens
  ("To Grand Central"), `filter` the "Narrow it down" row; `key` and `minutes` name that hub's profile fields. All hubs
  share the lens's `tiers`. `lens.hubLabel` ("Trip to") heads the choice. The website remembers the viewer's pick and
  carries it in the link (`hub=gct`); an app may offer the same choice or show the default only.
- `lens.filters` (the website's "Narrow it down" rows): `{lens, label, options}` picks tiers of that lens;
  `max: true` is a minutes ceiling; `top: true` (Most common home, on the `homes` lens) has no `options`
  of its own: its choices are the lens's `pick` ids, and a unit matches when its largest share in the
  lens's `field` list is a picked one.
- `palette`: every colour the website uses, keyed by its CSS variable name with the leading `--`
  (`"--bia": {"light": "#E0791A", "dark": "#F39A45"}`). Every colour reference elsewhere in
  `city.json` (a fill layer's `colors`, a pill's `color`, a lens tier) is a key here. Only the
  published copy has it; the website builds it from its stylesheets. Use it rather than copying
  hex values into the app, so a colour change on the website reaches the app with the data.
  `--accent` is the brand red (pins, buttons, the card's tinted boxes). `--accent-2`, when present, is
  the colour for controls such as layer toggles (Chicago: blue, for red, white and blue); when it's
  absent, use `--accent` (Canadian cities are red and white).
- `drive`: `hub` (`[lat, lon]`) and `hubName` ("Union Station", "State & Madison").
- `outside`: `beyond` (message when the point is outside the whole region), `regionPill`
  (template for the region name), `note` (shown on outside cards), and optionally `muniLabel` (added
  October 30, 2026; Hyderabad only): what an area beyond the city is called on its card ("Mandal");
  absent means "Municipality".
  Apps use `appBeyond` and `appNote` instead (added October 21, 2026; every city): the same messages
  without references to the web map's layers. In general, a key starting with `app` is the app's
  wording of the website text beside it; prefer it when present.
- `regionPlaces` (Toronto only): `file`, and `near`, the place kinds used for a "Near …" pill.
- `attribution`.

Pill colours on the card: a `{"layer": A, "else": B}` pill takes the colour of whichever layer
matched, from that layer's `colors[name]`; a `{"layer", "text", "color"}` pill uses its `color`;
a known-as pill is `--cult-enclave`; anything without a colour is `--ink-3`. Outside the city:
"Near …" is `--cult-enclave`, the municipality `--land-out-line`, the region `--muni-label`.
Pill background `--pill-bg`, text `--ink`.

### Text templates

Card text in `city.json` is a template, filled from a feature's properties:

- `{name}` inserts a field. `{f.num}` and `{r.party}` walk into nested objects (`f` = the feature's
  properties, `r` = the representative record).
- A list value becomes `a, b`.
- A part in `[square brackets]` is dropped if any field inside it is missing or empty. A missing
  field outside brackets blanks the whole text (the row then shows its `empty` text, or `—`).

Example: `"{name}[ (designated {since})]"` gives "Cabbagetown South (designated 2005)", or just the
name when `since` is missing.

### `transit` (October 28, 2026)

Where a city's transit stops, routes and live arrivals are, with the wording settings and route badge colours:
section 15. Only Toronto has it so far.

## 5. Building the "What's here" card for a coordinate

Point-in-polygon: even-odd ray casting on each ring; a point is inside a polygon if it is inside
the outer ring and not inside any hole; inside a MultiPolygon if inside any of its polygons. The
first matching feature in file order wins.

1. **Load** `city.json`, then every file the layers name, the profiles file, `representatives.json`,
   and (if present) `drive_grid.json` and `region_places.json`.
2. **Inside the city?** Test the point against the `footprint` layer.
   - **No:** find the `base.geojson` feature with `kind: "neighbour"` that contains the point.
     - None found: show `outside.beyond`. Done.
     - Found: title is the municipality `name`. Pills: "Near {place}" (Toronto: the nearest
       `region_places` entry whose `kind` is in `regionPlaces.near`, within 2.5 km, skipped if it
       is already the title), the municipality name, and `outside.regionPill` filled with
       `{region}`. Then the drive row (section 6) and `outside.note`. Done.
   - **Yes:** carry on.
3. **Hits.** For every layer whose kind is `fill`, `units`, `outline`, `patches` or `districts`,
   find the feature containing the point. Store as `hits[layerId]` (may be empty). For a `boards`
   layer, find one feature per board instead: `hits[layerId][board]`.
4. **Known-as names.** From the `knownas`-kind layer (points), take those within 650 m, nearest
   first, at most N, where N is the `knownas` number in the pill config (`{"knownas": 2}`).
5. **Pills** (`card.pills`, in order):
   - `{"knownas": N}`: one pill per known-as name from step 4.
   - `{"layer": A, "else": B}`: the name of `hits[A]`, or if none, of `hits[B]`.
   - `{"layer": A, "text": T}`: `T` filled from `hits[A]`, only if there is a hit.
5a. **Tower** (only when the card has a title, from a tap on a tower, a search or a shared link):
   the `skyscrapers.geojson` feature whose `name` or `aka` equals the title within 150 m, or else
   any tower within 20 m (a landmark inside a tower, e.g. the Lyric Opera in the Civic Opera
   House). If found, a block under the pills: the `towers` layer's `purpose` word, `supText` when
   `super`, `ucText` when `uc`; Height (Toronto: "298.3 m" over "979 ft"; Chicago, `distance` "mi":
   feet first), Floors, and `builtText` or `expectedText` with `year` ("TBD" when null); the
   `facts` as a list; `akaText` and a link to `https://en.wikipedia.org/wiki/{wiki}` labelled
   `moreText`.
6. **Boundaries** (`card.facts`, in order), each a label and a value:
   - Skip a row with `onlyInside: true` unless its layer has a hit.
   - `knownas: true`: the known-as names from step 4, comma-separated, or `—`.
   - `boards: layerId`: for each board in that layer's `boards` order that has a hit, `text` filled
     from the hit plus `{short}`/`{long}`, joined with " · " ("TDSB 7 · TCDSB 9 · Viamonde 3 ·
     MonAvenir 3"); `—` if none.
   - Hit: `text` filled from the hit.
   - No hit: if `emptyWithin` is `{layerId: name}` and that layer's hit has that name, `—`;
     otherwise `empty`, or `—`.
   - `cover` (Toronto's Permit parking row): a second line under the value, from the spot's unit's
     profile field `cover.field` (a percentage): `cover.text` with `{pct}` and `{name}` (the unit's name), or
     `cover.none` when the figure is 0. No second line when the unit has no profile or no figure.
7. **Standout** (optional line under the pills): if the unit's profile has `facts`, show the first
   one as "{profile name}: {text, first letter lower-cased}" followed by its `value` in smaller
   type. Section 7.
8. **Living here**: look up the profile by `hits[unitsLayerId].properties.code` (as a string key).
   Section 7.
9. **Representatives** (`card.reps.offices`, in order). Skip the whole section if the first
   office's layer has no hit. For each office: `h = hits[office.layer]`, or, when the office has `file`
   (Dallas's U.S. representative: `us_house_2021`), the feature of that file containing the point (the file
   is loaded for this row only and never drawn: the districts sitting members were elected on, before new
   lines take effect);
   `r = representatives[office.table][String(h.properties[office.key])]`. Row label `role`;
   value `r.name` linking to `r.url` (no record or no name: "Seat currently vacant"); subline
   `office.sub` filled with `{f: h.properties, r: r}`. Footer `card.reps.note` with `{date}` =
   `representatives.updated` written as a long date.
   **Trustees** (`card.reps.trustees`, after the offices): skip if
   `representatives[trustees.table]` is missing. For each board of layer `trustees.layer` with a
   hit `h` (in `boards` order): `r = representatives.trustees[board][h.num]`; label `role` filled
   from `h` plus `{short}`; `ward` = `trustees.ward` filled the same way. Value, by date (dates are
   `trustees.election` and `trustees.starts`, `YYYY-MM-DD`, Toronto time):
   - `r.winner` and today ≥ `starts`: the winner's name; subline `ward`.
   - `r.winner` before `starts`: the name; subline `ward` · `acclaimed` (if `r.acclaimed`) or
     `elected`, filled with `{election}` and `{starts}` as short dates ("Oct 26").
   - No winner but `r.leader` and the config has `leading` (Chicago): the leader's name; subline
     `ward` · `leading`.
   - Otherwise: `race` (before `election`) or `counting` (from `election` on), filled with
     `{n}` = number of candidates, `{s}` = "s" unless n is 1 (templates write `candidate[{s}]`) and
     the dates; the candidate names (`r.candidates`, ballot order) on expand; subline `ward`.
   Then, if `trustees.citywide` is set ({board, key, role, sub}) and at least one board row was
   shown: one more row, label `role`, record `representatives.trustees[board][key]` (Chicago's
   board president), subline `sub`, same rules.
   Names are plain text (no official page yet). Append `trustees.note` to the footer.
   **Citywide offices** (`office.citywide`, Toronto's mayor: `{role: "Mayor", citywide: "city", table: "mayor", sub:
   "Citywide"}`): no layer; the record is `representatives[table][citywide]`, shown wherever the section shows, in
   config order (Toronto lists the mayor first). The section's skip test uses the first office that has a layer.
   **Races on an office** (`office.race`, Toronto's mayor and city councillor: `{table, again?, retiring?, elsewhere?}`): when
   `representatives[race.table]` has a record for the seat and today is before `trustees.starts`, the row keeps the
   sitting member (name and link as usual), adds " · " and where they stand to the subline (`again` when
   `incumbentRunning` is true; when false, `elsewhere[incumbentElsewhere.office]` filled with its `{ward}`, else
   `retiring`), then under it, with the trustees' wording and dates: the winner and `acclaimed` or
   `elected` once there is one, otherwise `race`/`counting` with the candidate names on expand. From `starts` on,
   the plain office row.
   **Partisan ballots** (`card.reps.ballot`, Chicago, Dallas and New York for November 3, 2026): `{election, through, race, one,
   again, retiring, notUp, elsewhere {congress, house, senate, statewide}, races {key: label}, party {name: short},
   note}`, overriding the trustees' wording for `race` rows. Rows show the race until the end of `through` (election
   day; there is no results feed), then go back to the plain office row. An office's `race` may name `kind`
   (congress, house, senate), `layer` and `key` (the race keyed by another layer than the member: Dallas's members
   sit for the 2021 congressional lines, the race is on the new lines the map draws) and `text` (wording overrides;
   `{district}` is the race's key). Where the member stands comes from the member's `runs` (section 8): `again` when it
   is this race, `elsewhere[runs.office]` filled with `{district}` or `{race}` (`races[runs.race]`) when another,
   `retiring` when `null`. A race `{notUp: true}` adds " · " and `notUp` to the subline and no caret. Candidates show as
   "Name (short party)" in ballot order; a race with one candidate is a line, `one` with `{name}`. An office with
   `ballot: {table, key}` (U.S. Senate, Governor) is a race with no member, shown after the trustee rows while the race
   is, with subline `sub`. `ballot.note` is added to the footer until then.
   A list of more than 8 names is laid out as a grid, one name per cell, across the card's full width when open.
   While the web map's election view is on, the card opens with only the Representatives section expanded, and
   moved to the top of the sections.
   **Nearby** (`card.nearby`, both cities): for each `[key, label]` in `nearest` (or `[key, label, layer]`:
   then only while the layer with that id is on; `layer` may be `"layer:cat"` (schema 2: `"worship:mosque"`), then
   only while that layer is on with that category shown. If that layer has a
   group picked (and, with `groupsFor`, the row is that category), use `nearby.groups["key:group"]` and add " · " and the group's label to the row label), the nearest point
   of `nearby.groups[key]` by straight-line distance: row `label`, value its name, subline the
   distance ("600 m away"; to the nearest 50 m under a kilometre, then "1.8 km". With `distance`
   `"mi"`: "250 ft away" to the nearest 50 ft under 0.1 mile, then "0.4 mi", whole miles from 10). Then one row,
   label `within`, value the count of points of each `[key, one, many]` in `counts` within
   `radius` metres, "19 parks · 7 playgrounds …" (`one` when the count is 1). Footer `note`, always
   shown. `sources` (added October 20, 2026; every city): one line naming the section's sources, with no
   reference to map layers, for apps whose footer can't use `note` (which mentions the web map's layers). Counts only: never a score, ranking or "best". The website shows this section between
   Schools and Representatives.
   **Schools** (`card.schools`, Chicago and New York): load `card.schools.file` (`attendance.geojson`). For
   each `[level, label]` in `levels`, the feature of that `level` containing the coordinate: row
   `label`, value its `name` (linked to `url` when set), subline `sub` filled with `{grades}` and
   `{dist}` (straight-line distance to `[x, y]`, same format as Nearby), or `subNoDist` when the
   feature has no `x`. Levels with no hit are skipped (most of the city has no middle-school row).
   Footer `note` with `{year}` from the file. Section title `title`. No hits at all: no section.
   The website shows it between Living here and Nearby, and loads the file after the map is up.
   **Where to vote** (`card.vote`, optional; Toronto with places, Chicago precincts only): only while the current time is before
   `closes` (an ISO time with offset, when the polls close on `date`). Load `card.vote.file`
   (`voting.geojson`) and take the subdivision containing the coordinate; none: show nothing. The website
   shows a tinted box with a ballot-box icon right under the pills: a heading `title` filled with `{date}`
   (or `today` when it is `date` in `tz`), then `hours`; `lead`; the place's `n` (when present) and `a` with
   the straight-line distance to `[x, y]`; `entrance`, `access` (filled from `e`, `ae`) and `vat` when they
   apply; a `show` button framing the spot and the place, a link `link` [text, url] to the City's MyVote;
   footer `note` filled with `{ward}` (`w`), `{sub}` (the subdivision number without leading zeros) and
   `{asof}`. It also draws a ballot-box mark at the place. A feature without `x` (Chicago) has no place:
   after `lead`, show `precinct` filled with `{ward}` and `{precinct}` (`p`), subline `precinctSub`, and the
   `link` as the only action; no mark. Not part of Compare. Once `closes` has passed,
   don't load the file or show anything.
   *Vote centers* (Dallas and Chicago, when `card.vote.counties` is set; Chicago's leads and `note` are also filled
   with `{ward}` and `{precinct}`): a feature with `k` (a county key in `counties`)
   is a whole county where a registered voter can vote at any vote center. The phase comes from `early`
   ({from, to}) and today in `tz`: before `from` the heading is `early.soon`, from `from` to `to` it is
   `early.title` (both filled with `{from}`, `{to}`), with `early.hours`; after `to`, `title`/`hours` as above.
   Then `earlyLead` (before and during early voting) or `centersLead`, filled with `{county}` (the county's
   `name`), and the 3 nearest entries of the file's top-level `centers` ([x, y, name, room, address, county
   key, kind]; kind 1 election day, 2 early voting, 3 both) of that county and the phase's kind, each with its
   straight-line distance; then `earlyMore` / `centersMore` filled with `{n}`, `{ed}` and `{county}` from the
   top-level `counts` ({county: {ed, ev}}). The link is the county's `link`. Marks at the listed places;
   `show` frames the spot and them. A county with `precinct: true` (Denton) has one feature per precinct
   (`k`, `c` precinct, and `n`, `a`, `r` room, `x`, `y` for its election day polling place): on election day
   (after `early.to`) show it as a place, with footer `precinctNote` (`{precinct}`, `{county}`, `{asof}`);
   before, list its early voting sites as above and add `precinctEarly` filled with `{n}`. Footer `note`
   with `{county}` and `{asof}`. The website also shows the box on cards outside the city (the counties
   cover the suburbs).
   **Districts beyond the city** (`card.outsideFacts`, optional; Dallas): layer ids whose files cover the region,
   not just the city (Dallas's `tx_house`, `tx_senate`, `us_house`: the nine counties). On a card for a spot
   outside the city, add those layers' `card.facts` rows after Municipality and County, and their `card.pills`
   entries that have `text`. The website shows them in a Boundaries section on the outside card.
   **Transit nearby** (`card.transit`, both cities): load `card.transit.file` (`transit.json`). Rows:
   - `station`: the nearest station of the `metro`-kind layer (its second file: `subway_stations` /
     `cta_stations`), skipped beyond 5 km; value its name, subline `stationSub` filled with `{lines}`
     and `{dist}`.
   - For each `[mode, label, named]` in `rows`: the routes of that `m` with `day: true` that have a stop
     within `radius` metres, nearest stop first; each shown as its number (`named`: number and name,
     "501 Queen"). A route in family `freq` is marked (filled by default; a double ring in Toronto and Chicago, whose
     chips follow the map's badge styles); the note says so.
     Toronto has a third row, `["go", "GO buses", false]`: GO routes with a stop within `radius`; Chicago a second,
     `["pace", "Pace buses", false]`.
   - `night`: routes in family `night` with a stop within `radius` (Toronto's 300-series, Chicago's
     overnight routes), numbers only.
   - `stop`: the nearest stop's name and distance, or `none` when there is no stop within `radius`.
   - `bikeshare` (optional; Toronto): load the `docks` layer's file (`bikeshare.geojson`) too. Row `label` ("Bike Share"): the nearest station within `bikeshare.radius` metres (500), its `n`, subline `sub` filled with `{dist}` and `{docks}` (`d`), then " · " and `charge` when `e`; else `none`.
   Footer `note` with `{week}` (from `transit.json`, a short date). Hover/tooltip text for a route:
   "{r} {n}" plus `every` filled with `{h}`, plus `nightOnly` when `day` is false. `kinds` names a
   route's mode for search ("Bus route"). The website shows the section between Schools and Nearby;
   each number is a button that draws the route on the map. Describe only: no scores.
10. **Title**: the searched place's name if there is one. Otherwise (a dropped pin): the name of
   `hits[unitsLayerId]` (the neighbourhood / community area); failing that, the first `fill`-kind
   layer's hit; coordinates (`43.6681° N, 79.3669° W`) only for a spot no layer covers.
   The standout line (step 7) drops its "{profile name}: " prefix when the title is that name.

The website shows the standout line under the pills, then four collapsible sections in this
order: Boundaries, Living here, Schools (Chicago), Transit nearby, Nearby, Representatives.

### Worked example (Toronto, 43.66810, -79.36690)

Computed from the October 8, 2026 data. Use it as a first test case.

- **Pills:** Downtown · Cabbagetown · St. James Town · Votes in Toronto Centre (no BIA here).
- **Boundaries:** Former city: Old Toronto · Area: Downtown · Neighbourhood:
  Cabbagetown-South St.James Town (#71) · Known as: Cabbagetown, St. James Town (263 m and
  609 m away) · Heritage district: Cabbagetown (Metcalfe) (designated 2002) · BIA: None ·
  City ward: Ward 13 · Toronto Centre · Provincial: Toronto Centre · Federal: Toronto Centre ·
  School wards: TDSB 7 · TCDSB 9 · Viamonde 3 · MonAvenir 3.
- **Living here** (profile `"71"`): Housing: Middle housing cost, median home $950K · renters
  pay $1,330/mo · To Union: 30–45 min, about 32 min by transit · Getting to work: Mostly transit,
  walk or bike, 31% drive · 27% transit · 38% walk or bike · Households: A mix, 55% rent ·
  Home types: Detached 3% · Semi & row 18% · Low-rise 28% · Towers 52% · Built: 1960 or before
  41% · 1961–80 27% · 1981–2000 23% · 2001–21 9% · Language at home: English 84%, no other
  language above 5%, "Another 3% name two or more equally."
- **Representatives:** read from `representatives.json` (`wards["13"]`, `prov["Toronto Centre"]`,
  `fed["Toronto Centre"]`), then trustees from `trustees.tdsb["7"]`, `trustees.tcdsb["9"]`,
  `trustees.viamonde["3"]`, `trustees.monavenir["3"]`.

Note the unit's map name (`Cabbagetown-South St.James Town`) and its profile `name`
(`Cabbagetown-South St. James Town`) differ slightly; the Neighbourhood row uses the map's, the
Living here footer the profile's. The live page,
`https://layers.city/toronto/#pin=43.66810,-79.36690`, shows the same card; if they ever
disagree, the live page is right.

**Tour** (`tour` in `city.json`, optional): `invite`, `start`, `stepText` (`{n}`, `{of}`), `next`, `back`, `done`, `closeText`, `dismissText`, and `steps`: `[{title, text, layers, hi, scope, view, pin}]`. `layers` is the exact set of layer ids on for the step, `hi` the ones to point out, `scope` `inner` (default) or `outer`, `view` `"city"`, `"region"` or bounds `[[south, west], [north, east]]`, `pin` (present: open the card at the city's `example`, or `{at, name}`). The website restores the map as it was when the tour ends. Apps may ignore it.

**Views** (`presets` in `city.json`, optional): named views shown as a dropdown at the top of the website's panel. `label`, `placeholder` (optional, the dropdown's text before a view is picked), `customText`, `customFrom` (optional, `{name}`; the dropdown reads `customText (customFrom)`) and `customNote` (`{name}`: shown once someone changes the map after picking a view), `boundaryLabel`, `electionText` (`{label}`), `window` (days, default 180), `items` and `elections`. Each item: `{id, name, note, layers, lens, bus, scope, view, boundaries, lead, hint}`. A view replaces the whole state: exactly `layers` on (sub-toggles such as `stnNames` included), `lens` (else the first lens), `bus` families (else the layer's default), `scope` `inner` (default) or `outer`, no filters, picks, focus or card, then `view` (`"city"`, `"region"` or bounds). `boundaries` (Who represents me) is a list of boundary layer ids shown one at a time with chips to switch; the first one on is the `lead` of the earliest `elections` entry `{date, lead, label}` dated today or later and within `window` days, else the item's `lead`. `hint` is text for under the search box while no spot is pinned. Ids are the same in every city (`explore`, `local`, `civic`, `newcomer`, `transit`); links carry `preset=<id>`. Apps may ignore it.

**Heritage building row** (`{"label": "Heritage building", "heritageBuilding": true}` in `card.facts`, after the heritage district row): the property within 40 m of the spot (150 m when the pin's name matches the property's), nearest first, shown as its name (or address) with "(built 1901, designated 1976)"; no row when there is none.

**Pickup row** (`card.pickup`, a Boundaries row placed by `{"label", "pickup": true}` in `card.facts`; Toronto "Collection day" after Address, Chicago "Street sweeping" after Address grid; October 14, 2026): find the feature of `file` containing the spot. None: show `outside` if set (Toronto: not on curbside routes), else no row. Otherwise take its `sched` dates on or after today in `tz`; none left: `after` with `{year}` if set (Toronto), else no row (Chicago, out of season). With `group`, dates within 4 days of each other are one visit ("Oct 30 and Nov 2"). The row: `head` filled with `{day}` (the weekday most of the area's dates fall on) and the feature's properties (Chicago "Ward {w}, section {s}"), then the next `show` visits each as `next` ("{when}: {items}"; `{when}` is "Today", "Tomorrow" or "Thu, Oct 15", `{items}` the `items` labels joined, first letter capitalised), then `note` with `{year}`.

**Address row, by each street's own start** (`card.address.origins`; San Francisco, October 31, 2026, which has no
citywide grid): `dir` names a folder of squares like the street sweeping row's (`<i>_<j>.json`, `cell` 0.005°), each
`{s: [[street, starts at (cross street, or ""), rises toward (north, northeast…, or "" for a short street), lowest
hundred], …], p: [[street index, lon, lat, number], …]}` (address points about 30 m apart). Take the point nearest
the spot within `within` metres (none: no row). The row: `text` with `{street}` and `{block}` (the point's number
rounded down to the hundred; `textLow` under 100), then, when there's a `toward`, `riseFrom` (lowest hundred 100 or
more and a cross street: `{low}`, `{from}`, `{toward}`), else `rise` (`{from}`, `{toward}`), else `riseNoFrom`,
then `sub`.

**Street sweeping row** (`card.sweep`, a Boundaries row placed by `{"label", "sweep": true}` in `card.facts`; San
Francisco, October 31, 2026): `dir` names a folder of squares, `<i>_<j>.json` with i = floor(lon / `cell`) and j =
floor(lat / `cell`) (`cell` 0.005°, about 450 m); fetch the square holding the spot. Each square is
`{s: [street names], l: [block limits], f: [[street index, limits index, side, [[weekday 0–6 from Monday, from hour,
to hour, weeks of the month as bits: 1 = 1st week … 16 = 5th], …], [lon, lat, lon, lat, …]], …]}`; a block side is in
every square its line comes within about 40 m of, so one square is enough. Take the block side whose line is
nearest the spot, within `within` metres (none: no row), and the other sides of the same street and limits. The row:
the street, the limits in brackets, then a line per side, "<side> <days> <hours>[, <weeks>] · next <when>" (days
with the same hours and weeks together: "Every day", "Weekdays", "Mon–Fri", "Mon, Wed & Fri"; hours "2–6 am",
"10 am–noon"; weeks omitted when every week, else "1st & 3rd weeks"; the week of the month is ceil(day / 7); `when`
"today" while today's sweep hasn't ended in `tz`, "tomorrow", or "Tue, Nov 3"), then `note`. Source: `source`.

**Pickup in apps** (added October 21, 2026; Toronto, Chicago, Dallas, New York): `appTitle` (the reminder's title: "Pickup tomorrow", Chicago "Move your car"), `appReminder` (its body, with `{items}` as in `next`; Chicago's has none, a sweep has one item), and where `outside` exists, `appOutsideHead` and `appOutside` (a short tile heading and line, "Private pickup" / "Building or area has its own collection"; the full `outside` stays for a detail view). A reminder goes out the evening before each date in `sched` (for `group`, before each visit's first date). Vancouver has no pickup file: no row, no reminder.

**Road closures** (`card.closures`, section `cls`, before Changing nearby; Toronto and Chicago; October 14, 2026): from the `closures` layer's file whatever the layer's toggle, only when at least one is within `radius` m (Toronto 500, Chicago 805) of the spot; otherwise the section is left out. Hide permits whose `end` is before today in the layer's `tz`. Distance to the nearest point of the line. Nearest first (a `closed` before a `narrowed` at the same distance), at most `max` (4): the layer's `closedText` or `narrowedText` with a red line or amber dots key · `street` · a line of `startsText` (permits starting later), `untilText` (with the year and `longText` when two or more years out), hours (`allDayText` for "24h"), the project `name` and the distance · `extent` when it differs from `street`. More than `max`: `more` with `{n}`. Footer `note` with `{date}` = the file's `asof`. Permit dates, never a reopening forecast.

**Changing nearby** (`card.changes`, section `chg`, after Nearby): sites within `radius` m (Toronto 500, Chicago 805), nearest first, at most `max` (6): kind with a stage dot (ring for demolitions) · address · stage, date (`dates[dl]`) and distance · the description cut to about 110 characters · the link. More than `max`: `more` with `{n}`. None: `none`. Footer `note` with `{date}` = `asof`.

**Address row** (`card.address`; a Boundaries row placed by `{"label", "address": true}` in `card.facts`): grid cities show `grid` filled with `{ns}` and `{ew}`, the spot's numbers read off `axes` and rounded to the nearest 100 ("About 2400 N · 1200 W"; 0 shows as "0"), then `sub`. With `within`, first check the spot is in `within.name` on layer `within.layer`; if not, show `within.elsewhere[that name]` (plain text) or no row. Divided cities show `east` or `west` (which side of the `divide` street the spot is: its longitude at the spot's latitude, or at its nearest stretch), then `sub` with `{street}`: the nearest `e`/`w` street on that side within about 1.5 km, or `example[side]`.

**Compare two places** (website, since 1.1): the same card for two spots, merged row by row. Each
section's rows are lined up by label (the first place's order, then any the second place alone has);
the label sits above the two values, A then B, with "—" where a place has no row. Caveats and
footer notes show once per section. Spots outside the city contribute Municipality and region rows
(Boundaries) and the drive-time row (Living here). Nothing is ranked or highlighted. Links:
`pin`/`name` for A, `pin2`/`name2` for B.

**Report a problem** (`card.report`, all cities, October 14, 2026; optional, apps may ignore it): a link at the foot of the card opening a small box: a pick of `kinds` (what's wrong), an "include this place" checkbox (unticked by default) and a `mailto:` link to `to` (go@layers.city) with `subject` (`{city}`, `{kind}`) and a body of `body`, then, only when the box is ticked, `placeText` with `{name}` and `{link}` (a map link with the pin), then `footer`. Every text key has an engine default; a city's config sets `to` and may override any of them (Chicago's `kinds` say "street closure"). The report goes from the person's own email app; nothing is sent by the page.

## 6. Drive time (outside the city only)

`drive_grid.json`: `{hub, date, spacing_km, points: [[lon, lat, minutes], …]}`. Take the nearest
point; if it is more than 2 km away, show nothing. Row: "Drive to {hubName}: about {minutes} min
from here", plus "Typical for {municipality}: {drive} min" from the `base.geojson` feature's
`drive` (skip if missing or if the feature has `rest: true`). Always show the caveat: "With no
traffic, at posted speeds. Most trips take longer." Tiers: under 30, 30–60, 60–90, 90+ minutes.

## 7. Profiles (Living here)

Keyed by unit code as a string (`"71"`). Fields:

| Field | Meaning |
|---|---|
| `name` | Unit name. |
| `value` | Median home value, dollars. Shown as `$800K`, `$1.2M`. |
| `rent` | Median monthly rent paid by renting households, utilities included (Canada: shelter cost of rented dwellings; Chicago: ACS gross rent). Counts every renter, long-time and subsidized included, so it runs below new-lease rents. |
| `renterPct`, `carPct`, `transitPct`, `walkBikePct` | Whole-number percentages. |
| `pop`, `hh` | Optional, since October 19, 2026. The unit's population and private households from the same census or survey, as weights for citywide figures (the site's Compare page). Not shown on the card. |
| `cost`, `commute`, `tenure` | Tier ids; labels come from `lens.lenses` (match `key`). |
| `union`, `unionBand` | Toronto only: transit minutes to Union, weekday 8–9 am, and its tier. |
| `bloor`, `bloorBand` | Toronto only, since October 30, 2026: the same to Bloor-Yonge station, the transit lens's second hub. Same tier ids as `unionBand`. |
| `loop`, `loopBand` | Chicago only: transit minutes to the Loop (quickest of five Loop arrival points), weekday 8–9 am, and its tier. Same tier ids as `unionBand`. |
| `downtown`, `downtownBand` | Dallas only: transit minutes to downtown (quickest of Akard, St. Paul, West End and EBJ Union Station), weekday 8–9 am, median over the ZIP, and its tier. Same tier ids as `unionBand`. Where fewer than half the ZIP's points reach downtown within three hours, `downtown` is null and the band is `over60`. |
| `penn`, `pennBand`, `gct`, `gctBand` | New York only: transit minutes to Penn Station and to Grand Central (42 St), weekday 8–9 am, median over the community district, and their tiers. Same tier ids as `unionBand`. |
| `montgomery`, `montgomeryBand`, `missionbay`, `missionbayBand` | San Francisco only (unlisted): transit minutes to Montgomery St station and to 4th & King (Mission Bay), weekday 8–9 am, median over the neighborhood, and their tiers. Same tier ids as `unionBand`. |
| `homes` | 4 shares (%) of home types, in the order of `card.living.homes.types`. |
| `built` | 4 shares (%) by period built, in the order of `card.living.built.bands`. |
| `lang` | Up to 5 `[language, pct]`, largest first. Demographic: card only. |
| `langMulti` | Toronto only: % naming two or more languages equally. |
| `canopy`, `canopyBand` | Tree canopy: % of the unit's land under tree cover (water left out), from ESA WorldCover 2021 (10 m), and its band `c1`–`c4` (cuts in `cities/<city>/canopy.json`; tier labels in the `canopy` lens). Missing when not fetched. |
| `permit`, `permitBand` | Toronto only (on dev): % of the unit's land inside an on-street permit parking area, and its band `p0` (none), `p1` (under 25%), `p2` (25–75%), `p3` (75% or more); tier labels in the `permit` lens. Built by `cities/toronto/parking.py`. A description of the place, not of the people; not used in `facts`. |
| `ages` | 5 shares (%) of residents by age, in the order of `card.living.ages.bands` (under 15, 15–24, 25–44, 45–64, 65+). Card only. |
| `recent` | Recent immigrants, % of residents: Toronto, immigrated to Canada 2016–2021 (2021 Census, of everyone in private households); Chicago, born abroad and entered the US in the ACS's latest period (of everyone). Demographic: card only, never a lens, filter or fact. |
| `recentSince` | Chicago only: that period in words ("2010 or later"). |
| `homesTier` | Not stored; the website computes it. Apps don't need it. |
| `facts` | Optional. Up to 3 ways the unit stands out among its peers, strongest first: `[{text, field, end, scope, rank, of, value}]`. `text` is a finished sentence fragment ("Highest rents in North York", "Among the most affordable homes on the South Side"); `value` is the figure behind it ("median $1,660/mo"). `field` is one of `value`, `rent`, `renterPct`, `transitPct`, `walkBikePct`, `carPct`, `canopy` (high end only: "Among the leafiest…"), `detached`, `large`, `oldest`, `newest`, `hub`; `end` `high`/`low`; `scope` `city` or `peers` (the unit's former city, Old Toronto area or side); `rank` (1–3) of `of` units. Built by `engine/facts.py` from non-demographic fields only. Units that don't stand out have no `facts`. |

Rows, in order (labels from `card.living`):

1. **Housing**: cost tier label · "Median home $800K · renters pay $1,320/mo" · `caveat`. The caveat explains what the rent
   figure counts (what renting households pay, utilities included, long-time tenants and subsidized
   homes too); keep it beside the figure.
2. **`hub`** (when the city's transit-time field is present): its tier label · `hubText` with
   `{minutes}`. The field is the lens in `lens.lenses` that has `minutes` (`union` in Toronto,
   `loop` in Chicago); its `key` names the tier field. With `hubs`, use the picked hub's `minutes`, `key` and
   `short` (the row's label); the website labels the row with `short` then, not `card.living.hub`.
3. **Getting to work**: commute tier label · "72% drive · 24% transit · 3% walk or bike".
4. **Households**: tenure tier label · "35% rent".
   **Tree canopy** (`card.living.canopy`, when `canopy` is present): the `canopy` lens tier label for
   `canopyBand` · `text` with `{pct}` · `caveat`.
5. **Home types** and **Built**: a small stacked bar, then each share of 1% or more in words
   ("Detached 37% · Semi & row 16% · …").
6. **Language at home**: the first language always; the 2nd and 3rd only at `floor`% or more
   (5). If only one shows, add "No other language above 5%". Then `note`, filled with
   `{multi}` = `langMulti` (the bracketed part drops when it's missing).
7. **Ages** (`ages`): the same stacked bar and words as Home types, five bands (`--mix-1` … `--mix-5`).
8. **Recent immigrants** (`recent`): `text` filled with `{pct}` and `{since}` (= `recentSince`), then
   `caveat`. Skipped when `recent` is missing.
9. Footer: `footer` filled with `{name}`.

Sources: Toronto 2021 Census (City of Toronto Neighbourhood Profiles); Chicago American Community
Survey 2020–2024. Neither is current pricing; the caveat says so and must stay.

## 8. Representatives

`{updated: "YYYY-MM-DD", <table>: {<key>: {name, url, party?}}}`. Tables and keys come from
`card.reps.offices`. Toronto: `wards` (by ward number), `prov` and `fed` (by riding name).
Chicago: `wards`, `house`, `senate`, `congress` (by number). Dallas: `council`, `house`, `senate`, `congress`
(by number; `congress` keyed by the 2021 districts in `us_house_2021.geojson`, until members elected on the new
lines take office in January 2027). A missing record means a vacant seat.
Checked weekly. Toronto's municipal election is October 26, 2026; new councillors appear within a
week of taking office (November 15).

Toronto also has `trustees: {board: {wardNum: {candidates: [name, …], winner?, acclaimed?}}}` for
the four school boards (`tdsb`, `tcdsb`, `viamonde`, `monavenir`), from the City's election results
file. `winner` appears once every poll in that ward has reported, or straight away for a ward with
one candidate (`acclaimed: true`). Results are unofficial until the City Clerk certifies them.
Around the election the file is refreshed hourly on election night and daily until November 16.
Toronto also has `council: {wardNum: {candidates: [name, …], incumbentRunning?, winner?, acclaimed?}}` for
the 25 council races, from the same file and with the same rules. `incumbentRunning` says whether the sitting
councillor (`wards[wardNum].name`) is on that ward's ballot, matched by name; absent if the seat has no member.
When it's false and the councillor is running elsewhere, `incumbentElsewhere` says where: `{office: "mayor"}` or
`{office: "council", ward: "14"}`. Toronto also has `mayor: {city: {name, url}}` (from the Mayor's page on
toronto.ca) and `mayorRace: {city: {candidates, incumbentRunning, winner?}}` (the results file's Mayor office).
There are no incumbent trustees in this data: TDSB's wards were redrawn for 2026, so the trustees
in office until November 15 sat on different lines.

New York's ballot (cities/nyc/ballot.py, from the Board of Elections' contest list) uses the same shapes with `race_assembly` in place of `race_house` (members' `runs.office` is still `house`), adds `race_council` (special elections; the member's `runs.office` `council`), and `race_statewide` keys `governor`, `comptroller`, `attorneygeneral` and `proposals` (the City Charter questions: `candidates` are the questions' titles, no `parties`; its office row has `ballot.text.race` for its own wording). New York's `parties` are already short and list every line a candidate is on ("D, WF"; an independent line named after the candidate is "independent"). Chicago and Dallas also have the November 3, 2026 ballot (engine/ballot.py, from each city's
`raw/ballot/candidates.json`): `race_congress`, `race_house`, `race_senate` `{district: {candidates: [names],
parties: [party as printed]}}` (a Senate district the ballot covers with no race: `{notUp: true}`), and
`race_statewide` `{ussenate, governor}`. Each `house`, `senate` and `congress` member gains `runs`:
`{office: "congress"|"house"|"senate", district}`, `{office: "statewide", race}`, or `null` (on no ballot), matched
by name. Dallas's races come from Dallas County's sample ballot, so districts that touch the city only in Collin,
Denton, Kaufman or Rockwall counties (TX-3, 4, 26; House 4, 33, 65, 70, 89) have no race entry.

Chicago has `trustees: {cps: {"1a": …, "10b": …, "president": {candidates, leader?, winner?}}}` for the
Chicago Board of Education election on November 3, 2026 (20 subdistricts and a citywide president;
terms start January 15, 2027). Candidates come from the Chicago Board of Elections' candidate list.
Its results pages give no "all precincts reported" signal and mail ballots are counted for two weeks,
so on and after election night only `leader` is set; `winner` appears once the board proclaims the
results (about three weeks later). Illinois has no acclamation: a sole candidate is still on the
ballot and shows as "1 candidate". The current board (10 elected in 2024, 11 appointed) isn't shown.

## 9. Not in this data

Real-time data (weather, air quality, traffic, beach water quality, transit arrivals) is not
published here. An app fetches it from its own sources and keeps it visibly separate from the
card's census and boundary data, with its own source line.

## 10. Changes

The website's maintainer updates this file whenever the published data changes shape. A breaking
change bumps `schema` in `city.json` and gets a new section at the top of this file saying what
changed and how to migrate.

## 11. Drawing the boundary layers on a map

The website draws its layers with Leaflet on a plain base. This section gives what an app needs
to draw the same boundary layers on another map (Apple's MapKit, for the iOS app): which layers,
their geometry, and how the website styles and labels them. Transit lines, streets, highways,
landmarks and the lenses are not covered here yet.

### Which layers

Every layer in `groups` whose `kind` is `fill`, `units`, `districts`, `outline`, `boards`, `patches`
or `knownas`. Keep the group order and use `name` and `note` for the layer list. A layer with
`"on": true` starts switched on. Today that gives:

| City | Layer (`id`, kind) | File |
|---|---|---|
| Toronto | Former cities (`boroughs`, fill major) | `boroughs` |
| | Old Toronto areas (`areas`, fill minor) | `areas` |
| | Neighbourhoods (`nbhd`, units) | `neighbourhoods` |
| | Known-as names (`cultural`, knownas) | `cultural` |
| | Heritage districts (`heritage`, districts) | `heritage` |
| | City wards (`wards`, outline city) | `wards` |
| | Provincial ridings (`prov`, outline state) | `wards` (see below) |
| | Federal ridings (`fed`, outline national) | `federal` |
| | School board wards (`school`, boards) | `school_wards` (one board at a time, see below) |
| | Business Improvement Areas (`bia`, patches) | `bia` |
| Chicago | The sides (`sides`, fill major) | `sides` |
| | Community areas (`ca`, units) | `community_areas` |
| | Known-as names (`knownas`, knownas) | `knownas` |
| | Landmark districts (`heritage`, districts) | `heritage` |
| | City wards (`wards`, outline city) | `wards` |
| | Illinois House districts (`house`, outline state) | `il_house` |
| | Congressional districts (`congress`, outline national) | `congress` |
| | School board districts (`school`, boards) | `school_board` |
| | Special Service Areas (`ssa`, patches) | `ssa` |

Read these from `city.json`; the table is a snapshot, not a list to hard-code.

### Geometry

- Each layer's `file` plus `.geojson`. Polygons are `Polygon` or `MultiPolygon`, **with holes**
  in every file above (Toronto's `areas` has 10, Chicago's `ssa` 23). Drawing an outer ring alone
  fills the holes and puts the wrong colour over the place inside. In MapKit, `MKGeoJSONDecoder`
  returns `MKPolygon` / `MKMultiPolygon` with `interiorPolygons` set, and each feature's
  properties as JSON `Data`. SwiftUI's `MapPolygon(coordinates:)` takes one ring and cannot
  draw holes.
- Toronto's provincial ridings reuse `wards.geojson`: in Toronto each ward is exactly one
  provincial riding. Same shapes as the ward layer, labelled with `{prov}` and styled as `state`.
- Several layers share edges (wards, ridings, neighbourhoods). The website just strokes each
  polygon; there is no separate line file.
- Sizes: 2,000–13,000 vertices per layer, 4–280 KB. Decode once per city off the main thread
  and keep the shapes; switching a layer on or off adds or removes them, it doesn't re-read.

### How the website draws them

Colours are `palette` keys (light / dark resolved there). Widths are in screen points. Drawing
order, bottom to top, is the table's order. Party colours: one riding layer at a time is shaded (the one switched on
or ticked most recently; a link or view with several picks the highest level), and while it is, the area fills and
the lens are switched off; they come back when the shading ends. Switching a fill or the lens on ends the shading.

| Kind | Fill | Stroke | Label (at `lp`) | Label shows from zoom |
|---|---|---|---|---|
| `fill`, size `major` | `colors[name]`, opacity 0.55 | `--city`, 2 (a pale gap between areas) | `name`, 15 pt heavy, `--ink` | 10; fades to 35% from 13 |
| `fill`, size `minor` | `colors[name]`, opacity 0.6 | `--city`, 2 | `name`, 13 pt bold, `--ink` | 11 |
| `patches` | `--bia`, opacity 0.45 | `--bia`, 1.2 | `label` template, 10 pt semibold, `--bia` | 14 |
| `districts` | `--hd`, opacity 0.14 | `--hd`, 1.6, dashed 4 on / 3 off | `label` template, 10 pt semibold italic, `--hd` | 14 |
| `units` | none | `--nbhd`, 0.9, at 70% opacity | `name`, 10.5 pt medium, `--ink-2`, wraps at ~120 pt | 13 |
| `outline`, level `national` | none | `--fed`, 2.2 | `label` template, 11 pt bold, `--fed` | 11 |
| `outline`, level `state` | none | `--prov`, 2, dashed 6 on / 4 off | `label` template, 11 pt bold, `--prov` | 11 |
| `outline`, level `city` | none | `--ward`, 2.2 | `label` template, 11 pt bold, `--ward` | 11 |
| `outline` with `party`, shaded | `--pty-<colour>` (`--pty-red`, `-blue`, `-orange`, `-green`, `-other`), opacity 0.38; vacant `--pty-vac` at 0.22; no member listed: none | `--pty-edge`, 1.8, solid, over a `--pty-case` halo 5.5 at 90% | as unshaded, in `--pty-edge` | 11 |
| `boards` | none | `--sbw`, 2.6, dashed 9 on / 4 off | `label` template, 11 pt bold, `--sbw` | 11 |
| `knownas` | (points: label only) | | `name`, 11.5 pt semibold italic, `--cult`; `kind: "enclave"` uses `--cult-enclave` | 12 |

- `places` layers (institutions): an icon per point, from zoom 11, the name beside it from zoom 14,
  coloured `--in-university`, `--in-college`, `--in-hospital`; a hospital with `ed` gets a heavier
  ring. Tapping one opens the card for that spot, titled with its name. The website's search also
  suggests them by name.
- `towers` layer: a square badge per tower (16 pt; 20 pt with a 2 pt `--tw-sup` gold ring when
  `super`), with a glyph per `use` (office: horizontal bands; residential: a grid of windows; mixed:
  both) in the panel colour on `--tw-res`, `--tw-com` or `--tw-mix`. When `uc`, the badge is hollow:
  panel colour inside, a dashed 1.5 pt border and the glyph in the use colour. Supertall icons from
  zoom 12 with names from 13; the rest from 14 with names from 15. Tapping one opens the card titled
  with its `name`.
- A `boards` layer draws only the features of one board at a time, chosen by the user (a row of
  `short` names under the layer; the default is the first). The website keeps the choice in links
  as `board=school:tcdsb`.
- Fill colours come from the layer's `colors` map by feature `name` (the same map that colours the
  first pill on the card). A name missing from the map uses `--ink-3`.
- Labels have no box; the website gives them a soft halo in `--city` so they read over lines.
- **Zoom** is the web-map zoom. From a MapKit region:
  `zoom = log2(360 × mapWidthInPoints / (256 × region.span.longitudeDelta))`.
  On a 390 pt-wide phone, zoom 11 ≈ 0.27° of longitude across, 13 ≈ 0.067°, 14 ≈ 0.034°.
- **Label collisions.** When labels overlap, the website keeps them in this order and hides the
  later one: known-as names, Old Toronto area names, unit names, ward / riding / district / school ward numbers,
  BIA / SSA names, heritage / landmark district names. (Former-city / side names are not in the
  list: they always show.) In MapKit, map this order onto annotation `displayPriority`.
- Tapping anywhere still opens the "What's here" card for that point (section 5); the drawn
  layers never change what the card says.

### Adapting to Apple's map

The website draws on its own pale base; Apple's map has roads, labels and points of interest of
its own. The values above are the website's. These adjustments are the app's to make and tune on
a real phone:

- Add overlays at the `aboveRoads` level so Apple's place and street names stay on top and
  readable. Use the muted map style and hide Apple's points of interest.
- The fill opacities (0.55, 0.6, 0.45) assume a blank base. Over Apple's map, start near 0.25 for
  `fill` and `patches`, and keep strokes as they are.
- Apple already labels many neighbourhoods. Draw unit labels only when the units layer is on,
  give them the lowest priority, and drop any whose text matches the place name Apple shows there,
  if that can be detected; otherwise accept occasional doubles and test.
- Rebuild or redraw overlay renderers when the appearance switches between light and dark, so the
  colours follow; renderers don't always pick up a dynamic colour change on their own.

### Check

Toronto, 43.66810, -79.36690 (the worked example in section 5) sits inside the Downtown fill
(`--a-downtown`), in Ward 13, inside the Cabbagetown (Metcalfe) heritage district, and outside
any BIA. `https://layers.city/toronto/#pin=43.66810,-79.36690` shows the same; turn the
layers on there to compare.

## 12. Links to pages on the website

The app opens these pages in an in-app Safari sheet rather than rebuilding them (added October 20, 2026).

- **Fact sheet for a spot:** `https://layers.city/<city>/profiles/?at=<lat>,<lon>` (latitude first,
  3 decimals is plenty). The page finds the neighbourhood that contains the spot, opens its sheet and
  drops a "you are here" pin. Outside every unit it says so. Optional `&lens=<id>` opens a lens other
  than the overview.
- **Fact sheet for a named unit:** `https://layers.city/<city>/profiles/?n=<slug>`, where `<slug>` comes
  from `https://layers.city/<city>/profiles/data/index.json` (`{asof, places: [{slug, name}]}`); match the
  unit's `name` from the card. Prefer the `at=` form when you have a spot.
- **Which cities have fact sheets:** those whose `profiles/data/index.json` loads (Toronto and New York as of
  October 20, 2026). A 404 means none yet: hide the link.
- **Venue pages:** `https://layers.city/<city>/venues/<slug>/` (Toronto and New York). The venue list isn't
  published as app data yet; it will be when the weekend brief needs it.


## 13. The list of cities

`https://layers.city/cities.json` (added October 21, 2026) lists every published city, so an app picks up
a new city without an update: `{version: 1, cities: [{id, name, title, schema, country, listed, region, data}]}`.
`name` is the short name ("Toronto"), `country` `ca` or `us`, `listed` false for a city that's live but not
announced, `region` the regional view's bounds `[[south, west], [north, east]]` (a quick first test of which
city a spot might be in, before the footprint and `base.geojson` tests in section 5), `data` the path of its
data folder. The build rewrites it whenever any city is assembled. Load a city's files only after its `schema`
is one the app knows; keep bundled cities working offline.

## 14. The weekend brief

`weekend.json` (Toronto and New York as of October 21, 2026; a city without it has no brief: hide the Weekend
tab's content and its notification). Built daily by `engine/weekend.py` in *Fetch transit closures* and
*Refresh venues*, so it always describes the next weekend: the coming one from Monday to Thursday, the current
one from Friday to Sunday.

```
{version: 1, city, tz, asof,
 weekend: {from: "2026-10-23T17:00", to: "2026-10-25T23:59", label: "Oct 23–25"},   city time, Fri 5 p.m. to Sun midnight
 sources: ["subway", "events", "roads", "venues"],                                   which inputs this city has
 closed: [{kind, title, line, when, start, end, at?, text?, link?}],                at most 5, already ranked
 on:     [{title, venue, slug, when, start, shows, at, link}]}                       at most 5, already ranked
```

- `closed[].kind`: `transit` (a planned rapid transit closure: `route` the line's number as text ("1"), `color`
  its palette key ("--l1", null when the palette has none; Toronto's Line 1 is yellow, so pick the badge's text
  colour for contrast), `title` "Line 1 · Finch to Sheppard-Yonge",
  `line` "No service · shuttle buses" or "Closes early at night", `text` the agency's full notice), `event`
  (special-event road closures: `line` "126 road closures", `at` the middle of the event, `link` the organizer's
  notice when there is one) or `road` (full closures of an expressway, ramp or major arterial that start at most a
  week before the weekend, so long-running closures don't repeat every week; closures within 600 m are one item,
  "3 closures near Lawrence W DVP N Ramp", `line` the stretch or "… and 2 more nearby", `at` a point on it;
  `when` says "Nightly 9 p.m.–5 a.m." or "Daily 6 a.m.–6 p.m." when the permit has set hours). Ranked transit, then events by size, then
  expressways, then arterials.
- `when` is display text clipped to the weekend: "Sat–Sun", "Sun 6 a.m.–6 p.m.", "All weekend". `start`/`end`
  are the full times in city time.
- `on[]`: shows at the city's big venues (Venues), biggest venue first, at most two from one venue; a show that
  repeats has `shows` > 1 and `when` "Fri–Sun" or "Sat · 3 shows". `link` is the venue's page on layers.city
  (getting there, parking). Facts only: no prices, images or ticket links (the event data's terms).
- Either list may be empty: say so ("No planned closures this weekend") rather than hiding the section.
- Transit closures in Toronto come from the TTC's GTFS-Realtime service alerts (City of Toronto Open Data, Open
  Government Licence – Toronto; since October 21, 2026, replacing the alerts list behind ttc.ca). A closure that
  runs only at night says "Closes early at night" with `when` naming the nights ("Fri night", "Fri–Sun nights").
  If the feed fails, `sources` loses `subway` and the brief carries on without it.

## 15. Transit: stops near a spot, where each route goes, live arrivals

Toronto as of October 28, 2026 (buses, streetcars, subway and LRT), San Francisco as of October 30 (Muni buses,
streetcars (`tram`), cable cars (`cable`, a word of their own: "cable car") and Muni Metro, as `lrt`, and from October
31 BART, as `subway`, with route ids `BART-Yellow` and so on and platforms headed "Platform 1"; live times from 511.org for Muni and from BART's own feed, `/api/arrivals?city=sf`: send `liveRapid` and
`&lines=` with the BART routes at the platforms asked for, as for New York). New York as of October 30 (MTA buses and the subway, live for both: buses from MTA Bus Time, the subway from the MTA's
feeds; add `&lines=<route ids>` with `liveRapid`, the rapid routes at the platforms asked for, so only their feeds
are read, and `&onlyRapid=1` when every stop asked for is a platform, so the bus feed isn't). It is the data behind
the website's "Where does this line or route go?" page (`/toronto/routes/`, `/sf/routes/`); an app can rebuild that page natively from it. A
city without `transit` in its `city.json` has none of this: hide the feature.

### Where things are: `city.json` `transit`

```
transit: {
  page:   "/toronto/routes/",                         the web page (deep link: ?stop=<stop id>&r=<route>&p=<pattern>)
  stops:  "/toronto/routes/data/stops.json",          every stop and platform, and every route's directions (below)
  route:  "/toronto/routes/data/r/{route}.json",      one file per route: its patterns' lines, stops and "story"
  sched:  "/toronto/routes/data/sched/{bucket}.json", when each route runs at each stop (below); null if none
  schedFiles: 128,                                    how many files sched is split into
  live:   "/api/arrivals?city=toronto",               next arrivals (below); null when the city has no live feed
  liveRapid: "&rapid=1",                              add when any stop asked for is a platform (s[8] = 1)
  liveNone: {"lrt": "the TTC doesn’t publish live times for Lines 5 and 6 yet"},   modes with no live data: show
                                                      the route's frequency ("Every 6 min or so") and, in detail, this
  liveSource: "TTC GTFS-Realtime",
  modes: ["bus", "tram", "subway", "lrt"],
  stationKm: 1, nearKm: [0.45, 0.8],                  search radii (below)
  regionsWithThe: ["East End", "West End"],           region names that take "the" in a sentence
  knownWithThe: "^(.* District|…)$",                  a pattern: known-as names that take "the" (the Financial District)
  known: "cultural",                                  the known-as layer file (section 3), for "in Greektown"
  title, credits,                                     the page's title and the credit line to show
  badges: {bus, tram, exp, night: {fill, text, outline?},   route badges: a rounded rectangle, number in it
           lines: {"1": {fill, text}, …}}                   subway and LRT: a round bullet in the line's colour
  words: {…}                                          the city's own wording (below); {} for Toronto
}
```

**City wording** (`transit.words`, added October 30, 2026; every key optional, and a missing key means Toronto's
wording, shown in brackets):
- `lineNames`: what to call a line in a sentence ("Line 1"): San Francisco's `{"J": "J Church", "Yellow": "BART
  Yellow line", …}`. A line named here leads a sentence with "The": "The J Church towards Balboa Park starts at …".
- `lineGroups`: lines said once by a group name: `{"BART": ["Yellow", "Orange", "Red", "Green", "Blue",
  "Oakland Airport"]}`. A station's bullets show one "BART" bullet (badge colour `#0E6FB8`, white text) instead of
  one per line, and "Change for BART, J Church".
- `at`: what joins a stop name's two streets (" at "): San Francisco's " & " ("Mission St & 16th St"). Use it
  wherever this section says " at ".
- `connectWith`: "connects with <this> at <stations>" ("the subway"): "BART and Muni Metro".
- `connectionsLabel`: the heading of the connections fact ("Subway connections").
- `mi`: true to show distances in feet under 0.1 mi and miles above (metres and km).
- `changeBare`: true to list lines in "Change for …" by their ids ("Change for 4, 5, 6") rather than `lineNames`.

Platforms' `side` and `travel` words can also be the agency's own: Muni's subway platforms are `inbound` and
`outbound` ("Inbound platform"), as are a Muni Metro line's patterns' `head` (show them capitalised, "Outbound").
In San Francisco a street stop a bus shares with a Muni Metro line is a stop (`platform` 0) with its side of the
street; a stop only Muni Metro uses, or one at a station, is a platform.
New York's platforms' `side` is the MTA's own sign wording: "Uptown platform", "Manhattan-bound platform".

Paths are on `https://layers.city`. The files are rebuilt whenever the schedule changes (weekly at most); they
are about 1.3 MB (`stops.json`, ~310 KB compressed) and 1–50 KB per route. Bundle `stops.json` with the city's
data and refresh it with the rest; fetch route files when a route is opened and cache them.

### `stops.json`

```
{asof: "2026-10-28", week: "2026-11-02",
 routes: {"<route id>": [short, name, mode, families, minutes, patterns]},
 stops:  [[id, name, lon, lat, side, travel, {"<route id>": [[pattern, d], …]}, code, platform], …]}
```

- **Route entry**: `short` the number riders see ("72", "1"), `name` ("Pape", "Line 1 (Yonge-University)"), `mode`
  (`bus`, `tram`, `subway`, `lrt`), `families` (`freq` every 10 min or better all day, `exp` express, `reg`
  other daytime routes, `night` overnight; a route whose only family is `night` runs overnight only: leave it
  out of the daytime list), `minutes` the typical weekday midday wait (null if under one an hour).
- **`patterns`**: one entry per pattern (a direction, or a branch of one), indexed from 0, matching
  `r/<route>.json` `patterns[k]`: `[head, to, length_m, share, regions, stations, next, dir]`.
  - `head`: `north`, `south`, `east` or `west`, the way the pattern runs on the city's grid (for subway and LRT,
    the word most of its platforms use). Show it as "Northbound" and so on.
  - `to`: where it ends: a station name ("Don Valley Station") or the last stop's name. Clean it (below).
  - `share`: its share of the route's trips (a branch with 0.2 is one bus in five).
  - `regions`: `[[from_m, to_m, name], …]`, the districts it passes through in order ("East End", "Scarborough").
  - `stations`: `[[d, name, lines], …]`, subway stations it connects with, `lines` the line numbers there. For a
    subway or LRT pattern these are only the stations where *other* lines meet it.
  - `next`: for a pattern that ends somewhere other than a station, the pattern it carries on as after looping
    round (the 88 inside Thorncliffe Park), or null.
  - `dir`: the schedule's direction, "0" or "1".
- **Stop**: `id` the agency's stop id (the id live arrivals use); `name` as the agency writes it; `side` "South side",
  "Eastbound platform" or ""; `travel` the direction traffic travels there (`north`…); then which patterns of
  which routes call there and how far along each (`d`, metres from the pattern's start); `code` the stop number on
  the pole ("Stop #8361"), "" for platforms; `platform` 1 for a subway or LRT platform, else 0.
- A stop is matched to the direction whose side of the street it's on, so the two sides of a street are two stops.
  Platforms are named after the station on the map ("Bloor-Yonge Station - Northbound Platform").
- **Cleaning names** (as the page does): drop a platform suffix (" - Eastbound Platform", " LRT Platform") and
  the agency's side notes (" North Side", " (East)"). The street of a stop is the cleaned name before " at ",
  without a leading house number ("44 Thorncliffe Park Dr" → "Thorncliffe Park Dr").

### Stops near a spot (the list)

1. Take stops within `nearKm[0]` (450 m) of the spot, and platforms within `stationKm` (1 km); if there are
   none, try `nearKm[1]` (800 m).
2. For each daytime route and direction, keep only its **nearest** stop. The direction key is the pattern's
   `head` for buses and streetcars, and its `dir` for subway and LRT (Line 1 is southbound on Yonge and
   northbound on University in the same direction of travel). Skip a pattern with less than 300 m left
   after the stop (the bus ends there). A ride that loops round first (below) counts as 200 m further away, so a
   stop across the road going straight there wins.
3. Group the kept stops into cards by cleaned name, when within 150 m of each other (both sides of an
   intersection; a station's platforms and its bus bays). Sort cards by distance and show at most eight, plus
   any station card beyond them. In a card, platforms come first, then stops by distance.
4. Each stop is a section headed by its `side` ("Eastbound platform", or "South side of Overlea Blvd · Stop
   #8344") with walking directions to its exact position. Each route there is a row: the badge, the
   direction word (for a platform, the platform's own `travel` word), "<name> to <to>" ("Pape to Don Valley
   Station"; for a line, "Line 2 to Kennedy Station"), the next arrivals, then up to two subway connections
   *ahead* of the stop (`stations` with `d` more than 150 m past the stop's `d`) and the regions it goes on
   to ("East York → North York", each once, in order). Rows sort subway and LRT first, then frequent routes,
   express, others, then by number.
5. **Loops**: when a pattern has `next` and less than max(1.5 km, 30% of the pattern) is left after the stop,
   describe the ride as carrying on into pattern `next`: its direction, `to`, regions and stations follow on
   (the second pattern's distances shifted by the first's length). Mark the row "↻ Loops round first". Among
   rides in the same direction, prefer a straight one, then the longest.

### Live arrivals: `GET {live}&stops=<id>,<id>…[&rapid=1]`

```
{now: 1793123589, asof: 1793123574,
 stops: {"8344": [[route, dir, epoch_s, live], …], …}}       sorted by time, up to 90 minutes ahead
```

- San Francisco's answers can be up to 15 minutes old when 511.org turns a request away (it allows 60 an hour):
  compare `asof` with `now`, and past 5 minutes treat the times as scheduled (no "live" styling).
- Up to 24 stop ids per request. Send `liveRapid` when any of them is a platform. Answers are cached 15 s at the
  edge and the agency's feed 20 s, so refreshing more often than every 30 s gains nothing.
- Match an arrival to a row by stop id and `route` (the route id). Ignore `dir`: Toronto's feed leaves it 0.
- `live` 1: a vehicle is on its way (a prediction). 0: the trip hasn't started; the time is the schedule's. Show
  the second kind differently (the page uses grey italics).
- Show the next three as minutes from now, from `epoch_s - now` (correct for the phone's clock skew with `now`);
  "Due" under a minute. A route in `liveNone` has no arrivals: show "Every {minutes} min or so".
- The request carries only stop ids; nothing about the caller is kept. Nearby stop ids do say roughly where the
  phone is: ask only while the list or a widget is showing, and say so in the app's privacy notes.
- On an error (503) or no network, show no times rather than old ones as if new.

### Scheduled times: `sched/{bucket}.json`

For a route with no live times (overnight, a rush-hour-only route, Lines 5 and 6 before they open for the day),
the next departure from the timetable: "Next bus at 5:42 a.m.", "Next streetcar tomorrow at 6:01
a.m.", "Next train Monday at 6:00 a.m." (bus, streetcar, train for subway and LRT).

The timetable is split by stop id into `schedFiles` files. A stop's file: `h = 0`, then for each character of the
id, `h = (h × 31 + its character code) mod schedFiles`; fetch `sched` with `{bucket}` replaced by `h`. Each file
is a few kilobytes and stands alone:

```
{fetched: "2026-10-28", feed: ["2026-11-01", "2026-12-21"], tz: "America/Toronto", gap: 90,
 days:  {"2026-11-01": 0, …},             each date in the next ten weeks (within the feed) -> its kind of day
 week:  [1, 2, 3, 3, 4, 5, 0],            Monday to Sunday of a typical week: for a date not in days
 spans: [[342, 1530, …], …],              this file's span lists: [start, end, start, end…], minutes
 stops: {"<stop id>": {"<route id>": [index into spans for each kind of day], …}, …}}
```

- Minutes are in `tz`, from the start of that service day; they can pass 1440 (a 1:30 a.m. bus is 1530 on the day
  before). A span is a run of departures with no gap longer than `gap` minutes (the live feed's reach); an empty
  list means the route doesn't stop there that kind of day.
- Next departure: take the city's date and time now; for the day before, today and the next seven days, add that
  day's offset × 1440 to its spans. If now falls inside a span, the route is running: show nothing from here (the
  live times, or "No live times right now"). Otherwise the next departure is the earliest span start after now.
- Show it only when there are no live times for that row, and for `liveNone` routes in place of the frequency
  while they aren't running. The page says "from the timetable" in the route detail. Fetch a stop's file when first needed and cache it until
  `stops.json` changes.

### One route from one stop: `r/<route>.json`

```
{r, n, m, f, h,                         as the route entry above
 stops: {"<stop id>": "name", …},       every stop the route calls at
 patterns: [{k, dir, trips, share, head, km, to,
             line: [[lon, lat, d], …],  the pattern's path, d metres along it
             stops: [[d, stop id], …],  its stops in order
             hoods:   [[from, to, name or [a, b]], …],   neighbourhoods; [a, b] means it runs on the boundary
                                                         ("between Blake-Jones and North Riverdale")
             regions: [[from, to, name], …],
             streets: [[from, to, name], …],             the streets it runs along (under, for a subway)
             cross:   [[d, name], …],                    main streets it crosses (none for subway and LRT)
             stations:[[d, name, lines], …],
             pois:    [[d, name, kind], …],              landmarks within 200 m: "Shopping mall", "Hospital",
                                                         "Bridge" ("Over the Leaside Bridge") …
             known:   [[d, name], …],                    known-as names within 250 m ("Riverdale")
             calls:   [[d, station], …],                 subway and LRT only: every station, in order
             next?}]}                                    the pattern it loops into, as in stops.json
```

Everything is measured in metres along the pattern, so a ride from a stop is the part of each list past the
stop's `d` (from `stops.json`). Through a loop, append pattern `next` with its distances shifted by the first
pattern's length (its last `line` d), and add a step "The bus loops round at <last stop>: stay on".

**The paragraph ("Takes you through")** describes the whole pattern the rider is on (for a loop, the pattern
it loops into), as the page writes it:

- A title: "<from> to <to> (via <station>)". A start or end at a station is the station; a stop on the route's
  own main street goes by its cross street. "via" is the connection where the most lines meet, the one nearest
  the middle of the trip on a tie, else the street it runs along longest.
- "The 72 southbound starts at <start> and runs along <main streets>, from <first region> through <…> into
  <last region>." For a line: "Line 2 towards Kennedy Station starts at …" and "runs under" for subway. Main
  streets are those it runs along for at least max(700 m, 10% of its length) (1.5 km for subway and LRT),
  at most four, in order. Each region once, in the order reached.
- "It serves <places>, connects with the subway at <stations>, and passes <landmarks>, before ending at <end>."
  Places: the known-as names along it (in italics), topped up to three or four with neighbourhoods it runs
  through for 500 m or more, at most five, leaving out a name that repeats one already used (Leaside-Bennington
  after Leaside). Stations: those between start and end, each with the known-as name within 500 m ("Pape
  Station in Greektown"), said once for neighbours sharing it. A line with four or more stations along the
  route becomes "follows Line 5, with 23 of its stations along the way", naming only stations where another
  line meets it. Landmarks: at most four. Names matching `knownWithThe` and regions in `regionsWithThe` take
  "the".

**The steps ("From your stop, in order")**: from the stop's `d` to the last stop, ordered by `d`: the stop
(with its neighbourhood and region), "Into <region>", "Along <street>" (with its length; "Under" for subway),
each new neighbourhood, stations ("Change for Line 2"), for subway and LRT each station called at, landmarks
with their kind, known-as names, "Crosses <street>" (in a quieter style), and the end. Facts beside it: the
connections ahead, where it ends (with its neighbourhood), and "<n> stops · <distance> · about every <h> min,
weekday middays".

**The map**: draw `line` from the stop's `d` on (the part behind faded or left out) over the city's
neighbourhoods, main streets and subway lines (sections 3 and 11), with the stop, the end, stations (every
call, for a line) and landmarks marked at their `d` along `line`. Tint the neighbourhoods it passes, each a
different colour in turn, with their names, and the known-as names near the route.
