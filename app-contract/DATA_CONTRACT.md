# Layers.City data contract (schema 1)

This is everything an app needs to rebuild the map's "What's here" card from the published
data, without reading the website's code. The website (this repo) is the only producer; an app is
a read-only consumer. Last updated October 10, 2026 (Skyscrapers: the `towers` layer kind, `skyscrapers.geojson` and a tower block on the card; campuses off the Landmarks file, their nicknames now on the Universities layer as `aliases`; `under` on layers nested under Landmarks; `distance` unit, Chicago in miles with a half-mile Nearby radius; Chicago's Schools section and `attendance.geojson`; Nearby section and `nearby.json`; institution points: the `places` layer kind and `institutions.geojson`; school boards in both cities: the `boards` layer kind, a School wards / School board row and trustee rows, with Chicago's leader and citywide president; earlier: map layers and `palette`, section 11; card title names the neighbourhood; profile facts; Chicago's To the Loop fields).

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
- **Caching.** GitHub Pages serves with about a 10-minute cache. The data changes rarely
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
| `base.geojson` | Outline shapes. `properties.kind`: `city` (the city itself), `neighbour` (each surrounding municipality, with `name`, `region`, `lp`, `drive`), `outside` (land beyond the region). |
| `regions.geojson` | Label points for regions/counties. Not needed for the card. |
| Layer files | One per map layer, named by `file`/`files` in `city.json` `groups`. Section 5 lists the ones the card uses. |
| `nbhd_profiles.json` / `ca_profiles.json` / `la_profiles.json` | Census figures per neighbourhood / community area / local area (Vancouver, in progress). File name is `lens.file` in `city.json`. Section 7. A unit with no entry here (Vancouver's Stanley Park, code 23) has no Living here rows and takes no lens tier. |
| `representatives.json` | Who holds each seat. Section 8. |
| `drive_grid.json` | Free-flow drive minutes to the hub on a ~1.5 km grid, outside the city. Section 6. |
| `region_places.json` | Toronto only: ~470 named GTA communities. `[{name, muni, region, kind, at:[lon,lat]}]`. |
| `region_areas.geojson` | Region/county outlines for the regional view. Not needed for the card. |
| `nearby.json` | Points for the card's Nearby section: `{groups: {key: [[lon, lat, name?], …]}}`. Keys and labels come from `card.nearby` (section 5). Named kinds (`library`, `centre`, `er`) carry a name; counted kinds (`park`, `playground`, …) are bare points. |
| `attendance.geojson` | Chicago only: CPS attendance areas for the card's Schools section. One polygon per school and grade range, all levels in one file. `properties`: `level` (`es` elementary, `ms` middle, `hs` high), `grades` ("K–8", "7–8", "9–12"), `name` (the school's full name), `url` (its CPS profile page, may be empty), `x`, `y` (the building, lon/lat; absent when unknown, then `addr` may name the street). Top-level `year` ("2025–26"). Areas of one level don't overlap. Describe only: no ratings, scores or enrolment. |
| `voting.geojson` | Only around an election (Toronto, and Chicago in precinct-only form): the voting subdivisions with each one's election-day voting place, for the card's where-to-vote box (`card.vote`, section 5). Built by `cities/toronto/voting.py` from the City's voting subdivisions and voting places (fetched daily in October by `fetch-voting.yml`). One polygon per subdivision; they don't overlap. `properties`: `c` code (ward, 2 digits, + subdivision, 3), `w` ward number, `a` the place's address, `x`, `y` the place (lon/lat), and when known `n` building name, `e` preferred entrance (left out when just "Main Doors"), `ae` accessible entrance when different, `vat` true where a Voter Assist Terminal is set up. Top-level `asof` (the City's last edit) and `election` (date). Advance voting places are not included. Chicago's file has no voting places (the Board publishes none by precinct): each feature is a precinct with only `c`, `w` and `p` (precinct number); top-level `asof` is the date the precinct layout was approved. |
| `skyscrapers.geojson` | Buildings 150 m and taller (points) for the `towers` layer, from each city's Wikipedia list (CC BY-SA 4.0; credit "Wikipedia"), built by `engine/skyscrapers.py`. Sorted tallest first. `properties`: `name`, `h` (height in metres, architectural: spires count, antennas don't), `ft` (feet), `floors` (may be null), `year` (completed, or expected when `uc`; null when unknown), `use` (`res`, `com` office or hotel, `mix`), `purpose` (display word: "Residential", "Office", "Hotel", "Mixed-use"), `uc` (true until open for occupancy, including topped-out towers), `super` (true at 300 m+), `rank` (by height in the city among towers built or topped out; a tower still under construction gets the rank it will have), `facts` (1–3 short sentences, most telling first), and optionally `aka` (a former or popular name), `address`, `wiki` (English Wikipedia article title). Top-level `source`. |
| `heritage_buildings.geojson` | Heritage buildings (layer kind `heritage`, id `hbld`), built by `engine/heritage_buildings.py` from `cities/<city>/raw/heritage_buildings.json` (fetched monthly by `engine/fetch_heritage_buildings.py`). Properties protected one by one: Toronto, Part IV designations from the City's Heritage Register (listed properties and district-only Part V properties left out); Chicago, the City's Individual Landmarks (a point inside each landmark's shape). Top-level `asof`. `Point` features: `n` name (always in Chicago; Toronto only when the register's description starts with one, about half), `a` address, `y` year built, `ar` architect, `d` year designated, and Toronto only `b` designation by-law(s), `t` building type, `hcd` the Heritage Conservation District it is also in; Chicago only `id` ("L-176"). Any field may be missing. |
| `changes.geojson` | What's changing (layer kind `changes`, loaded after the map; card section `chg`), built by `engine/changes.py` from `cities/<city>/raw/changes/` (fetched weekly by `engine/fetch_changes.py`). Big changes only: new buildings that aren't single houses, demolitions of buildings that aren't houses and (Toronto) rezoning, site plan and subdivision applications. Top-level `asof` (fetch date), `window` (years). `Point` features, one per site (items within 35 m merged): `k` kind (`rezoning`, `siteplan`, `subdivision`, `building`, `demolition`), `s` stage (`proposed`, `approved`, `building` = under construction, `finished`), `date` (YYYY-MM-DD) and `dl` what that date is (`applied`, `issued`, `finished`), `a` address, `d` short description, optional `u` (the City's page: Toronto applications), `n` (application or permit number), `units` (homes created, when known), `status` (the source's own status), `also` (`[[kind, stage, "YYYY-MM", url]]`: other items on the same site). Withdrawn, refused, cancelled, expired and suspended items are left out; open items up to 6 years old; approved items by application date within 4 years (the data has no decision date); finished within 2 years. Chicago has no `proposed` (no proposals data) and no completion date (`dl` is `issued`). |
| `addresses.geojson` | How addresses work (layer kind `addresses`), built by `engine/addresses.py` from the city's own `streets` and `collectors` files and `cities/<city>/addresses.json`. Top-level `kind`: `grid` (Chicago) or `divide` (Toronto). **grid**: `LineString` features with `role` (`base` for the two zero lines, `mile` for the rest), `axis` (`ns`: an east-west line carrying a north/south number; `ew`: a north-south line carrying an east/west number), `num`, `dir` (`N`, `S`, `E`, `W`, or empty for 0), `street` (the street on that line) and `label` ("2400 N"); each line is straight across the city, clipped to its outline. Top-level `axes`: `{ns: [[lat, signed number]…], ew: [[lon, signed number]…]}` sorted by position, north and east positive; interpolate linearly between neighbours (and carry the end stretch's pace beyond them) to read a spot's address numbers. **divide**: top-level `street` ("Yonge St"; Vancouver "Ontario St"); features with `role` `divide` (that street, and in Vancouver also Carrall St downtown, each with its own `street`) or `e` / `w` (a drawn street named … E or … W that meets it; in Vancouver W … or E …, e.g. "W Broadway"), `street` the name. Optional top-level `axes` (`{ns: [[lat, number]…], ew: [[lon, signed number]…]}`, as a grid city's, sorted by position; `ns` numbers have no direction: they rise going south) and `axesArea` (`[west, south, east, north]`, where the axes hold): interpolate to read a spot's block numbers (Vancouver, south of False Creek). Card text: `card.address.blocks` (`{ns}`, `{ew}` with W or E). |
| `construction.geojson` | Transit lines under construction (layer kind `construction`), built by `engine/construction.py` from OpenStreetMap (ODbL) and the curated `cities/<city>/construction.json`. Line features (`LineString` or `MultiLineString`): `id`, `name`, `short`, `mode` (`subway`, `lrt`), `color` (hex), and optionally `owner`, `opens` (only an owner-published estimate, as text), `length` (text), `about`, `link`. Station features (`Point`): `part: "station"`, `id` (the line's), `name`. Only lines with construction under way; a line opens → it leaves this file. |
| `closures.geojson` | Optional; may be missing or empty (load it so a failure doesn't stop the map). Road closures and lane restrictions caused by transit construction (layer kind `closures`), rebuilt daily just after midnight Eastern by `engine/closures.py` from Toronto's Road Restrictions feed and Chicago's CDOT permits. Top-level `asof` (local time of the fetch, "YYYY-MM-DDTHH:MM") and `today`. `LineString` (or `Point` when a permit has no stretch). `properties`: `proj` (a line `id` from `construction.geojson`, `up` for work on an existing line being upgraded, or `other`), `name` (the project, display text), `street`, `extent` (text), `kind` (`closed` or `narrowed`), `art` (true on a drawn arterial; false = a local street, shown only zoomed in; lane work on local streets is left out), `start`, `end` (permit dates, "YYYY-MM-DD" or with time; not a reopening forecast), `hours` ("24h", "21:00–05:00" or null), `days` (`daily`, `weekdays`, `weekends`, `some days` or null), `both` (both directions), `who` (permit holder), `desc` (up to 220 characters). Includes permits starting within 7 days; hide those whose `end` is before today in the city's time zone (`tz` on the layer in `city.json`). |
| `transit.json` | Streetcar and bus routes and stops, built by `engine/surface.py` from the agency's GTFS (TTC, CTA), refreshed monthly. Top-level `asof` (fetch date, "YYYY-MM-DD") and `week` (the Monday of the week the schedule was read for). `routes`: `[{r, n, m, f, day, h, b}]`: `r` route number (text: "29", "J14", "X9"), `n` name ("Dufferin"), `m` mode (`tram` streetcar, `bus`; in Toronto also `go`, below), `f` families (any of `freq`, `exp`, `reg`, `night`; below), `day` (false for a route that runs only overnight, e.g. Toronto's 300-series), `h` (typical wait in minutes on weekday middays, 10 am–3 pm, in the busier direction; null under one trip an hour), `b` bounds `[west, south, east, north]`. `stops`: `[[lon, lat, name, [route index, …]]]`, indexes into `routes`. Families describe the service and are never a ranking: `freq` = at least 6 trips an hour each way, averaged over every 3-hour block from 7 am to 7 pm on a weekday; `exp` = the agency names the route express; `night` = at least one trip each way in every hour from 2 to 4 am on a weeknight; `reg` = every other route with daytime service (neither `freq` nor `exp`). Other agencies (Toronto: GO buses, from Metrolinx's GO GTFS, refreshed with the TTC's) join the same lists with their own `m` (`go`), `r` prefixed so numbers never collide ("GO 41", not "41"), `f: []` (the families describe the city's own network), and `in: true` on routes with a stop inside the city. Top-level `feeds` (only when there are any): `{go: {asof, week, routes, in}}`. Apps that don't show GO buses can skip routes whose `m` isn't `tram` or `bus` (and stops served only by them). |
| `transit_routes.geojson` | One feature per route in `transit.json` (`MultiLineString`, simplified ~8 m: the route's busiest pattern, plus stretches of its other patterns and direction that run more than ~35 m from it, such as branches and one-way pairs). `properties`: `r`, `n`, `m`, `f`, `day`, `h` (and `in` for other agencies' routes) as in `transit.json`. Top-level `asof`, `week`, `feeds`. The website loads it only when the Bus routes layer is on or a route is picked. |
| `streetcars.geojson` | Toronto only: the features of `transit_routes.geojson` with `m: "tram"` and `day: true` (the 11 daytime streetcar routes), for the `streetcars` layer. |
| `collectors.geojson` | Collector streets (layer `coll`, kind `streets`, `under: "streets"`): one feature per street name (`LineString` or `MultiLineString`), `properties`: `name`, `cls` (`"coll"`), `len`. Toronto from the City's Collector road class; Chicago from OpenStreetMap `tertiary` roads. Stretches on a main street are left out. Drawn thinner than `minor` from zoom 13; `labelZoom` (15) is the zoom names start at; `yieldLabels` means its names give way to the main streets'. |
| `institutions.geojson` | Universities, colleges and hospitals (points) for the `places` layers. `properties`: `name`, `cat` (`university`, `college`, `hospital`), `sub` (campus, network or ownership, optional), `ed` (true for a hospital with an emergency department). Curated by fixed rules (public or nonprofit only; see each city's `institutions.py`). Describe only: no ratings. |

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
- `distance` (optional): the unit for distances shown on the card, `"km"` (the default when absent; Toronto) or `"mi"` (Chicago). Config values such as `card.nearby.radius` stay in metres either way.
- `units.singular` / `units.plural`: what the city calls its units ("Neighbourhood",
  "community areas").
- `footprint`: the id of the layer that outlines the city. A point outside it gets the
  "outside the city" card.
- `groups`: `[[groupName, [layer, …]], …]`. Each layer has `id`, `kind`, `name`, `note`, and
  `file` (one file, add `.geojson`) or `files` (several). Kinds the card tests a point against:
  `fill`, `units`, `outline`, `patches`, `districts`, and `boards` (below). The `knownas` kind is a
  point layer used by distance (step 4 below). Other kinds are map drawing only.
- A `boards` layer (`school` in both cities: Toronto's file `school_wards`, Chicago's `school_board`) holds several overlapping sets of
  wards in one file, one set per school board. Each feature has `board` (an id), `num` (the
  board's ward number, a string), `area` (a ward name, French boards only, e.g. "Est"), `wards`
  (the City wards it is made of) and `lp`. The layer's `boards` lists `[id, short, long]` per board
  in display order (`["tdsb", "TDSB", "Toronto District School Board"]`); the first is the one the
  map shows by default. Chicago has one board (`cps`, the Chicago Board of Education; `num` "1a" …
  "10b"), so there is nothing to pick. Templates on this layer can use `{short}` and `{long}` as well as the
  feature's fields.
- A `places` layer draws the points of `file` whose `cat` equals the layer's `cat` (several layers
  share `institutions.geojson`). `place` names the kind of place ("Hospital", "City College"),
  `edText` the extra hover words for a feature with `ed`, and `aliases` (optional, Universities)
  maps a feature `name` to the nicknames search should also match. Not part of the card.
- A `towers` layer (id `towers`, file `skyscrapers`) draws every feature of `skyscrapers.geojson`.
  Its text: `place` ("Skyscraper", search sub-line), `key` (`res`, `com`, `mix`, `uc`, `sup`: the
  legend shown under the layer while it's on), `purpose` (card wording per `purpose`, e.g.
  "Office tower"), `supText`, `ucText`, `builtText`, `expectedText`, `akaText` (`{aka}`),
  `moreText` (the Wikipedia link), `sourceText` (shown when a tower has no article). Card: section 5,
  step 5a.
- A `streetcars` layer (Toronto, id `tram`, file `streetcars`) draws its routes in `--tram`, each numbered
  along the line; stops (from `transit.json`, those served by a daytime streetcar) from zoom 15.
- A `heritage` layer (both cities, id `hbld`, file `heritage_buildings`, off by default, after Heritage districts): a small diamond per property in `--hd` from zoom 15 (`minZoom`; only those in view are drawn), its name from zoom 16. Tap: name (or address), `place` and type, address, `builtText` (`{y}`), `byText` (`{ar}`), `designatedText` (`{d}`), and Toronto's `bylawText` and `hcdText` rows. Named ones are in search.
- A `changes` layer (both cities, id `chg`, file `changes`, `lazy`, `optional`, off by default): a dot per site coloured by stage (`--chg-1` proposed, `--chg-2` approved, `--chg-3` under construction, `--chg-4` finished), demolitions as dashed rings; `stages` (`{id: [short, long]}`, the panel's chips, any mix; links write `chg=proposed+approved` when not all are on), `kinds` (labels), `dates` (`applied`, `issued`, `finished` templates with `{date}`), `unitsText`, `alsoText`, `linkText`, `legend`. Tap a dot: kind, stage and date, address and homes, description, the other items on the site, the link.
- An `addresses` layer (both cities, id `addr`, indented `under` Main streets, off by default, file `addresses`):
  grid cities draw each `base` line bold and each `mile` line dashed in `--ag`, labelled once at its west
  (`ns`) or north (`ew`) end ("2400 N"; a base line "Madison St · 0"); divided cities draw the `divide`
  street bold in `--ag` and the `e` / `w` streets in `--ag-e` / `--ag-w`, with "West · Yonge St · East"
  marks along it (`westText`, `eastText`). Name in the panel: "Address grid" (Chicago), "Yonge: East and
  West" (Toronto).
- A `regional` layer (Toronto: id `gobus`, "GO buses", indented `under` the GO trains, file `transit_routes`,
  `lazy: true`) draws another agency's routes, those with `m` equal to the layer's `mode` (`go`), in that
  mode's colour (`--gobus` in `city.css`), numbered like the others ("GO 41"). Regional view: every route.
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
- `card`: `pills`, `facts`, `living`, `reps` (section 6).
- `lens.file` (the profiles file) and `lens.lenses`: each has `key` (the profile field holding a
  tier id) and `tiers: [[tierId, label, colourVariable], …]`. Use the label; the colour variable
  resolves through `palette`.
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
  (template for the region name), `note` (shown on outside cards).
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
7. **Standout** (optional line under the pills): if the unit's profile has `facts`, show the first
   one as "{profile name}: {text, first letter lower-cased}" followed by its `value` in smaller
   type. Section 7.
8. **Living here**: look up the profile by `hits[unitsLayerId].properties.code` (as a string key).
   Section 7.
9. **Representatives** (`card.reps.offices`, in order). Skip the whole section if the first
   office's layer has no hit. For each office: `h = hits[office.layer]`;
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
   **Nearby** (`card.nearby`, both cities): for each `[key, label]` in `nearest`, the nearest point
   of `nearby.groups[key]` by straight-line distance: row `label`, value its name, subline the
   distance ("600 m away"; to the nearest 50 m under a kilometre, then "1.8 km". With `distance`
   `"mi"`: "250 ft away" to the nearest 50 ft under 0.1 mile, then "0.4 mi", whole miles from 10). Then one row,
   label `within`, value the count of points of each `[key, one, many]` in `counts` within
   `radius` metres, "19 parks · 7 playgrounds …" (`one` when the count is 1). Footer `note`, always
   shown. Counts only: never a score, ranking or "best". The website shows this section between
   Schools and Representatives.
   **Schools** (`card.schools`, Chicago only): load `card.schools.file` (`attendance.geojson`). For
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
   **Transit nearby** (`card.transit`, both cities): load `card.transit.file` (`transit.json`). Rows:
   - `station`: the nearest station of the `metro`-kind layer (its second file: `subway_stations` /
     `cta_stations`), skipped beyond 5 km; value its name, subline `stationSub` filled with `{lines}`
     and `{dist}`.
   - For each `[mode, label, named]` in `rows`: the routes of that `m` with `day: true` that have a stop
     within `radius` metres, nearest stop first; each shown as its number (`named`: number and name,
     "501 Queen"). A route in family `freq` is marked (filled by default; a double ring in Toronto and Chicago, whose
     chips follow the map's badge styles); the note says so.
     Toronto has a third row, `["go", "GO buses", false]`: GO routes with a stop within `radius`.
   - `night`: routes in family `night` with a stop within `radius` (Toronto's 300-series, Chicago's
     overnight routes), numbers only.
   - `stop`: the nearest stop's name and distance, or `none` when there is no stop within `radius`.
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

**Views** (`presets` in `city.json`, optional): one-tap named views shown as a chip row at the top of the website's panel. `label`, `customText` and `customNote` (`{name}`: shown once someone changes the map after picking a view), `boundaryLabel`, `electionText` (`{label}`), `window` (days, default 180), `items` and `elections`. Each item: `{id, name, note, layers, lens, bus, scope, view, boundaries, lead, hint}`. A view replaces the whole state: exactly `layers` on (sub-toggles such as `stnNames` included), `lens` (else the first lens), `bus` families (else the layer's default), `scope` `inner` (default) or `outer`, no filters, picks, focus or card, then `view` (`"city"`, `"region"` or bounds). `boundaries` (Who represents me) is a list of boundary layer ids shown one at a time with chips to switch; the first one on is the `lead` of the earliest `elections` entry `{date, lead, label}` dated today or later and within `window` days, else the item's `lead`. `hint` is text for under the search box while no spot is pinned. Ids are the same in every city (`explore`, `local`, `civic`, `newcomer`, `transit`); links carry `preset=<id>`. Apps may ignore it.

**Heritage building row** (`{"label": "Heritage building", "heritageBuilding": true}` in `card.facts`, after the heritage district row): the property within 40 m of the spot (150 m when the pin's name matches the property's), nearest first, shown as its name (or address) with "(built 1901, designated 1976)"; no row when there is none.

**Road closures** (`card.closures`, section `cls`, before Changing nearby; Toronto and Chicago; October 14, 2026): from the `closures` layer's file whatever the layer's toggle, only when at least one is within `radius` m (Toronto 500, Chicago 805) of the spot; otherwise the section is left out. Hide permits whose `end` is before today in the layer's `tz`. Distance to the nearest point of the line. Nearest first (a `closed` before a `narrowed` at the same distance), at most `max` (4): the layer's `closedText` or `narrowedText` with a red line or amber dots key · `street` · a line of `startsText` (permits starting later), `untilText` (with the year and `longText` when two or more years out), hours (`allDayText` for "24h"), the project `name` and the distance · `extent` when it differs from `street`. More than `max`: `more` with `{n}`. Footer `note` with `{date}` = the file's `asof`. Permit dates, never a reopening forecast.

**Changing nearby** (`card.changes`, section `chg`, after Nearby): sites within `radius` m (Toronto 500, Chicago 805), nearest first, at most `max` (6): kind with a stage dot (ring for demolitions) · address · stage, date (`dates[dl]`) and distance · the description cut to about 110 characters · the link. More than `max`: `more` with `{n}`. None: `none`. Footer `note` with `{date}` = `asof`.

**Address row** (`card.address`; a Boundaries row placed by `{"label", "address": true}` in `card.facts`): grid cities show `grid` filled with `{ns}` and `{ew}`, the spot's numbers read off `axes` and rounded to the nearest 100 ("About 2400 N · 1200 W"; 0 shows as "0"), then `sub`. Divided cities show `east` or `west` (which side of the `divide` street the spot is: its longitude at the spot's latitude, or at its nearest stretch), then `sub` with `{street}`: the nearest `e`/`w` street on that side within about 1.5 km, or `example[side]`.

**Compare two places** (website, since 1.1): the same card for two spots, merged row by row. Each
section's rows are lined up by label (the first place's order, then any the second place alone has);
the label sits above the two values, A then B, with "—" where a place has no row. Caveats and
footer notes show once per section. Spots outside the city contribute Municipality and region rows
(Boundaries) and the drive-time row (Living here). Nothing is ranked or highlighted. Links:
`pin`/`name` for A, `pin2`/`name2` for B.

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
| `cost`, `commute`, `tenure` | Tier ids; labels come from `lens.lenses` (match `key`). |
| `union`, `unionBand` | Toronto only: transit minutes to Union, weekday 8–9 am, and its tier. |
| `loop`, `loopBand` | Chicago only: transit minutes to the Loop (quickest of five Loop arrival points), weekday 8–9 am, and its tier. Same tier ids as `unionBand`. |
| `homes` | 4 shares (%) of home types, in the order of `card.living.homes.types`. |
| `built` | 4 shares (%) by period built, in the order of `card.living.built.bands`. |
| `lang` | Up to 5 `[language, pct]`, largest first. Demographic: card only. |
| `langMulti` | Toronto only: % naming two or more languages equally. |
| `canopy`, `canopyBand` | Tree canopy: % of the unit's land under tree cover (water left out), from ESA WorldCover 2021 (10 m), and its band `c1`–`c4` (cuts in `cities/<city>/canopy.json`; tier labels in the `canopy` lens). Missing when not fetched. |
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
   `loop` in Chicago); its `key` names the tier field.
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
Chicago: `wards`, `house`, `senate`, `congress` (by number). A missing record means a vacant seat.
Checked weekly. Toronto's municipal election is October 26, 2026; new councillors appear within a
week of taking office (November 15).

Toronto also has `trustees: {board: {wardNum: {candidates: [name, …], winner?, acclaimed?}}}` for
the four school boards (`tdsb`, `tcdsb`, `viamonde`, `monavenir`), from the City's election results
file. `winner` appears once every poll in that ward has reported, or straight away for a ward with
one candidate (`acclaimed: true`). Results are unofficial until the City Clerk certifies them.
Around the election the file is refreshed hourly on election night and daily until November 16.
There are no incumbent trustees in this data: TDSB's wards were redrawn for 2026, so the trustees
in office until November 15 sat on different lines.

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
order, bottom to top, is the table's order.

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
