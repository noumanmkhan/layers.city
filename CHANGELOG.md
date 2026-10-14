# Changelog

## Since 1.1

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
