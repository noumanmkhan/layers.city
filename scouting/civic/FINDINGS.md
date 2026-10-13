# Civic rows for v1.2: what the open data supports (October 14, 2026)

Scout: `scouting/civic/scout.py`, run in Actions by `scout-civic.yml` (October 14). Raw output in
`out/` (one JSON per question, `summary.json`, `scout.log`). Nothing here feeds the map.

## Toronto: garbage day — buildable
- **Calendar:** CKAN `solid-waste-pickup-schedule`, resource `pickup-schedule-2026` (OGL – Toronto,
  refreshed yearly, last March 5, 2026). 418 rows: 8 calendars (`Tuesday1`, `Tuesday2`, `Wednesday1`,
  `Wednesday2`, `Thursday1`, `Thursday2`, `Friday1`, `Friday2`), one row per week (`WeekStarting`) with
  T/0 flags for `GreenBin`, `Garbage`, `Recycling`, `YardWaste`, `ChristmasTree`. Covers houses and
  buildings under 9 units with daytime curbside collection.
- **Areas:** the City's GIS layer *Residential Waste Collection Schedule*,
  `gis.toronto.ca/arcgis/rest/services/cot_geospatial21/MapServer/3`: 51 polygons whose `AREA_NAME`
  is the calendar name exactly ("Wednesday1"); `AREA_LONG_CODE` adds the district ("D2WES1"). This is
  the live layer; the CKAN shapefile (`solid-waste-daytime-curbside-collection-areas`, 34 polygons,
  "Tuesday 1" with a space, two "No Collection" areas downtown) dates from 2019 and has no licence: use
  the GIS layer. No licence is stated on the GIS server (same as the voting layers): on the commercial
  re-check list.
- **Card row:** "Collection day: Wednesday · this week garbage and green bin; next week recycling and
  green bin", for spots inside an area; areas outside (downtown night collection, apartments) get a
  short note instead. Calendar must be swapped each January (the 2027 resource appears around March;
  until then, say so rather than guess).
- Also on that service: litter areas, white goods (appliance pickup by day, 4 areas), transfer
  stations (7 points), front-end collection points (3,222, schools and businesses: not for the card).

## Toronto: drop-in programs — buildable, medium
- CKAN `registered-programs-and-drop-in-courses-offering`, resource *Drop-in* (refreshed weekly; last
  September 3 per the catalogue, but sessions run October 8 to November 19, so the rows are current;
  licence "not specified" on the portal). 34,091 sessions: `Location ID`, `Course Title`, `Section`
  (FitnessTO 9,538, Sports 8,043, Swim 6,692, Hobbies 3,089, Early Years 787, Skate 1,493…),
  `Age Min`, `Age Max` (often "None"), date, start/end time, weekday.
- Next 7 days: 6,670 sessions, 1,043 open to children (age max 12 or under, or min 6 or under):
  Recreation Fun and Play with Caregiver, Leisure Swim (incl. Preschool), Indoor Playground, Leisure
  Skate, Tween Zone, Open Gym with Family…
- *Locations*: 1,884 rows (177 with drop-ins), with address parts but **no coordinates**: place them
  on the City's Address Points (as What's changing does) or match to the Parks and Recreation
  facilities already fetched for Nearby.
- Card idea: in Nearby, "Drop-in for kids this week" with the nearest few centres and their next
  sessions (title, day, time, ages), linking to the City's page. A "for kids" / "all ages" pick is the
  natural filter; never a ranking.

## Chicago: no garbage schedule; street sweeping instead — buildable
- No open garbage or recycling day data (only 311 complaints and 2013 recycling areas).
- **Street sweeping 2026:** schedule `u5ai-3efk` (ward + section, month, dates such as "13,14";
  April to November) and zones `2r7q-emq3` (polygons by ward section; map view `nk6s-cie5`), both
  updated June 8, 2026. Card row April to November: "Street sweeping: next Oct 21–22 (Ward 43,
  section 2). Signs go up the day before." The Chicago counterpart of Toronto's garbage day.
- Winter: *Snow Route Parking Restrictions* `i6k4-giaj` (2-inch ban streets) and *Winter Overnight
  Parking Restrictions* `mcad-r2g5` (Dec 1–Apr 1, 3–7 am), both lines last updated December 2021.
  Static but useful; a layer plus a card row when the pin is on or next to one.

## Chicago: Park District activities — buildable, with a data quirk
- `tn7v-6rnw` *Chicago Park District Activities* (updated daily; Terms of Use): 9,801 rows, start
  dates from September 2025 to April 2027; 1,025 starting in the next 14 days, all with coordinates.
  `age_range` is coarse (Youth, Adult, Early Childhood, All Ages…), `activity_type` mostly Instruction
  (registered classes); 242 are `Open` (drop-in-like). Times look shifted: a boot camp reads "1:30am
  to 3am" even in the free-text notes. Check against the Park District site before showing times.

## Beaches — build in the off-season, show from June
- **Toronto:** CKAN `toronto-beaches-water-quality` (102,534 samples since 2007, per site: `beachId`,
  `beachName`, `siteName`, `collectionDate`, `eColi`), 10 beaches, sampled daily June to mid-September
  (last 2026 sample September 16). **No status field**: the advisory ("unsafe for swimming") is Toronto
  Public Health's call and isn't in the data. Don't compute safe/unsafe ourselves; find the feed behind
  the City's SwimSafe page first (the page is WordPress; its status table may come from an API that
  only appears in season). `toronto-beaches-observations`: water temperature, waves, clarity, birds.
- **Chicago:** *Beach Lab Data* `2ivx-z93u` (culture and DNA readings per beach, updated October 8,
  2026). *Beach E. coli Predictions* `xvsz-3xcj` stopped on September 1, 2025; *Beach Swim
  Advisories* `t62e-8nvc` is the 2016 archive. Whether the Park District still publishes advisories
  openly in 2026 needs a check in June.
- Plan: build the layer and card row in winter; switch on when the first samples of the season land.
  Off-season the row says "Swim season is June to Labour Day".

## Snow clearing
- Toronto: nothing on the City's GIS server (no snow, plow or windrow layers) and no CKAN dataset for
  live plow positions. PlowTO's live map isn't open data. Parked.
- Chicago: snow routes and overnight parking bans above (static).

## Suggested order
1. Toronto collection day (card row; optional map layer of the 51 areas coloured by day).
2. Chicago street sweeping (card row April–November; zones layer) plus snow routes.
3. Toronto drop-ins for kids (Nearby). Then Chicago Park District activities once the times are checked.
4. Beaches in winter, live from June, after finding Toronto's advisory feed.
