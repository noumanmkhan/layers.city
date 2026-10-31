# Changelog

## Since 1.1

### San Francisco: regional buses (October 31)
- A *Regional buses* layer under Regional trains: AC Transit's Transbay lines, Golden Gate Transit and SamTrans, from
  OpenStreetMap like Chicago's Pace (no timetables). In the city view, only the routes that stop in San Francisco.
  They also join the card's Transit nearby and the Getting around View.
- Data: three OSM feeds in `cities/sf/surface.json`, fetched weekly with the other routes.

### San Francisco: collector streets (October 31)
- The tier below the main streets (Haight, Sutter, Sacramento, 18th St, Arguello…), 136 streets from OpenStreetMap's
  tertiary roads, under Main streets, from zoom 13, as in Toronto, Chicago, Vancouver, Dallas and New York.
  `cities/sf/collectors.py`, from the main-streets fetch; no new download.

### San Francisco: Where to live, and buses and ferries in Getting around (October 31)
- San Francisco gets the fifth View the other cities have: *Where to live*, housing cost by neighborhood with BART,
  Muni Metro and frequent buses. *Getting around* now also shows frequent and express Muni buses and the Bay ferries.

### San Francisco on Compare (October 31)
- San Francisco joins the Compare page, city vs city and neighborhood vs neighborhood, from its 38 residential
  Analysis Neighborhoods (ACS 2020–2024) with transit minutes to Montgomery St. Its default neighborhood is Noe
  Valley, paired with New York.

### San Francisco: Community Benefit Districts (October 31)
- San Francisco's version of Toronto's BIAs and New York's BIDs: 16 districts where property owners pay for cleaning,
  safety and upkeep on a commercial strip (Union Square, Downtown, Yerba Buena, the Castro, Noe Valley, Japantown…).
  A toggle in Places, a "Benefit district" row on the card ("Union Square BID (since 1999)") and a pill.
- Cultural districts are now plum instead of the shared orange, so the two layers read apart when both are on.
- Data: OEWD's file on DataSF (c28a-f6gs), fetched monthly with the hazard zones (`fetch_extras.py`, `extras.py`).

### Hyderabad: fuller streets, the whole ring road, business parks (October 30)
- Main streets now take every primary and secondary road around the ring road, named or not, so they no longer stop
  and start; tertiary roads are a new Collector streets layer. 341 main streets and 371 collectors.
- The Outer Ring Road draws in full, over the area beyond the city, instead of being cut at the city line.
- Business parks under Landmarks: 25 multi-tenant office and IT parks (Mindspace, Cyber Towers, Sattva Knowledge City,
  Dallas Center, Divyasree Orion, DLF Cybercity, Waverock, Genome Valley...), from zoom 12. No single-company campuses.
- Engine: a highway feature with `"over": true` draws above the mask that greys the area beyond the city; streets
  without a name no longer get an empty hover tip.

### Hyderabad, unlisted: the revenue-track map (October 30)
- A new city at /hyderabad/, kept off the hub. The 35 mandals mostly inside the Outer Ring Road are the units, filled by
  their district; the regional view covers every mandal of the four districts, with a district focus. Known-as names,
  landmarks, PIN codes, main streets, highways, the Metro and the MMTS. No lens (the profile file is empty and the
  lens is marked optional), no constituencies and no representatives yet: the card says why.
- Engine: `outside.muniLabel` names the areas beyond the city on their card ("Mandal"); absent means "Municipality",
  as before. Contract: the `outside` entry in section 4.

### Next scheduled bus when nothing is live (October 28)
- On Where does this line or route go?, a route with no live times because it isn't running (overnight, a
  rush-hour-only route, Lines 5 and 6 before they open) now says when the next one is due from the timetable: "Next
  streetcar at 5:28 a.m.", "Next bus tomorrow at 6:42 a.m.", "Next bus Monday at 6:31 a.m.". While a route is
  running, live times are unchanged.
- Data: the weekly schedule fetch writes `raw/surface/sched.json` (surface.json `"sched"`): for each stop and route,
  the spans of each kind of day it runs in. The page build splits it by stop into 128 small files
  (`docs/toronto/routes/data/sched/`), so the page loads a few kilobytes for the stops on screen, and only when a
  route has no live times. Contract section 15 and `city.json` `transit.sched` for the iOS app.

### Renamed: Where does this line or route go? (October 28)
- With buses, streetcars, subway and LRT on it, "Where does my bus go?" is now "Where does this line or route go?"
  (page title, map panel row, Privacy and Attributions), and its hub row is tagged TRANSIT instead of BUSES.
  The address stays /toronto/routes/.

### Subway and LRT on Where does my bus go? (October 28)
- Stations show as their own cards in the stops near you (Bloor-Yonge Station: Northbound, Southbound, Eastbound
  and Westbound platforms, then its bus bays), each platform with its line's bullet, where it goes and the next
  trains, live from the TTC's subway feed. Stations count from up to 1 km away; a station card is never cut from
  the list.
- Each line gets the same treatment as a bus: a paragraph ("Line 2 towards Kennedy Station starts at Kipling Station
  and runs under Bloor St W, Bloor St E and Danforth Ave… connects with the subway at Spadina Station in the Annex,
  St George Station and Bloor-Yonge Station…"), every station as a step, and a map with each one marked.
  A bus that runs alongside a line (the 34 under Line 5) now says "follows Line 5, with 23 of its stations along the
  way" instead of naming all of them. The station you're at is no longer listed as a connection.
- Lines 5 and 6 show how often they run ("Every 6 min or so"): the TTC publishes no live data for them yet.
- Data: the weekly schedule fetch keeps the subway and LRT apart (`raw/surface/rapid_routes.json`, `rapid_stops.json`,
  each shape with its platforms in order) and now tries backup copies of the schedule: the City's file has been an
  empty zip since October 27, so it currently uses the Mobility Database's archived October 27 copy (service to
  December 21). That also brought in the stop numbers.

### Streetcars on Where does my bus go? (October 28)
- The 16 streetcar routes join the buses: about 500 more stops, red TTC streetcar badges, the route paragraph and
  map, and live times (they were already in the TTC's live feed). Wording now says "bus or streetcar"; the page
  name stays.
- Fix, buses too: a stop that sits near a route in both directions (streetcar tracks down the middle of King,
  bus shapes drawn on a street's centreline) now belongs only to the direction whose side of the street it's on.
  Before, a stop across the street could be offered as the nearest one, and stop counts included both sides
  (the 72 southbound from Don Valley read 51 stops; it's 42).
- Paragraph wording: "the" before district names (the Financial District), stations sharing an area name it once,
  a landmark that is also a station (Union) is said once, and History reads "History (music venue)".

### Live next-bus times (October 27)
- Where does my bus go? shows the next buses for each route at each stop near you, and on the route view
  ("Next buses: 5, 10, 18 min"; italic when the bus hasn't started its trip yet), refreshed every 30 seconds.
- From the TTC's GTFS-Realtime trip updates, read by the site's first server code, a Cloudflare Pages Function
  (`functions/api/arrivals.js`, `/api/arrivals?city=toronto&stops=...`), since the TTC's server doesn't let
  browsers read the feed. The feed is cached 20 s and answers 15 s at the edge; a lean protobuf scan keeps it
  inside the free plan. Privacy and Attributions updated.

### Where does my bus go? (October 27)
- A new page at `/toronto/routes/`, linked from the hub's Toronto card and a new row in the map's Getting around
  group (city.json `pageLinks`: rows in the layer panel that open a page instead of toggling a layer): find stops near you (or an address) and see, for
  each bus and direction, where it ends and its subway connections; pick one for the ride from your stop in order
  (neighbourhoods, main streets along and across, stations, landmarks, the end) and a route map. Stops are
  labelled by side of the street (North side of Overlea Blvd). Built by `engine/routes/build.py` from the TTC
  schedule and the map's published layers; `cities/toronto/routes.json` holds the settings and a short list of
  extra landmarks (malls, civic centres, big parks) placed at the TTC stop that serves them. Buses only for now.
- Each stop shows its stop number (the one on the pole, from the schedule's stop codes) and opens walking
  directions to that exact stop in Apple Maps or Google Maps. Campuses are named by campus (Centennial College,
  Story Arts Centre).
- Loops: a stop near the end of a trip that loops round and leaves again the other way (the 88 inside
  Thorncliffe Park) shows the ride on through the loop ("↻ Loops round first", then St Clair Station), with a
  "stay on" step where the bus turns back, instead of saying the bus ends a few stops later.
- "Takes you through" is now a paragraph for the whole route in the chosen direction, condensed from the same
  data as the step-by-step list: where it starts, its main streets, the regions it crosses, the places it serves
  (the names people use first, like Riverdale), its subway connections (Pape Station in Greektown), landmarks
  and where it ends. The route map tints each neighbourhood it passes in turn and names them, with the
  known-as names (Greektown, Canary District) in italics.
- The paragraph opens with a one-line tag in the TTC's own style ("Don Valley Station to Commissioners St (via
  Pape Station)"; a stop on the route's own street goes by its cross street), and on phones shows its first
  sentence with "More" for the rest.

### Venues: GO fares by station (October 24)
- Toronto venue pages quote the GO fare for each trip from the GTA (Brampton to Scotiabank Arena: GO fare $10.30)
  instead of just "GO fare". The figures are GO's own station-to-station fares from its GTFS
  (`cities/toronto/fetch_go_fares.py`, *Fetch GO fares*, monthly), so they aren't hand-kept. A trip that changes at
  Union onto another GO train is priced end to end, and so is a trip from inside Toronto that ends on GO (Finch to BMO
  Field: TTC to Union, then GO to Exhibition, GO fare $4.40 with the TTC leg free), which used to say only the TTC fare.
  Engine: an optional `fares.railTable` and a `railFareAmt` word.
- Fix: a trip from the venue's own GO station (Cooksville for the Living Arts Centre) now says to walk from it,
  instead of riding to Union and back.

### Chicago: vote centers in the election box (October 20)
- Chicago's election box now lists the three nearest vote centers and marks them on the map, as Dallas's does.
  Until November 2 they are early voting sites (the 50 ward sites and the two downtown sites: "any voter in
  Chicago can vote at any Early Voting/Vote Center site"); on November 3, the 51 election day vote centers
  (the ward sites and the downtown SuperSite; the Board's office is early voting only), beside each voter's own
  precinct polling place, which the Board still doesn't publish. The footer names the ward and precinct and
  points to the Board's lookup for that polling place.
- From the Board of Election Commissioners' Early Voting/Vote Centers page (its table of ward, site and
  address), placed with the Census geocoder, then Nominatim: `cities/chicago/fetch_vote_centers.py`, daily to
  election day in *Fetch Chicago voting places* (`fetch-chicago-voting.yml`, in deploy.yml's list).
- For the iOS app: Chicago's `voting.geojson` precincts gain `k: "chicago"`, and the file gains top-level
  `centers` and `counts`; `card.vote` gains `early`, `counties` and the centers wording (contract sections 3, 5).
  Same format as Dallas's; additive, schema stays 1.

### Line badges instead of stations when zoomed out (October 18)
- Every city's rapid-transit layer (subway, the 'L', SkyTrain, DART) now hides its stations, dots and names alike,
  until zoom 13. In their place each line carries a badge in its own colour: a TTC-style number, New York's letter
  bullets (a trunk's services grouped, e.g. A C E) or a name pill where lines go by colour (Red, Expo). With a whole
  line in view the badge sits near its outer end, the way transit maps mark lines; zoomed in, it is re-placed after
  each move on the line's longest stretch on screen, clear of the panels and other badges, so a line in view always
  says which it is. Labels come from a new `badges` map on the metro layer in city.json (Toronto's line ids are
  already its numbers). Prompted by New York's 461 stations, which buried the city view.

### About link moves to the hub footer (October 18)
- The "How it's built" card is gone from the hub; the write-up at `/about/` is now an About link in the footer,
  beside Privacy, Attributions and Terms. No change to the page itself, the maps or the app's data.

### Sports & rec in Toronto (October 18)
- *Sports & rec* in Outdoors: 592 City parks and community centres with pools, rinks, ball diamonds, sports fields,
  tennis, pickleball, basketball, skateparks or cricket, from the City's recreation facilities list (one row per
  pool tank, ice pad, field and court). A chip per sport; none picked shows them all, picking narrows to places
  with any of them. From zoom 12; a tap lists what's there ("3 ball diamonds, 8 tennis courts…"), the address and
  the City's page. Pickleball comes from the parks list, which has no counts.
- Data: `fetch_nearby.py` also downloads the Facilities and Locations tabs (monthly, with the parks list);
  `sports.py` builds `sports.geojson`. Engine: a `places` feature may list several categories (`cats`), its pin
  taking the first picked one; layer options `narrow` (chips start unpicked) and `search: false`. Credited on the
  Attributions page (the map's credit line already names City of Toronto Open Data).

### Fact sheets: border addresses keep their neighbourhood (October 18)
- The pin is rounded to about 100 m before it is shown or shared, but the neighbourhood used to be looked up from
  the rounded spot, so a building on a border street could land in the neighbourhood across the road (an address
  on the south side of College St came up as University). The neighbourhood now comes from the exact spot; shared
  links keep the `n=` they name as long as the rounded spot could have come from inside it.

### Schools in Toronto (October 18)
- *Schools* in Education: all 817 TDSB, TCDSB, Viamonde and MonAvenir schools, from the Ontario Ministry of
  Education's school list (2024–25). Chips for Elementary and Secondary; a *French programs* row for
  French-language or French immersion (174 immersion schools from the boards' lists, all matched). It replaces
  the two French school toggles; old links that name them open Schools with that program picked.
- Icons from zoom 13; a tap opens the school's grades, board, address and website. Nearby counts elementary and
  secondary schools within 1 km, never a "nearest school" (zoning is set by the board, not distance).
- Data: `fetch_schools.py` (Actions, twice a year) keeps only descriptive columns; `schools.py` builds
  `schools.geojson`. Engine: a `places` layer may have `popup` (details on tap); `replaces` values starting with
  `@` pick a group. Credited on the map and the Attributions page.

### Libraries & community centres; Community & Faith (October 18)
- A new toggle in every city, *Libraries & community centres*, with a chip for each: the public libraries and
  community centres the card's Nearby section already lists, now on the map. Icons from zoom 12, so the city view
  stays clear (about 280 points in Toronto, 310 in Chicago). Search finds them by name.
- The group is renamed *Community & Faith* and the new toggle leads it; Dallas, with no faith data yet, has a
  *Community* group with just this toggle.
- Engine: `engine/community.py` writes `community.geojson` from the Nearby points (called by each city's
  `nearby.py`); a `places` layer may set `minZoom` (12–14) to hold its icons back; library and centre glyphs.

### Fewer toggles: merged place layers (October 18)
- Eleven toggles become three, each with chips to show any mix: *Places of worship* (churches, mosques, Hindu
  temples, synagogues, Buddhist temples, gurdwaras, other faiths; the church families appear as a second chip row
  while churches show), *Halal & kosher food* (halal, kosher) and *Colleges & universities* (universities,
  colleges). The card's Nearby rows follow the chips, search still names each place's kind, and old links that
  name the former layers (`layers=mosques`, `pick=churches:catholic`) open the merged layer with that category.
- Engine: a `places` layer may have `cats` (several categories, a chip each, in the link as `cats=`), `icon`,
  `groupsFor`, `groupLabel` and `replaces`. Data contract schema 2: the old layer ids are gone; migration note at
  the top of the contract. Data files unchanged.

### Layer panel reorganised (October 18)
- Groups now run in the order people need them, the same in every city: Places, Outdoors, Getting around, What's
  changing, Education, Parking & Charging, Representation, Faith & Community, Lenses. The All, Basic and Live tabs
  keep that order; Live is now the What's changing group on its own.
- Moves: universities and colleges out from under Landmarks into a new Education group with the French schools;
  BIAs (and Chicago's SSAs, Dallas's PIDs) into Places; the live layers into What's changing, with Road closures as
  its own row and Special events under it; the neighbourhood and suburban lenses into Lenses; badges under
  Neighbourhoods; the East/West address layer as its own row. The *What's changing* layer is now *New development*.
- Toronto opens quieter: former cities, Old Toronto areas, known-as names and streetcars start off, so the first view
  is neighbourhoods, landmarks, streets, highways, GO and the subway, and the rest are each one click away.

### Parks in Toronto (October 18, on dev)
- An *Outdoors* group with a *Parks* layer, off by default: the City's 1,629 park outlines (Green Spaces, parks
  only), shaded green, with the name on hover. Chips narrow it to parks with a playground, water play (splash pad or
  wading pool), a washroom or a dog off-leash area; several at once means all of them, and the rest fade so the
  green space still reads. Tap a park for what it has and its page on toronto.ca. In the link as `park=`.
- Amenities come from the City's parks list, each entry matched to its outline at build time (`parks.py`: same name
  nearby, else the outline it sits in, else the nearest within 40 m). The City's list names no splash pads or wading
  pools, so those are from OpenStreetMap. Fetched monthly with the Nearby data, which now also rebuilds and deploys
  `parks.geojson`. Engine: the `parks` layer kind; other cities unchanged.

### Special events: the marathon course (October 17)
- The Special events layer draws a race course where the organizer publishes one: a thin line over the closures,
  kilometre marks (every fifth below zoom 14), and start and finish flags, shown until the event ends. First course:
  the Waterfront Marathon, from Canada Running Series' official Garmin course (42.33 km by GPS, marks scaled to
  42.195 km). Credited on the map and the Attributions page.
- Engine: `events.json` organizers take `courses` (GPX, official distance, the dates it applies to); events.py
  adds them to the event as `courses` (additive; contract updated). New pane `evcourse`. Other cities unchanged.

### Special events: closures matched to the police notice (October 17)
- The City's feed filed Saturday's 5K closures as one block from Saturday 3 a.m. to Sunday 5 p.m. and left some
  race-day streets out. `events.json` can now carry *corrections* for an organizer, applied by `engine/events.py` on
  every daily run until they expire: rules that retime or drop the feed's closures, and stretches to add, traced
  along the street centrelines. Changed and added closures say in their popup that the times come from the police.
- Waterfront Marathon, per the Toronto Police release of October 16: setup area from Friday 10 a.m.; Saturday is
  Bay from 4 a.m. and Lake Shore and lower Bay 8 a.m. to 1 p.m. (Front, King, Temperance and the rest dropped);
  Sunday's Bay and Wellington from 4 a.m., Dundas from 6 a.m.; added Fort York Blvd, Dundas from University to Bay,
  Yonge from Dundas to Queen and from Gerrard to College, Bay from Queen to Richmond, and the University-to-York
  ends of Queen, Richmond and Adelaide. A stray laneway off Huron St is dropped. 398 closures.

### Parking in Toronto (October 17, on dev)
- A *Parking* group with three layers. *Green P parking*: the City's 252 car parks from its 2019 open-data list (the
  latest it publishes), squares filled for garages and outlined for surface lots, sized by spaces; spaces, clearance and
  TTC commuter lots in the popup; no rates. *Permit parking areas*: the 97 on-street permit areas, dashed and labelled
  by code. *EV chargers*: 582 public sites (2,802 Level 2 and 257 DC fast ports) from the AFDC station API, the
  listings behind NRCan's locator, plus City-operated chargers it lacks; dots sized by ports, DC fast filled with a
  bolt, temporarily unavailable ones grey; network, hours and price as listed. Chips narrow both point layers.
- The card's Boundaries gain *Permit parking*: the spot's area, then how much of its neighbourhood is inside permit
  areas. A *Permit parking* lens shades neighbourhoods by that share (none, under 25%, 25–75%, 75% or more).
- Engine: layer kind `spots` (points from a shared file picked by `cat`, `mark` `lot` or `charger`, drawn near the
  view from `minZoom`, class chips); `patches` take `cls`/`lcls`; facts rows take `cover`. Colours `--gp`, `--evc`
  (EV charging; `--ev` is special events), `--permit`, `--prk-0`…`3`. Other cities unchanged.
- Data: `fetch_parking.py` and `parking.py`, monthly in `fetch-toronto-parking.yml` (in the deploy trigger list).
  Contract: `parking.geojson`, `permit_areas.geojson`, `permit`/`permitBand` (additive).

### Special events: the Waterfront Marathon (October 17, on dev)
- **Special events** layer (Toronto, under Getting around, in the All and Live tabs): road closures the City's
  Road Restrictions feed flags as special events, grouped into events by organizer, refreshed daily with the
  transit closures (`fetch_closures.py` now also writes `raw/closures/events.json`; new `engine/events.py`;
  `cities/toronto/events.json` names the organizers). Drawn in violet (`--ev`): solid while closed, lighter if
  closing later today, hidden once reopened, rechecked every five minutes. Popups give the times, the event and
  the organizer's closure notice. Curb-lane-only closures are dotted.
- **Event view and banner:** while a big event is on (from three days before until its last closure ends), it is
  the first entry under Views (main and collector streets, highways and the event, framed on its closures), and a
  banner on the first visit offers it. Taking the view or closing the banner is remembered per event.
- First event: the TCS Toronto Waterfront Marathon, October 16–18, 403 closures (Canada Running Series).
- Data contract: new optional file `events.geojson` and layer kind `events` (additive).

### Vancouver and Dallas on the maps hub (October 16)
- Both cities are announced: cards on the maps hub (with outline thumbnails; Vancouver's includes the University
  Endowment Lands), `unlisted` and `inSwitcher` dropped, place pages (`/vancouver/local-areas/`, `/dallas/zip-codes/`)
  and sitemap entries, and a guides line for all four cities. The hub's refresh notes name TransLink and DART.
- Attributions: Vancouver and Dallas each have their own section; the shared one is now "Used for every city".
- Place pages: a unit that isn't one of the city's own (Stanley Park, the University Endowment Lands) says what it is
  and isn't counted in the index title; a ZIP with no median home value no longer stops the build.

### University Endowment Lands in Vancouver's city view (October 16, on dev)
- The Point Grey lands west of the city (UBC's campus, Pacific Spirit Regional Park and the UEL neighbourhoods, the
  Point Grey piece of Metro Vancouver's Electoral Area A) are part of the city view as *University Endowment Lands*:
  never masked, an olive tint and dashed outline, searchable as UEL or UBC Endowment Lands. They get the city's level
  of detail where data exists: a unit of their own (24) with Living here figures from the 2021 Census (placed against
  the 22 local areas' tiers without moving them, never ranked in the facts), transit time to Waterfront, tree canopy,
  main and collector streets, landmarks (Museum of Anthropology, Chan Centre, Pacific Spirit Park, Wreck Beach, UBC
  Botanical Garden, Nitobe Garden), University Village and Wesbrook Village, buses and Transit nearby, Mobi, bike paths
  and lanes and Nearby parks, playgrounds, courts and community centres (OpenStreetMap, since the City's data stops at
  its line), places of worship, provincial and federal ridings, and card rows saying who runs it and where it votes.
  Not there: the City's own data (permits, heritage, BIAs, the civic election), which doesn't cover it; the card says so.
- Engine: `base.geojson` kind `annex` (inside the footprint, unmasked, `--annex` colour); facts rows `skipEmpty`;
  search uses a feature's `aka`; profiles marked `apart` are never ranked; `bikes.json` `extra` and `extraClip`.
  Other cities have none of these, so they look the same.

### Vancouver, Toronto's features (October 16, on dev, unlisted)
- *Places*: universities, colleges and hospitals (curated: UBC, SFU's Harbour Centre campus, Emily Carr; Langara, VCC,
  BCIT downtown; VGH, St. Paul's, Mount Saint Joseph, BC Children's and Women's, UBC Hospital, with their emergency
  hours or ages), skyscrapers at 100 m and up (72 built and 1 under construction, from Wikipedia), heritage districts (Gastown, Chinatown and
  Yaletown historic-area zoning, and First Shaughnessy), 680 municipally designated heritage buildings, CSF
  French-language and VSB French immersion schools, the suburban drive lens (to Waterfront Station) and a tree canopy
  lens and card row (ESA WorldCover).
- *Getting around*: collector streets, the City's bikeways (protected, painted, local-street bikeways, off-street
  paths), Mobi stations and a Mobi row in Transit nearby, What's changing (issued building permits: Vancouver
  publishes no development applications, so every item is Approved), and transit under construction: the Broadway
  Subway (six stations) and, in the regional view, the Surrey Langley SkyTrain.
- *Representation*: BC provincial districts and federal ridings cut to the city line (federal shaded by party), and
  the 22 BIAs, with pills and card rows. MPs on the card; the mayor, council and MLAs follow the October 17 and 24
  elections. *Faith & Community*: places of worship (churches in the city, other faiths across Metro Vancouver).
- *Card*: Nearby (library, community centre, emergency department, parks, playgrounds, tennis, off-leash areas),
  Changing nearby, and an election-day box for October 17 (any voting place in the city; the nearest three).
  *Views*: Explore downtown, Know your city, Who represents me, Where to live, Getting around.
- Not built, with reasons: `cities/vancouver/PARKED.md` (collection day, halal and kosher shops, road closures,
  development applications; wards and region focus don't apply).
- Engine: `bikes.json` `subField`; Vancouver's register, permits and heritage names; `construction.json`
  `unnamedIn` and SkyTrain stops under construction; `skyscrapers.json` `min` (and a geocode is used only while its address is listed); Opendatasoft sources in the bike,
  heritage and permit fetchers. New jobs: *Refresh Vancouver representatives* (weekly), *Fetch Vancouver places*
  (monthly). Other cities' output unchanged.

### Vancouver and Dallas in the city switcher (October 16, on dev)
- Vancouver and Dallas now appear in the city switcher on every map (Toronto, Chicago, Vancouver, Dallas). They stay
  `unlisted`: still no maps hub card and no sitemap entry. A new optional `"inSwitcher": true` in `city.json` lets an
  unlisted city into the switchers; `engine/assemble.py` honours it, and the contract notes it (additive, no schema bump).

### Chicago: Pace buses and Faith & Community (October 16, on dev)
- *Pace buses*, a `regional` layer under Metra like Toronto's GO buses: 134 routes, the whole network in the
  Chicagoland view and the 49 that stop in Chicago in the city view, numbered "Pace 270" (Pulse lines by name), in a
  deep teal (`--pace`). A *Pace buses* row in Transit nearby, and Pace in the Getting around view. Pace's own GTFS is
  offered "for non commercial use", so routes and named stops come from OpenStreetMap's route relations instead
  (`engine/osm_routes.py`, a surface.json feed with `osm` in place of `gtfs`, refreshed by the weekly bus job). No
  timetable in OSM: Pace routes have `day: true` and no frequency. Three routes with no ways in OSM are left out.
- *Faith & Community*, Toronto's nine toggles: 2,311 churches inside the city with chips for Catholic, Baptist,
  Methodist (with the AME churches), Lutheran, Episcopal, Presbyterian, Orthodox, Evangelical and Other; mosques (72),
  synagogues (113), Hindu temples (20), Buddhist temples (28), gurdwaras (2) and other faiths (53) across Chicagoland
  (most gurdwaras and mandirs are in the suburbs); 63 HMS-certified halal stores and 7 cRc-listed kosher grocers and
  bakeries. Nearby rows for each while its layer is on. `cities/chicago/fetch_faith.py` keeps a geocode only when it
  names the house number and town (Census geocoder as a fallback), and `.github/workflows/fetch-chicago-faith.yml`
  refreshes it monthly.
- Not built: a garbage-day row. Chicago publishes no garbage collection days; the only open recycling data is the
  2013 service areas, and blue-cart weeks hang on each home's garbage day. Street sweeping stays the card's row.
- Engine: `surface.py` takes a route's `day` from the feed when it has no schedule, and keeps shorter new stretches
  for OSM routes. Other cities' transit output unchanged. Contract sections 3, 4 and 5 (additive).

### November 3 ballot on the card (October 16, on dev, Chicago and Dallas)
- Under each state representative, state senator and U.S. representative, the card lists that district's candidates
  on the November 3 ballot with their party (R, D, L, G), in ballot order, under a caret; one candidate shows as
  "Unopposed on the ballot". The sitting member is marked "running again", "not running again", or where they are
  running instead (Chicago's Rep. La Shawn Ford, House 8: "running for Congress, IL-7"). Staggered state senate seats
  that aren't up say "seat not on the ballot this year". U.S. Senate and Governor rows follow, statewide.
- Dallas's congressional row keeps the member for the district they were elected on and names the new district the
  spot votes in ("2 candidates for the new TX-33").
- Rows disappear after election day: there is no results feed for these races yet.
- Sources: Chicago, the Board of Elections' candidate list already fetched for the school board (status Sept. 11);
  Dallas, Dallas County's countywide sample ballot (new `fetch_ballot.py`), read by OCR in `ballot.py` and checked by
  eye against the PDF. Districts reaching the city only outside Dallas County (about 4% of the city) show no race.
- Engine: `engine/ballot.py` (race tables, name matching for `runs`), `card.reps.ballot`, `race.layer/key/text/kind`,
  `ballot` offices (contract sections 7 and 8, additive). Toronto unchanged.

### Election view for city wards (October 16, on dev, Toronto)
- Until the new council takes office (November 15), switching on City wards turns on an *Election view*: every ward
  in one neutral violet (no party's colour), standing in for the area fills, the lens and party colours as party
  shading does, and taking precedence when a view turns on several riding layers. Its tick is under the layer's row.
- Ward labels become a bold violet chip (just the number at the whole-city zoom, so all 25 fit); from zoom 13 the
  chip carries the election date, the incumbent ("not running" for the four who aren't: Wards 4, 11, 14 and 19)
  and the number of candidates. After election day they say votes are being counted, then name the winner.
- Tapping a ward opens the card on Representatives alone; the councillor row keeps the incumbent and lists the
  candidates under a caret, like the trustee rows.
- Mayor: a Mayor row heads Representatives on every card (Olivia Chow, linked to her page on toronto.ca, "running
  again"), with the 53 mayoral candidates under a caret in ballot order, no one highlighted. The election view's
  note adds "Also on the ballot: Mayor, 53 candidates". Lists longer than 8 names open as a two-column grid across
  the card; in the election view Representatives moves to the top of the card's sections.
- Incumbents running elsewhere are named as such, on labels and the card: Brad Bradford (Ward 19) "running for
  mayor", Dianne Saxe (Ward 11) "running in Ward 14". Perks and Fletcher stay "not running".
- Data: `representatives.json` gains `mayor`, `mayorRace` and `incumbentElsewhere` (the fetch job now also reads
  the Mayor's page title), and `council` (candidates, `incumbentRunning`, winner) from the City's results
  file, which the weekly job already fetches. Config: `election` on outline layers, `race` on a card office
  (contract sections 4, 7 and 8, additive).

### Colour by party (October 16, on dev, Toronto, Chicago and Dallas)
- Riding layers can be shaded by the sitting member's party: Toronto's provincial and federal ridings, Chicago's
  Illinois House and congressional districts, Dallas's Texas House and Senate districts. On when the layer goes on,
  with a *Colour by party* tick and a key with seat counts under its row. Red, blue, orange and green tints (new
  palette keys `--pty-*`), grey for a vacant seat, clear where the table has no member.
- One layer at a time: the most recent wins; a link or view with several picks the national level. Shading switches
  the area fills and the lens off and brings them back when it ends; switching a fill or the lens on ends it.
  Shaded lines use a contrasting edge on a halo. Links write `party=<id>` or `party=none` only when the shading
  differs from that default.
- Config: optional `party` on outline layers and a top-level `party` block (contract section 4). No data changes:
  parties were already in `representatives.json`. Dallas's congressional districts wait for January (members sit
  for the old lines). City wards stay uncoloured (nonpartisan).
- Fixed (Dallas): Texas House, Senate and congressional districts are now cut to land, so their party colours no
  longer tint the lakes. A new optional `maskWater` file (`lakes.geojson`) lets the city view's mask paint lakes
  beyond the city as water, so district edges along their shores don't show through.

### Dallas, Toronto's features (October 16, on dev, unlisted)
- Landmarks (29), universities, Dallas College campuses and ERs (IPEDS and CMS, public and nonprofit only),
  skyscrapers (Wikipedia), the City's 21 landmark historic districts, 13 public improvement districts (a layer, a pill and a card row, like Chicago's SSAs), collector streets, bike lanes (the City's
  completed bike facilities), DART bus routes and a Transit nearby section, a *To downtown* transit lens (DART
  schedules, r5py), tree canopy (ESA WorldCover), the suburban drive lens, Collection day (garbage and recycling
  weekday, brush and bulky trash week), school districts and Dallas ISD trustee districts (a `boards` layer and a
  School district row), Nearby (libraries, recreation centers, ERs, pools, dog parks; parks, spray grounds,
  playgrounds and tennis courts within half a mile), representatives (council, Texas House and Senate, Congress)
  refreshed weekly, views and a tour. DART station names in title case.
- Engine: an office in `card.reps` can name a polygon `file` the card checks but the map doesn't draw (Dallas's
  members of Congress sit for the 2021 lines until January); `surface.json` `stopNames` tidies capitalised stop
  names; `fetch_bikes.py` reads ArcGIS layers. Other cities' output unchanged.
- Not built, with reasons: `cities/dallas/PARKED.md`.

### Dallas, voting first (October 15, on dev, unlisted)
- A new city, live only at /dallas/ (marked `unlisted`: no hub card, not in the other maps' switchers), in the same
  shape as Toronto and Chicago: the City of Dallas inside a Dallas–Fort Worth regional view of nine counties
  (Dallas, Tarrant, Collin, Denton, Rockwall, Ellis, Johnson, Kaufman, Parker), with county focus.
- Dallas has no official neighbourhoods, so its units are the ZIP codes people use (Census ZIP Code Tabulation
  Areas, clipped to the city) and its eleven areas group them (a first draft for local review: Downtown & Uptown,
  East Dallas, Lake Highlands, North Dallas, Far North Dallas, Northwest Dallas, West Dallas, Oak Cliff, South
  Dallas, Southern Dallas, Pleasant Grove). Known-as names (Deep Ellum, Bishop Arts, Uptown, Lakewood…), main
  streets, highways, DART light rail, the Silver Line and the TRE, council districts, Texas House and Senate
  districts, congressional districts (the 2025 map used in 2026) and counties. A ZIP lens (housing cost, renters
  and owners, housing type) and Living here from the 2020–2024 ACS; ZIPs mostly in another town carry no figures.
- Where to vote, in a new form: Dallas, Tarrant and Collin counties run vote centers (vote at any one in your
  county), so the box lists the three nearest early voting sites until early voting ends (October 30), then the
  three nearest election day vote centers, with marks on the map. Denton County assigns a polling place by
  precinct: the box shows it on election day, and its early voting sites before. It shows on cards in the suburbs
  too. Sources: Dallas County's Vote Center Finder layer, Tarrant County's lists (placed by the Census geocoder,
  then Nominatim), Collin County's polling-locations API and Denton County's polling-locations and precinct layers,
  refreshed daily by *Fetch Dallas voting places*.
- Texas House, Texas Senate and congressional districts are drawn across all nine counties (October 15), and a
  card in the suburbs lists them under Boundaries, with the congressional pill (new optional `card.outsideFacts`).
  Council districts, areas and ZIP codes stay Dallas only.
- Fixed: a tap or search in a suburb listed after an empty town shape (Hebron near Dallas; Coquitlam 1 near
  Vancouver) found nothing; the engine now skips empty shapes.
- Engine: `card.vote.counties`, `early`, `centersLead`, `earlyLead`, `centersMore`, `earlyMore`, `precinctEarly`,
  `precinctNote` (contract section 5, additive); the vote box now also shows outside the city; Living here shows a
  figure without a tier when the city has no lens for it (Dallas has no getting-to-work lens: nearly everyone drives).

### Thirteen more neighbourhood drawings (Toronto, October 15)
- Kensington-Chinatown (market houses with awnings, produce, a bicycle), University (the ROM's Crystal, University
  College), Cabbagetown-South St.James Town (Victorian cottages, Riverdale Farm's barn), Fort York-Liberty Village
  (blockhouse and earthworks, a sawtooth factory and chimney), Rosedale-Moore Park (a ravine bridge), South Riverdale
  (Leslieville semis, the Leslie Street Spit lighthouse), Downsview (a hangar and a turboprop), York University
  Heights (a domed rotunda, campus blocks, a subway canopy), Willowdale West (North York Centre's towers, the civic
  centre, Mel Lastman Square's arcade), Kingsway South (the Old Mill bridge), Junction Area (main-street storefronts,
  a freight train), Cliffcrest (the Bluffs and a sailboat) and Morningside Heights (zoo animals). 23 in all.
- Each landmark was checked against the neighbourhood polygons first: the St. James Town towers, the Don Jail,
  the West Toronto Diamond and Mel Lastman Square sit in neighbouring units, so those drawings use what is inside
  instead (Mel Lastman Square's drawing went to Willowdale West, where it is). The Bluffs moved from Guildwood's
  drawing to Cliffcrest's; Guildwood now has trees beside Guild Park's columns.
### Bike Share stations (Toronto, October 15, on dev)
- New toggle "Bike Share stations" indented under Bike lanes, off by default: every Bike Share Toronto station
  (1,074 on October 15) as a small ringed dot from zoom 12, filled lime where it charges e-bikes (52). Tap a
  station for its name, number of docks, e-bike charging, and whether the kiosk takes credit cards (541 don't:
  unlock with the app or a member key). No live counts of bikes or free docks: they change by the minute.
- The card's Transit nearby section gains a "Bike Share" row: the nearest station within 500 m, how far, its docks
  and whether it charges e-bikes ("No station within 500 m" otherwise), whether or not the layer is on. Config
  `card.transit.bikeshare`; the file loads after the map.
- Data: Bike Share Toronto's GBFS feed (Toronto Parking Authority; linked from the City's open data portal, no
  licence stated), fetched weekly by `engine/fetch_bikeshare.py` in *Fetch bike lanes* (now weekly, Thursdays),
  built by `engine/bikeshare.py` into `docs/toronto/data/bikeshare.geojson` (~150 KB; loaded when the layer is
  first turned on).
- Engine: layer kind `docks` (`minZoom`, `countNote`, popup texts in `city.json`); new colour `--dock`.
  Contract sections 3 and 4 (additive, schema 1).

### Faith & Community order (Toronto, October 15)
- The group now runs Churches, Mosques, Hindu temples, Synagogues, Buddhist temples, Gurdwaras, then Other faiths.
  Halal grocers & butchers sit under Mosques and Kosher grocers, butchers & bakeries under Synagogues (`under`),
  shown indented as the Landmarks toggles are. Drawing order on the map is unchanged. For the iOS app: only the
  order and `under` in `city.json`.

### Toronto starting layers (October 15, on dev)
- First load and Reset now show Neighbourhood badges and Collector streets, and no longer show Universities,
  Colleges, Hospitals or Skyscrapers (still under Landmarks, off). The rest is as before: Former cities, Old
  Toronto areas, Neighbourhoods, Known-as names, Landmarks, Main streets, Highways, GO trains, Subway & LRT,
  Streetcars. Links that list their layers are unchanged. For the iOS app: only the `on` flags in `city.json`.

### Neighbourhood badges (Toronto, October 15, on dev for review)
- New toggle "Neighbourhood badges" under Places, after Neighbourhoods, on at first load. Ten neighbourhoods get a
  one-colour drawing of what they're known for (Harbourfront-CityPlace, Thorncliffe Park, Wellington Place,
  Yonge-Bay Corridor, Casa Loma, St Lawrence-East Bayfront-The Islands, The Beaches, High Park-Swansea, Humber Bay
  Shores, Guildwood), laid like a watermark: faint, with no background or text (the neighbourhood label names the
  place), turned to run parallel to Steeles Ave like the city's grid.
- Each drawing is sized to 70% of the largest box of its shape, turned the same way, that fits inside its
  neighbourhood, so it never spills into a neighbour. It sits over the street lines and under the outlines and
  every label; knockouts are masked out so the map shows through.
- Engine: layer kind `badges` (`align` names the street to turn to; `scale`, `opacity`, `minWidth`, `maxWidth`),
  `engine/badges.py` (drawings in `cities/<city>/badges/*.svg`, optional `places.json` to keep a badge on one part of
  a multi-part neighbourhood) → `docs/<city>/data/badges.json` (~20 KB). Contract sections 3 and 4 (additive, schema 1).
- A first version also fitted every other neighbourhood's name as a text label; dropped after review.

### Bike lanes (Toronto and Chicago, October 15)
- New toggle "Bike lanes" under Getting around, after Bus routes, off by default: each city's bike network, one line
  per segment: protected lanes lime (`--bike`), painted and shared a darker olive green (`--bike-2`), trails brown
  (`--bike-trail`); yellow-greens so they don't read as Line 2's green or as water. Chips, any mix: Protected, Painted, Shared,
  and Trails (Toronto). Protected and Painted are on at first; links write `bike=` when that changes.
- Tap a stretch: street, type ("Two-way cycle track"), the streets it runs between, the year installed (Toronto).
- Data: Toronto's Cycling Network (CKAN, 1,581 segments) and Chicago's Bike Routes (hvv9-38ut, 1,008 segments, no
  off-street trails), fetched monthly by `engine/fetch_bikes.py` (*Fetch bike lanes*), built by `engine/bikes.py`
  into `docs/<city>/data/bikes.geojson` (Toronto ~580 KB, ~120 KB gzipped; loaded when the layer is first turned on).
- Engine: layer kind `bikes`; drawn in the highway pane so a tap reaches the lane rather than the neighbourhood
  under it. Contract sections 3 and 4 (additive, schema 1).

### Panel groups fold, in a new order (all cities, October 14)
- Groups run Places, Getting around, Representation, then Faith & Community (Toronto). Drawing order on the
  map is unchanged.
- Tap a group's heading to fold it away; layers that are on stay on, and the folded heading says how many
  ("9 on"). Folded groups are remembered in the browser per city (localStorage `groupsFolded-<city>`); a tour
  step opens any folded group whose row it points out. Counted as `group_fold` / `group_open` events.

### A shorter panel header (all cities, October 14)
- Views is now a dropdown on one line instead of a chip row, so a 1080p screen shows at least six layer
  toggles (four before). Once the map changes after a view it reads "Custom (from …)"; picking the view again
  goes back to it. A picked view still shows its note and, for Who represents me, the boundary chips.
- The extent switcher shows names only (Greater Toronto Area / Toronto, Chicagoland / Chicago, Metro
  Vancouver / Vancouver); the "416 + 905"-style sublines and their `scope.*.sub` config are gone.
- The footer buttons (Reset, Hide all, Share, Image, Tour) fit on one row.

### Churches by denomination (Toronto, October 14)
- The Churches toggle gets a row of chips: All · Catholic · Anglican · Baptist · United · Presbyterian · Orthodox ·
  Evangelical · Other, one at a time, with a count. No new toggles. Families come from the OSM denomination, or
  the church's name when OSM has none (260 untagged became 168); those left show under All only.
- Engine: any `places` layer can take `groups` (chips, `grp` per feature); the pick is kept in shared links
  (`pick=`), and the card's Nearby row follows it ("Church · Orthodox").

### Faith & Community layers (Toronto, October 14)
- New panel group with nine toggles, all off by default: mosques, gurdwaras, synagogues, Hindu temples, Buddhist
  temples, churches, other faiths, halal grocers & butchers, kosher grocers, butchers & bakeries. One file,
  `docs/toronto/data/faith.geojson`, built by `cities/toronto/faith.py`.
- Places of worship: every named one in OpenStreetMap, one point per place, with denomination where tagged.
  `faith_overrides.csv` adds, fixes or drops places OSM gets wrong; first fix: the Islamic Society of Toronto
  (Masjid Darussalam) moved to its new building at 20 Overlea Blvd, and its duplicate pin dropped.
- Shops: 20 HMA-certified halal stores and 19 COR-certified kosher shops, hand-curated in `faith_shops.csv`
  (independents only; Real Canadian Superstore and Sobeys counters, an Edmonton listing and a wholesale bakery
  left out; Kosher City Plus and Isaac's KCP Bakery share one point). Placed with Nominatim.
- New fetch job `.github/workflows/fetch-toronto-faith.yml` (Overpass and Nominatim, monthly and when the
  script or a list changes on main).
- Engine: new icons and colours for these categories; a Nearby `nearest` row can name a layer as a third item
  and then shows only while that layer is on (the open card redraws when it changes). Other cities unaffected.
- Attributions credit HMA and COR; app contract documents `faith.geojson` and the Nearby rule.

### "How it's built" page replaces the source-code card (October 14)
- The hub's third card linked to the GitHub repo, which is going private. It now opens `docs/about/`, a
  write-up for readers such as employers: the problem, the principles (describe don't rank, current or not at
  all, private by design), the architecture (sources, scheduled jobs, geometry pipeline, static site, web and
  iPhone), keeping it current, and how it was built with AI. The "Not a snapshot" panel no longer points to
  public commits. Added to the sitemap. No change to the maps or the app's data.

### Hosting moved to Cloudflare Pages (October 14)
- layers.city is now served by Cloudflare Pages instead of GitHub Pages. `.github/workflows/deploy.yml` uploads `docs/`
  with Wrangler (direct upload) on pushes to main and after the fetch jobs that update published data; a newer
  deploy cancels one still running. www.layers.city redirects to layers.city with a Cloudflare redirect rule, and
  maps.noumankhan.ca keeps its 301. `docs/CNAME` and `docs/.nojekyll` are gone. URLs and data files are unchanged,
  so the iOS app needs nothing new; files are now revalidated on each request instead of cached for about ten
  minutes. Privacy page updated (hosting section).

### Licence and terms of use (October 14)
- The code is no longer MIT-licensed: `LICENSE` is now © 2026 Nouman Khan, all rights reserved, covering the code,
  page designs and written content. Versions published before October 14, 2026 keep their MIT licence. Open data
  keeps its own licences (OpenStreetMap-derived data stays ODbL, Wikipedia-derived text CC BY-SA), and
  "Layers.City" and the pin logo are named as trademarks.
- New hand-written page `docs/terms/` (Terms of use): what visitors are welcome to do (use the maps, share links,
  screenshots and saved images with their credit line) and what they aren't (copy or re-host the site, reuse its
  code or content, bulk-download files to power another service, use the name or logo). Linked from the hub,
  Privacy and Attributions footers and the place pages, and added to the sitemap. No change to the published data
  or the app contract.

### Directions in your maps app (October 14)
- The card gives straight-line distances; now a directions button hands a place to the visitor's own maps app
  for real routes and travel times. It sits in the card header (the pinned spot, searched address or landmark),
  in the vote box (the voting place) and beside each place in Nearby (library, community centre, emergency
  department). It opens Google Maps directions; on an iPhone, iPad or Mac it first offers Apple Maps or
  Google Maps. Plain links, starting from wherever the visitor is; nothing is sent until they pick. Optional
  `directions` text in city.json (`title`, `google`, `apple`, `pick`). Website only; apps may ignore it
  (on iOS, MapKit can open Apple Maps directly).

### Collection day and street sweeping on the card (October 14)
- **Toronto: Collection day.** A Boundaries row gives the spot's collection day and the next two pickups with
  what goes out ("Thu, Oct 15: Green bin, recycling"), from the City's live collection areas (51, matched by
  calendar name) and the yearly pickup calendar. Outside the curbside areas (apartments and buildings with 9 or
  more units, parts of downtown) it says so. Fetched monthly; a new year's calendar arrives on its own once the
  City publishes it (usually by March), and until then the row says the calendar has run out.
- **Chicago: Street sweeping.** A Boundaries row gives the ward section and its next sweeping dates, April to
  November, from the City's 2026 sweeping zones and schedule; nothing shows out of season or where there's no
  zone (the Loop).
- Engine: one generic "pickup" row (`card.pickup`) and file kind, so other cities can add any service that
  comes on set dates to set areas. For the iOS app: contract sections 3 and 5. Additive.

### All / Basic / Live, and road closures on the card (October 14)
- **Panel tabs.** The layer list now has three tabs: All, Basic (data that rarely changes: census, boundaries,
  landmarks, routes) and Live (refreshed from city feeds every day or week). They only filter the list; layers
  that are on stay on. Toronto and Chicago mark What's changing, Transit under construction and Road/Street
  closures as live (new optional layer key `live`). Live rows show how fresh their data is ("As of Oct 14"), in
  red once older than `staleDays`. Vancouver has no live layers yet, so no tabs. Picking a View or starting the
  tour switches back to All. Contract section 4. Additive.
- **Road closures on the What's here card** (both cities): a new section (`card.closures`, id `cls`) lists
  transit-construction closures and lane restrictions within 500 m (Chicago ½ mile) with permit dates, hours,
  project and distance, whether or not the layer is on; left out when there are none. Contract section 5.
  Additive.
- **Skyscrapers:** the hover tip on a tower under construction adds its expected year (the card already shows it).
- **Daily closures job fixed:** GitHub had been starting the scheduled runs about seven hours late, so the
  midnight-hour check skipped every run and closures stopped at October 10. A scheduled run now fetches unless
  today's file is already built.

### Brand colours on the maps (October 14)
- The map's accent changed from purple to the Layers.City red (#C8102E; #E5364F in dark mode): the pin, the
  layer toggles, buttons, the vote box and the card's highlights. Canadian cities are red and white. US cities
  are red, white and blue: Chicago's `city.css` sets a new `--accent-2` to blue for the panel's toggles,
  checkboxes and tour, while pins and buttons stay red. Compare's second pin (B) moved from orange to teal so it
  stays easy to tell from the red A. For the iOS app: `palette["--accent"]` has the new
  values; read `--accent-2` for toggles and fall back to `--accent` (contract section 4). Additive.

### New address (October 12)
- The site moved to **https://layers.city/** (GitHub Pages custom domain). maps.noumankhan.ca now 301-redirects
  there at Cloudflare, keeping the path and query string (and the browser keeps the `#` part), so old links and
  bookmarks still work. For the iOS app: change the data base URL to `https://layers.city/<city>/data/<file>`
  (contract section 1). The old URL keeps working through the redirect, at the cost of one extra hop.
- **One name: Layers.City** (October 12). The maps are no longer "Toronto Layers" and "Chicago Layers": `title` in
  city.json is now "Toronto · Layers.City" (browser tab, shared links, image names), and a new optional `heading`
  ("Toronto") is what the panel heading and city switcher show, under the Layers.City logo. Additive for apps
  (contract section 4): show `heading` where a city name fits, or keep showing `title`.

### Vancouver (in progress, unlisted)
- **First build** (October 11): maps.noumankhan.ca/vancouver/, kept out of the other cities' switchers and the
  maps hub (`"unlisted": true` in its `city.json`) until it's announced. Downtown / West Side / East Side, the
  City's 22 local areas (plus Stanley Park, which belongs to none of them), known-as names, landmarks, main
  streets, BC highways, SkyTrain and SeaBus, the West Coast Express, and a local area lens with Living here
  rows from the 2021 Census (dissemination areas summed into local areas; the City publishes no 2021 local-area
  profiles). Representatives come after the October 17 civic and October 24 provincial elections. For the iOS
  app: `la_profiles.json`, a unit with `park` and no profile; contract sections 3 and 4. Additive.
- **Bus routes and Transit nearby** (October 11): all 232 TransLink bus routes in families (8 frequent;
  15 express: RapidBus R1–R6, the 99 B-Line and routes named express; 5 overnight NightBus), stops from zoom
  15, and the card's Transit nearby section (nearest SkyTrain or SeaBus station, buses within 400 m, NightBus).
  `surface.json` gains `expressRoutes` (express by route number) and `stripZeros` (TransLink pads numbers:
  002 is shown as 2). Fetched weekly with the other cities. For the iOS app: `transit.json`,
  `transit_routes.geojson`, `card.transit`, as in Chicago.
- **To Waterfront** (October 11): the transit-time lens, card row and *Narrow it down* filter, like To Union and
  To the Loop: r5py on TransLink's schedules from 753 points in the 22 local areas, weekday 8–9 am, to Waterfront
  Station (`cities/vancouver/fetch_transit_waterfront.py`, fetch-transit-waterfront.yml). 15 min (Downtown) to
  48 (Dunbar-Southlands). Profile fields `waterfront`, `waterfrontBand`.
- **How addresses work** (October 11): a layer under Main streets, *Ontario St: East and West* (Ontario Street,
  Carrall Street downtown, and the main streets that take W or E), an Address row on the card (side, and south of
  False Creek the spot's block numbers, read off the City's street blocks: "About 5600 on north–south streets,
  1500 W on east–west ones"), and a tour step. Engine: the divide type takes `also` (more dividing streets),
  `prefix` (W/E before the name) and `axes` (block numbers); `card.address.blocks`. Contract section 3.
- **Engine**: a unit with no figures takes no lens fill (it showed Leaflet's default blue); `assemble.py`
  leaves `unlisted` cities out of the other cities' switchers. Toronto and Chicago look the same.

### Both cities
- **No zoom when tapping search on iPhone** (October 12, all cities): on touch screens the search box and the
  Focus picker use 16px text, so iPhone Safari no longer zooms the page in when they're tapped. Pinch-zoom
  still works. Desktop sizes unchanged.
- **Buses in each agency's own colours** (October 12): Toronto follows the TTC: streetcar numbers red with
  white text, bus numbers white with a red outline (frequent and regular alike), express green, Blue Night
  white with a blue outline; bus lines charcoal as on TTC route maps, express green (dashed when shown with
  other families), overnight blue. Chicago follows the CTA's bus map legend: local numbers dark grey, express
  red, X routes white with a green outline and green lines, the J14 Jump blue, Owl white with a blue outline
  and blue lines. In both, frequent routes are drawn heavier than regular ones, and the card's Transit nearby
  chips match the badges, with a double ring for frequent routes. Engine: route lines, badges and chips now
  carry `freq`, `exp` and `night` classes (night also on every route while the Overnight family shows), and
  optional `card.transit.routeClasses` adds classes by route number; the dashed rule is now `.rt.dash`.
  Vancouver looks as before. Website styling only; for the iOS app, contract section 5 describes the styles.
- **Views** (October 11, Toronto and Chicago): a chip row at the top of the panel with five one-tap views:
  Explore downtown, Know your city (neighbourhood/community area lens on the transit time downtown, express
  buses), Who represents me, Where to live (housing cost, frequent transit) and Getting around. Each replaces
  the whole map state and frames its area; changing anything after that shows "Custom". Who represents me
  shows one set of boundaries at a time with chips to switch, leading with the layer of the next election
  within 180 days (Toronto: City wards for October 26; Chicago: school board districts for November 3, then
  wards for February 23), and a hint under the search box until a spot is pinned. Links carry `preset=`;
  Reset and first load are unchanged. For the iOS app: a new optional `presets` key in `city.json`
  (contract section 5), which it can ignore.
- **Rent relabelled** (October 11, all three cities): the Housing row reads "renters pay $X/mo" instead of
  "rent $X/mo", and each city's caveat says what the figure counts: what renting households pay, utilities
  included, long-time tenants and subsidized homes too (basement suites in Toronto and Vancouver), so it sits
  below what a new lease costs. Same field and data. For the iOS app: wording only; contract section 4 and 5
  examples updated.
- **Narrow it down: Most common home** (October 11): pick detached, semi & row, low-rise or towers (Chicago:
  detached, attached, 2–19 or 20+ units) and only places where that is the commonest home type stay. A filter
  with `"top": true` on a pick lens; it takes its chips from the lens. Largest share rather than a 50% cut,
  since at 50% half of Toronto's neighbourhoods have no majority type and only 4 are mostly semi or row.
- **Heritage buildings** (October 11): a layer of buildings protected one by one, after Heritage districts.
  Toronto: 1,515 properties designated under Part IV (City Heritage Register; listed and district-only
  properties left out; names taken from the register's descriptions where they start with one, 767 of
  them). Chicago: 412 Chicago Landmarks (Individual Landmarks dataset). Small diamonds from zoom 15 (only those in view, so it stays smooth on phones), names
  from 16; popup with year, architect, designation, and Toronto's by-law and district; a Heritage building
  row on the card (within 40 m); named ones in search. Fetched monthly by
  `engine/fetch_heritage_buildings.py` (fetch-heritage-buildings.yml), built by
  `engine/heritage_buildings.py`. The Attributions page lists the new sources. For the iOS app:
  `heritage_buildings.geojson`, layer kind `heritage`, fact `heritageBuilding`; contract sections 3, 4, 5.
- **What's changing** (October 11): a layer of big changes (new buildings that aren't single houses,
  demolitions of bigger buildings, Toronto's rezoning, site plan and subdivision applications), one dot per
  site coloured by stage (proposed, approved, under construction, finished in the last two years;
  demolitions dashed), stage chips, a popup with the City's application page, and a *Changing nearby* card
  section (500 m / ½ mile). Toronto: 2,845 sites from development applications and building permits
  (permits placed on the City's address points); Chicago: 1,225 sites from building permits (no proposals
  data). Fetched weekly by `engine/fetch_changes.py` (fetch-changes.yml), built by `engine/changes.py`.
  Contact, owner and builder names are never kept. For the iOS app: `changes.geojson`, layer kind
  `changes`, `card.changes`; contract sections 3, 4, 5. Additive.
- **Tree canopy** (October 11): a new lens (*Tree canopy*: four bands per city, Toronto under 15 / 15–30 /
  30–45 / 45%+, Chicago under 8 / 8–15 / 15–25 / 25%+), a Living here row ("67% of the land is under
  trees") and a high-end fact ("Among the leafiest in Etobicoke"; facts now cover 121 Toronto and 64
  Chicago units). Share of land under tree cover, water left out, from ESA WorldCover 2021 (10 m, CC BY
  4.0), computed in Actions by `engine/fetch_canopy.py` (fetch-canopy.yml) and added to the profiles by
  `engine/canopy.py` (run.sh). Citywide 30.5% (Toronto's 2018 study: 28–31%) and 15.5% (Chicago's 2020
  tree census: 16%). For the iOS app: profile fields `canopy`, `canopyBand`, the `canopy` lens,
  `card.living.canopy`, facts field `canopy`, colours `--can-1`…`--can-4`; contract section 5. Additive.
- **Ages and recent immigrants** (October 11): two Living here rows. *Ages*: a stacked bar of five bands
  (under 15, 15–24, 25–44, 45–64, 65+). *Recent immigrants*: Toronto, the share who immigrated to Canada
  2016–21 (2021 Census Neighbourhood Profiles); Chicago, the share born abroad who entered the US 2010 or
  later (ACS 2020–2024 B05005 over B01001's total; new tables in `fetch_acs_more.py`). Each with a caveat
  naming its window; card only, never a lens, filter or fact. For the iOS app: profile fields `ages`,
  `recent`, `recentSince`, config `card.living.ages` / `recent`, and a fifth mix colour `--mix-5`;
  contract section 5. Additive, schema stays 1.
- **Guided first visit** (October 11): a five-step tour of each city through the map. A first visit (no
  link in the address, not seen before in this browser) shows a small invitation; a Tour button in the
  panel footer starts it any time. Each step sets exactly its layers, the scope and the view (kept clear
  of the tour box), may open the card, and outlines its layers in the panel; Back/Next, dots, arrow keys,
  Escape. The map before the tour is kept as a link and restored when it ends. Text in `city.json`
  `tour` (invite, buttons, steps with `title`, `text`, `layers`, `hi`, `scope`, `view`, `pin`). For the
  iOS app: a new optional `tour` key in `city.json` it can ignore or use for its own onboarding.
- **How addresses work** (October 11): a toggle under Main streets. Chicago's *Address grid* draws State
  and Madison as the zero lines and every mile line (800 N … 7200 N, 1200 S … 12700 S, 800 W … 7200 W,
  800 E … 2400 E), each numbered; Toronto's *Yonge: East and West* draws Yonge and tints the 43 drawn streets
  it splits (East teal, West orange). The What's here card gains an Address row: Chicago reads the spot's
  numbers off the grid ("About 1500 N · 2100 W"), Toronto says which side of Yonge and names a nearby E/W
  street. Built by `engine/addresses.py` from each city's street files and `cities/<city>/addresses.json`
  (in run.sh). For the iOS app: new file `addresses.geojson`, layer kind `addresses`, `card.address` and
  the `address` fact row; contract sections 3, 4, 5. Additive, schema stays 1.
- **Compare two places** (October 11): *Compare with another place* on the What's here card, then tap the
  map or search for a second spot. The card widens (on desktop) into one table: each of the card's rows,
  its label above the two places' values (A left, B right), section by section, with a dash where one
  place has no value; shared caveats and notes appear once per section. Pins are lettered A (purple) and
  B (orange). A second place outside the city switches to the regional view. Tapping elsewhere replaces B;
  × drops a place and goes back to the other's card. No highlighting of differences: describe, don't rank.
  Links add `pin2=lat,lng` and `name2=`. Engine only: no data files change; the iOS app can build the
  same view from the rows it already has (contract section 5).

### Toronto
- **Where to vote** (October 14): until polls close on October 26 at 8 pm, the What's here card opens with
  a tinted box and a ballot-box icon: "Election day · Mon, Oct 26 · 10 a.m. to 8 p.m. People living here vote
  at …", the building, its address and distance, the entrance and accessible entrance where the City lists
  them, a Show on map button and a link to the City's MyVote. A ballot-box mark sits on the voting place.
  From the City's 2026 voting subdivisions and voting places (its ArcGIS Online layers, one place per
  subdivision), fetched daily in October by `fetch-voting.yml` because the City says places can change up to
  election day; building names and entrances from its All Wards list where the addresses agree. The box and
  the file go away on their own once the polls close. For the iOS app: `voting.geojson` and `card.vote`
  (contract sections 3 and 5), optional and time-limited. Additive, schema stays 1.
- **Starting layers** (October 12): first load and Reset now also show Landmarks, Universities, Colleges,
  Hospitals, Skyscrapers and Streetcars, beside Former cities, Old Toronto areas, Neighbourhoods, Known-as
  names, Main streets, Highways, GO trains and Subway & LRT. Shared links that list their layers are
  unchanged; a link without `layers=` now opens with these. For the iOS app: only the `on` flags in
  `city.json` changed.
- **GO buses** (October 11): a new toggle under GO Transit trains draws GO's regional bus routes, in a
  dark GO green, numbered "GO 41" so they never mix with TTC route 41. The regional view shows the whole
  network (Hamilton, Niagara, Guelph, Peterborough…); the city view shows only the routes that stop in
  Toronto, numbered where they run inside it, with the rest fading under the region. Stops from zoom 12.
  The What's here card's Transit nearby gains a GO buses row, search finds "GO 41", and any GO route can
  be picked or tapped to see it alone, like a TTC route. Read weekly from Metrolinx's GO GTFS alongside
  the TTC's (a second feed in `surface.json`; `engine/fetch_surface.py toronto go`).
  For the iOS app: `transit.json` routes with `m: "go"` (prefixed `r`, `f: []`, `in`), top-level
  `feeds`, the `regional` layer kind, a third Transit nearby row; contract sections 3, 4, 5. Additive,
  schema stays 1.

### Both cities
- **Use my location** (October 11): on phones, a button in the search bar finds the phone, pins it (in blue,
  with an accuracy ring when it's rough) and opens the What's here card there. All lookups run in the
  browser; the position never leaves the phone and is left out of shared links. Outside the map's area it
  says so. `?at=lat,lng` in the address pretends to be there (for demos), and shows the button on any device.
- **Image shapes for Instagram** (October 11): the Image menu now offers Wide (3840 × 2160, as before),
  Square (2160 × 2160), Portrait 4:5 (2160 × 2700) and Story 9:16 (2160 × 3840). The Instagram shapes are
  drawn at twice a 1080-px frame so names stay readable on a phone; phones default to Portrait, and the
  choice is remembered. When focused on a place, the image fits the place and puts its name top left as a
  title. Credits wrap to fit. Engine only.
- **Focus on a place** (October 10): tap a neighbourhood's, area's or former city's name on the map (in
  Chicago a community area or side), or a "Focus on" chip on the What's here card. Everything outside it
  dims; trains, subway/'L' lines and routes that pass through stay full inside and half-faded outside, so
  you can follow them to where they end, and the rest fade out. The panel lists the lines and routes
  through it (route chips draw the route), main streets in or along it, and landmarks, institutions and
  skyscrapers inside. Tap outside, press Escape or Exit focus to leave. Links keep it as
  `focus=<layer id>:<name>` (e.g. `focus=nbhd:Cabbagetown-South St.James Town`). Engine only: no data
  files change, so nothing for the iOS app to port.
- **Every bus route** (October 10): the Bus routes chips are now *All*, *Frequent*, *Express* and
  *Regular* (every other daytime route: 119 TTC, 80 CTA) in any mix, with *Overnight* on a row of its
  own as before; the layer starts on All. All draws every daytime bus route (183 in Toronto, 123 in Chicago). Route shapes were
  rebuilt so each route is a handful of lines instead of dozens of overlapping pieces (Chicago 8,472
  pieces → 391, Toronto 2,838 → 652), which keeps All quick on phones and made the file smaller.
  For the iOS app: family `reg` in `transit.json`, `allText`/`allNote` on the layer, `bus=all` in
  links; contract sections 3 and 4. Additive, schema stays 1.
- **Tap a route to see it alone** (October 10): tapping a streetcar or bus line, or its number badge,
  shows that route alone in ink with its stops while every other route fades; tapping another route
  switches to it, and the next tap anywhere else (or Escape) brings them all back without opening the
  card. A passing look, so it isn't kept in shared links.
- **Collector streets** (October 10): a toggle under Main streets, off by default,
  drawing the next tier of roads (Toronto's Collector class, 989 streets; Chicago's OSM tertiary
  roads, 272) thinner than the main streets from zoom 13, named from 15. Most bus streets that aren't
  arterials are collectors, so bus lines stop floating: 93% of the TTC's network and 88% of the
  CTA's now sits on a drawn street. Also: at zoom 15 only the stops of routes being drawn show.
  For the iOS app: new file `collectors.geojson`, `labelZoom` and `yieldLabels` on a `streets`
  layer; contract section 3. Additive, schema stays 1.
- **Streetcars and buses** (October 10), from the TTC and CTA schedules (GTFS), refreshed monthly
  by a new Action (`fetch-surface.yml`).
  - Toronto: a **Streetcars** layer after Subway & LRT, off by default: the 11 daytime routes in
    red, numbered along the line, stops from zoom 15.
  - Both cities: a **Bus routes** layer, off by default, with chips for *Frequent* (every 10 minutes
    or better each way on weekdays, 7 am to 7 pm: 43 TTC bus routes, 23 CTA), *Express* (named express
    by the agency: 28 and 20), which can be on together (express then dashed), or *Overnight* on its
    own (at least hourly each way from 2 to 4 am: Toronto's Blue Night network, 35 routes including
    the night streetcars; 17 CTA routes). Daytime streetcars stay on the Streetcars layer. Families
    are worked out from the schedule, not the agency's branding.
  - Card: a **Transit nearby** section (between Schools and Nearby): the nearest subway/'L'
    station, every streetcar and bus route with a stop within 400 m (¼ mile in Chicago), overnight
    routes, and the nearest stop. Frequent routes are filled. Each number is a button that draws the
    route on the map in ink with its stops, whichever layers are on; tapping a line on the map or
    searching a route ("29", "Dufferin", "J14") does the same. Picked routes and the families are kept
    in shared links (`routes=29,504`, `bus=freq+exp`).
- For the iOS app: new files `transit.json`, `transit_routes.geojson` (load on demand) and, in
  Toronto, `streetcars.geojson`; new layer kinds `streetcars` and `buses`, `lazy` on a layer;
  `card.transit`; contract sections 3, 4 and 5. Additive, schema stays 1.
- **Transit under construction**: a new layer after Subway & LRT / the 'L', off by default. Dashed
  lines in the future line's colour with hollow stations: the Ontario Line, the Line 2 East and
  Eglinton West extensions and the Hazel McCallion Line (regional view) in Toronto; the Red Line
  Extension in Chicago. Tap a line or station for who builds it, its length and (where the owner
  has published one) the expected opening. Lines come from OpenStreetMap, filtered by a curated
  list; Yonge North isn't mapped there yet, so it's left off.
- **Road closures** nested under it, refreshed daily just after midnight Eastern: closures (red) and
  lane restrictions (amber) from transit construction, including GO Expansion in Toronto and the
  Red/Purple rebuild in Chicago. Arterials show from zoom 12 as a small diamond, and as the stretch
  itself when zoomed in; full closures of side streets appear from zoom 15. Tap for the hours, the
  permit dates, the project and the permit holder. Toronto from the City's live Road Restrictions
  feed, Chicago from CDOT permits.
- For the iOS app: new files `construction.geojson` and `closures.geojson` (optional), new layer
  kinds `construction` and `closures`, `optional` on a layer; contract section 3. Additive, schema
  stays 1.
- **Skyscrapers**: a toggle under Landmarks with every building 150 m and taller (Toronto 117 plus
  13 under construction, Chicago 138 plus 1), from Wikipedia's tallest-buildings lists. A square
  badge per tower: its glyph and colour show use (residential, office or hotel, mixed); hollow and
  dashed until open for occupancy; a gold ring at 300 m+. Tapping one adds a block to the card:
  use, height, floors, year (or expected year), up to three facts and a Wikipedia link. Search
  finds towers by name and former name ("Vista Tower", "John Hancock").
- **Landmarks**: campus points are gone from the Landmarks layer (the Universities toggle has them,
  and search still finds U of T, TMU, UIC, IIT… through the layer's nicknames). Universities,
  Colleges, Hospitals/ERs and Skyscrapers sit indented under Landmarks, all off by default. Willis
  Tower and 875 North Michigan stay on Landmarks too.
- For the iOS app: new file `skyscrapers.geojson`, new layer kind `towers`, `aliases` on the
  Universities layer, `under` on nested layers, card step 5a; contract sections 3, 4, 5 and 11.
  Additive, schema stays 1.

### Chicago
- **Election box** (October 14): until polls close on November 3 at 7 pm, the What's here card opens with the
  same tinted ballot-box box as Toronto's, naming the spot's ward and precinct ("Ward 43, Precinct 20"), the
  hours (6 a.m. to 7 p.m.) and a Find your polling place button to the Board of Elections' lookup. The Board
  publishes no polling places by precinct (its lookup needs a voter's name), so no building is named and no
  mark is drawn. Precincts from the City Data Portal (i8fv-xe4b, approved December 9, 2025), fetched by
  `fetch_precincts.py`, built by `cities/chicago/voting.py`. For the iOS app: `voting.geojson` features
  without `x`/`y` carry `p` (precinct); `card.vote.precinct` / `precinctSub` (contract sections 3, 5).
- **Schools** section on the card: the CPS elementary, middle (where one has its own area) and high
  school whose attendance area holds the spot, with grades, straight-line distance and a link to
  the CPS profile. CPS 2025–26 boundaries from the City's Data Portal. Names and grades only.
- **Miles**: card distances (Nearby and Schools) are in miles, feet when very close, and Nearby
  counts what's within half a mile (805 m, about a 10-minute walk) instead of 1 km. Toronto stays
  in kilometres.
- For the iOS app: new file `attendance.geojson`; new `card.schools` and top-level `distance`
  (`"mi"`) in `city.json`, with `card.nearby.radius` now 805; contract sections 3, 4 and 5.
  Additive, schema stays 1.

## Version 1.1 (October 10, 2026)

Everything up to commit `b69c3a0` (the iOS app section on the maps hub) is version 1.0. Version 1.1
adds the features below to both cities. The data stays at `"schema": 1`: every change is additive,
so the iOS app keeps working as it is. The last section lists what the app would need to show them.

### Toronto
- **School board wards** layer: the 2026 trustee wards of TDSB (12), TCDSB (12), Viamonde (3) and
  MonAvenir (2), one board at a time, built from whole City wards per the City Clerk's reference
  chart. Card: a *School wards* boundary row and a trustee row per board (candidates before the
  October 26 election, then the winner, then the trustee from November 15), from the City's
  election results file, refreshed hourly on election night.
- **Lakeshore** beyond the city limits now follows OpenStreetMap's Lake Ontario, Simcoe and Scugog
  outlines instead of Natural Earth's, so Port Credit and other lakeside places are on land.

### Chicago
- **School board districts** layer: the 20 Chicago Board of Education subdistricts (1a–10b) enacted
  by Public Act 103-0584. Card: a *School board* boundary row, a member row for the district and a
  citywide president row, with candidates from the Chicago Board of Elections' list; from election
  night (November 3) the row names who leads the unofficial count, and the winner once results are
  proclaimed.

### Both cities
- **Universities, colleges and hospitals**: three toggles under Landmarks. Public or nonprofit only;
  no partnership campuses or career colleges; hospitals with an emergency department ringed. Toronto
  curated and placed by OpenStreetMap; Chicago from IPEDS and CMS. Search finds them by name.
- **Nearby** section on the card: nearest library, community centre and emergency department with
  distance, and counts of parks, playgrounds and more within 1 km.

### Engine
- New layer kinds: `boards` (several overlapping ward sets in one file, with a picker) and `places`
  (institution points by category).
- Trustee rows support a leading candidate, a citywide seat and "1 candidate".

### For the iOS app (see `app-contract/DATA_CONTRACT.md`)
- New files: `school_wards.geojson` (Toronto), `school_board.geojson` (Chicago),
  `institutions.geojson`, `nearby.json` (both).
- New in `representatives.json`: `trustees`.
- New in `city.json`: layer kinds `boards` and `places`; card `facts` rows with `boards`;
  `card.reps.trustees`; `card.nearby`.
- Contract sections: 3 (files), 4 (`boards` and `places` kinds), 5 (School wards row, Trustees,
  Nearby), 8 (trustee data), 11 (drawing `boards` and `places`).
