# Dubai and the Dubai–Sharjah–Ajman area: brief (November 17, 2026)

The user's ask: start Dubai, set inside the Dubai–Sharjah–Ajman metropolitan area, and build it to the same
level of detail as Toronto wherever the data allows. This is the first city run end to end through **Claude Code on
the user's Mac** instead of cloud chat sessions, partly to measure the difference (see "Timing log" at the end).

The brief was written in a cloud session, which can't reach most of these portals. Everything under "Leads" is
from web search and needs checking. Nothing here has been downloaded yet.

## How to work (Mac-specific)
- Work in `~/Developer/layers.city` on the **internal drive**. Don't put anything on the Seagate drive. That drive
  is only for archiving data that's no longer needed (the user moves it himself; CLAUDE.md, "Large raw downloads").
- Fetch directly from the Mac: portals, APIs, Overpass, Wikipedia. Don't route scouting through `scout.yml` or other
  Actions. Actions are only for the recurring refresh jobs the finished city needs.
- Follow CLAUDE.md: work on `main`, `git pull --rebase origin main` before you start and again before each push,
  one change per commit, test in a browser (desktop and phone, light and dark), Notion rows at the end.
- **Build it unlisted** (`"unlisted": true` in `cities/dubai/city.json`) at layers.city/dubai/. No hub row, sitemap
  entry or city-switcher entry until the user says so.
- Stop and ask only for things that are the user's call: a source whose licence is unclear or non-commercial only,
  a download that needs his sign-in, the shape decisions marked **Decide** below if the data argues against the
  default, and anything politically sensitive (see "Care points"). For everything else, take the obvious option,
  note it in FINDINGS.md and keep going.

## Phase 1: scout (write `scouting/dubai/FINDINGS.md`, copy it to the project as claude/dubai-scouting.md if you can)
For each Toronto layer, find the Dubai source and the Sharjah/Ajman source, check its licence and terms, download
a sample, and record the fields, row counts, date and coverage. Use the format of claude/australia-scouting.md:
verdict, how the place differs, layer by layer, licences, content hooks, still open. Keep scripts in
`scouting/dubai/` and raw files in `cities/dubai/raw/` (gitignore anything big).

### Leads to verify
**Dubai Pulse** (dubaipulse.gov.ae, Digital Dubai). This is the main portal. Start with its own catalogue of every open
dataset (`smart_dubai_dubai_pulse_data_catalog_open`). Many datasets show a "Request Permission" button: check
whether the open ones download without an account and whether the Data API needs a key. Read the terms of use
(attribution, reuse, any commercial limits) before building on anything.
- Units: Dubai Municipality `dm_community-open` (planning communities with three-digit codes) and `dm_sectors-open`
  (KML, sectors). Population: Dubai Statistics Center `dsc_population_by_community-open`.
- Known-as names: Dubai Land Department `dld_lkp_areas-open` (the DLD's area names, which differ from DM community
  names; e.g. what people call Dubai Marina versus the DM community name). This is Dubai's version of Toronto's
  known-as layer. Also try OSM place names.
- Transit: RTA `rta_gtfs-open` (7z, updated January 2026: Metro Red and Green, Tram, buses, marine), plus RTA GIS
  layers (`rta_metro_lines_gis`, `rta_bus_routes_gis`, `rta_bus_stops_gis`, `rta_marine_stations_gis`,
  `rta_bicycle_tracks`), `rta_public_transportation_stations`, `rta_taxi_stand_locations`. A community mirror of
  the GTFS is on the Mobility Database (mdb-3359). Check whether RTA's GTFS-realtime (it has fed Google Maps since
  2020) is public, for live times on the Routes page.
- Other DM datasets: parks and beaches, heritage places, Makani entrances (`dm_dmgisnet_enterances`; Makani numbers are
  how Dubai addresses work, a strong card row and a "How addresses work" tour step like Vancouver's).
- Schools: KHDA private schools register (most pupils in Dubai go to private schools). **Drop the ratings and
  enrolment fields at fetch time**, the same as Toronto drops test results. Never rank.
- Libraries: Dubai Culture public library locations (updated November 2025).
- Look in the catalogue for: DHA health facilities (hospitals with an emergency department), mosques
  (IACAD), DEWA EV chargers, RTA paid-parking zones (Parkin), DLD rents and sale transactions (for a lens, see below),
  Dubai Calendar events, land use and master plan, building footprints, beach water quality.

**Sharjah**: Sharjah Digital Department runs the Mada geographic data platform (launched at GITEX 2024). Find out
whether any of it is public. Sharjah RTA (SRTA): look for any published bus GTFS; otherwise use OSM routes. Also
check the federal portals: FCSC open data (opendata.fcsc.gov.ae; some datasets are CC BY 4.0) and Bayanat
(bayanat.ae/en/Geo Data).

**Ajman**: Ajman Open Data portal (Opendatasoft, 400+ datasets, ajman.ae/en/ajman-data). Ajman Municipality *sells*
neighbourhood GIS layers (AED 100 per layer per neighbourhood): that isn't open data, so don't use it. Use OSM
for Ajman's neighbourhoods if the portal has no boundaries.

**OpenStreetMap** covers whatever the portals don't, as in Melbourne: neighbourhood names in Sharjah and Ajman,
main streets, parks, places of worship, campuses, bike lanes, land use.

### Transit facts to build in (check each)
- Dubai Metro Red and Green Lines; Dubai Tram (connects with the metro at Sobha Realty and DMCC); RTA buses,
  including intercity routes into Sharjah and Ajman (e.g. E308 Stadium–Al Jubail since May 2025); marine (abra,
  ferry, water taxi).
- **Transit under construction:** Dubai Metro **Blue Line**, 30 km, 14 stations, about half of it underground,
  linking the Red Line at Centrepoint and the Green Line at Creek. Due to open **September 9, 2029**. Tunnelling
  started May 2026. Use OSM's construction ways and stations or the RTA route map, the same way SRL East was done.
- **Etihad Rail** passenger service: Abu Dhabi–Fujairah since June 30, 2026. Dubai station (Jumeirah Golf Estates)
  and Al Dhaid (Sharjah) were due September 30, 2026: confirm they opened. Sharjah station is due March 30, 2027,
  so it's under construction. Show it like GO trains: regional rail in the regional view.
- Don't show Gold Line, Dubai Loop or high-speed rail ideas unless they have actually started construction.

## Shape (defaults; **Decide** = raise with the user only if the data argues against it)
- Same pattern as Toronto in the GTA, and SF and Melbourne: **Dubai in full detail inside a Dubai–Sharjah–Ajman
  regional view**. City id `dubai`, heading "Dubai", regional scope named something like "Dubai, Sharjah and Ajman".
- **Decide:** what counts as "the city". Default: Dubai's urban area from Jebel Ali to the Sharjah border, not the
  inland desert or the Hatta exclave (frame `view.city` and `view.region` for that).
- **Decide:** units. Default: DM communities as the main unit (like Toronto's 158 neighbourhoods), DLD area names
  as known-as names, DM sectors as the coarse level (like Toronto's former cities and Old Toronto areas).
- Sharjah and Ajman: the regional tier (like the 905), at whatever detail open data allows. Expect mostly OSM.
- Sides/footprint: Deira vs Bur Dubai (the Creek) is the historic split. Then the coastal strip and the newer
  inland districts. Suggest something sensible.

## Toronto parity checklist (fill in Built / No data / Not applicable for each, as in claude/australia-scouting.md)
Boundaries & names: units, known-as names, sectors, landmarks (curated, short), skyscrapers, regional municipalities.
Streets: highways (E11 Sheikh Zayed Road, E311, E611, Al Khail, Emirates Road…), main and collector streets.
Transit: metro, tram, buses by family, marine, intercity buses, Etihad Rail, under construction, Transit nearby,
Routes page, live times if a feed exists, Along the way.
Getting around: bike lanes, bike share (Careem BIKE: check for a GBFS feed and its terms), paid parking zones, EV
chargers, taxi stands.
Places: parks and beaches, sports & rec, libraries & community centres, hospitals with an ER, universities and
colleges (public or nonprofit rules adapted: note that many Dubai campuses are private branch campuses and decide a
fair rule), schools, places of worship, heritage places.
Card: address row (Makani), nearby (800 m), what's here, emergency department, happening nearby.
Pages: Guide + place pages, fact sheets, Routes, Venues, Events, Fun maps.
Lens: see below.
Civic: representatives and where to vote. Probably **not applicable**. The UAE has no municipal elections, and
Federal National Council members are chosen by an electoral college. Confirm and record that, and don't invent a
substitute row.

### Lens and "Living here"
No census like Canada's or Australia's. Use DSC population by community for density. For a housing-cost lens, check
DLD rent contracts and sale transactions on Dubai Pulse, aggregated to median rent and median price per square
metre per area. Only aggregates go into the repo: never individual transactions, plot numbers or party details.
**The rule stands: demographic data never shades the map.** No nationality, ethnicity or religion lens.

## Care points
- Keep the tone factual and neutral. No commentary on the government, rulers or politics, and no "representatives"
  rows for appointed offices.
- Map facilities, never people. Mosques number in the thousands: decide with the data whether a Places of worship
  layer is useful or should show only non-mosque faiths' sites with mosques on a chip (record the reasoning). Halal
  food layer: not applicable (it's the default). Leave kosher out.
- Boundaries: use official emirate and municipal lines. Don't draw or label international borders or disputed
  areas. The regional view stops at the metro area.
- Locale and time: `en-AE`, AED, Asia/Dubai (UTC+4, no DST); the weekend is Saturday–Sunday (government has a
  Friday half-day). English labels for now; keep the Arabic names the sources carry in the raw files. Plain pin logo
  (not the maple leaf). Summer heat matters for "walk to the stop" wording; keep times as they are, add no advice.
- Licences: every non-commercial-only source goes in NONCOMMERCIAL.md and on Attributions (CLAUDE.md "Licence").
  Credit Dubai Pulse datasets as their terms ask. If a source has no licence stated, don't use it; list it in
  FINDINGS.md for the user.

## Phase 2: build
Toronto first is the standing rule for *new features*. Dubai gets existing features only, so there's no conflict.
Build in this order, committing as each layer works, and keep the city unlisted throughout:
1. `cities/dubai/` skeleton from Melbourne's (city.json, region.json, run.sh, SOURCES.md, PARKED.md), units,
   known-as names, landmarks, highways and streets, regional municipalities.
2. Metro, tram, buses, marine, intercity, Etihad Rail, Blue Line under construction, Transit nearby, Routes page
   (live times if a public GTFS-RT exists; add it to `functions/api/arrivals.js` FEEDS like Melbourne).
3. Parks and beaches, sports & rec, libraries, hospitals/ER, campuses, schools, worship, heritage, skyscrapers.
4. Card rows (Makani address, nearby, ER), lens, Guide pages, fact sheets.
5. Venues, Events, Fun maps (suggest Dubai pairings in FINDINGS.md; don't build fun maps without the user).
6. Recurring refreshes: join the grouped workflows (`fetch-places.yml`, `fetch-parking.yml`, `fetch-fun.yml`…, one
   step per city) and add a `fetch-dubai.yml` only for what has no grouped home (CLAUDE.md, "Scheduled jobs").
7. FEATURES.md section for Dubai (marked unlisted, like Hyderabad's), CHANGELOG entry. Leave README and the hub alone
   until it's listed.

Engine changes: keep the engine free of city names. Any change there means rebuilding and checking every city.

## Done means
- layers.city/dubai/ live and unlisted, at Toronto parity for every layer whose data exists, with the checklist
  above filled in FINDINGS.md (Built / No data / Not applicable, with the reason).
- Notion: a Scouting row and a New feature row for Dubai (Cities: Dubai; Status Shipped with "unlisted" in Notes),
  per CLAUDE.md. If Notion isn't connected in Claude Code, list the rows at the end.
- A short report to the user: what's built, what's blocked by data, decisions taken on his behalf, and the timing log.

## Timing log (for the user's Claude Code vs cloud comparison)
Record in FINDINGS.md: start and end time of Phase 1 and of each Phase 2 step, the number of times you had to stop for
the user, and anything the Mac could reach that the cloud sandbox couldn't (direct portal downloads, Overpass, big
files). For comparison: Melbourne was scouted on November 12 and listed November 13 (Events November 14), across
several cloud sessions that relied on Actions and WebFetch for portal access.
