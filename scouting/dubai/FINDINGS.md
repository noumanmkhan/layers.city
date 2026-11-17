# Dubai, Sharjah and Ajman: scouting findings (November 17, 2026)

Scouted from the user's Mac (Claude Code), not from Actions. Brief: `scouting/dubai/BRIEF.md`. Raw files in
`cities/dubai/raw/` (big ones gitignored). Timing log at the end.

## Verdict
Buildable, with one large gap until Dubai Municipality approves us. Transit is the strongest part: RTA's GTFS
(October 31, 2026 issue, valid September 11 to December 31, 2026) has the Metro, the tram, 188 bus routes and
15 marine routes. OpenStreetMap is good for streets, parks, beaches, places, the Blue Line under construction and
Etihad Rail. The weak part is the **units**: DM's 224 community boundaries come with a condition (approval through
GeoDubai before use on a website), so the map starts on OSM's community polygons, which leave big holes
(Dubai Marina, JLT, Al Barsha, Al Quoz, the Palm, Jebel Ali). Decided with the user: OSM now, swap in DM after
approval. No census, no elections, no live bus times.

## How the place differs
- **Dubai Pulse is gone.** www.dubaipulse.gov.ae resets every TLS handshake, even from a UAE address. Its
  successor is **Data Dubai** (https://data.dubai, Liferay, run by the Dubai Data and Statistics Establishment),
  which rejects non-UAE addresses outright ("Request Rejected"). The user turned on a UAE VPN at 14:40 and it
  answered. Downloads are anonymous: `/o/dda/data-services/dataset-download?datasetId=<id>` returns a signed
  `cdn.data.dubai` link valid 10 minutes. The catalogue listing itself needs a browser session, so dataset ids
  were found through the site's own search (table below).
- **The Wayback Machine** holds about 3,600 old Dubai Pulse downloads (2022 to January 2026). Useful as a check,
  not as a source: superseded by Data Dubai.
- **Geo-blocking matters for refresh jobs.** GitHub Actions runners (US) cannot reach Data Dubai, makani.ae or the
  old Dubai Pulse. Any recurring Dubai refresh has to run from a UAE address (the user's Mac with the VPN) or be
  done by hand. OSM, the Mobility Database mirror and Ajman's portal are reachable from anywhere.
- **makani.ae** (DM's Makani public web service, a .svc with GetMakaniInfoFromCoord) also answers only from the UAE,
  so a live "Makani number" card row can't be called from readers' browsers abroad, and the service has no CORS
  promise. The bulk entrances file (Data Dubai 462928, 242 MB KML, August 2026) carries no approval clause.
- Units: Dubai has two naming systems: DM communities (three-digit numbers, e.g. "AL RIGGA - 119") and the Dubai
  Land Department's area names (300 areas, e.g. "Marsa Dubai" for Dubai Marina). Everyday names (Dubai Marina,
  JLT, JVC, Downtown) are neither; they are the known-as layer.
- No municipal elections; Federal National Council members are chosen by an electoral college of appointed
  electors. Representation and where-to-vote are **not applicable**.
- Weekend Saturday–Sunday, Asia/Dubai (UTC+4, no DST), AED, `en-AE`.

## Licences
| Source | Licence | Use |
|---|---|---|
| Data Dubai "Open" datasets | Dubai Open Data Licence (the PDF linked from data.dubai/en/terms-conditions, the same text as Dubai Pulse's, still marked DRAFT): worldwide, royalty-free, commercial and non-commercial, attribution required, no implied endorsement, adapted *databases* to be shared under the same licence | GTFS, parks, Makani entrances |
| DM communities (461494) and sectors (469026) | Same licence, **plus** DM's note: "prior to integrating any data into external websites … users must submit a request … via geodubai.dm.gov.ae … approved once the data owner provides approval" | **Not used** until the user's GeoDubai request is approved (user's decision, 14:51) |
| KHDA schools | KHDA: "not intended to be used for profit" | **Not used** (user's decision): schools from OSM |
| Ajman Open Data (data.ajman.ae, Opendatasoft) | 175 of 195 datasets CC BY 4.0, 2 ODbL, 18 none stated | Ajman districts (CC BY 4.0) |
| OpenStreetMap (Geofabrik GCC extract, November 16, 2026) | ODbL | Units, streets, places, rail, parks, everything else |
| Sharjah | No public open data. Mada (Sharjah Digital Department) is an inter-government platform, not a public portal | OSM only |
| FCSC (opendata.fcsc.gov.ae) | Cloudflare 403 to scripts; not needed | — |
| Bayanat | 404 | — |

No non-commercial source is used, so NONCOMMERCIAL.md is unchanged.

## Data Dubai dataset ids found
| id | Dataset | Latest file |
|---|---|---|
| 461494 | DM Communities (KML) | community_2026-10-20 (224 communities; approval clause) |
| 469026 | DM Sectors (KML) | sector_2026-10-20 (9 sectors; approval clause) |
| 462928 | DM Entrances (Makani, KML) | entrances_2026-08-25, 242 MB |
| 463074 | DM Parks and beaches X/Y | 2026-07-15, 157 rows: facilities *inside* parks (gates, play areas), not park outlines |
| 464582 | DM Heritage places | visitor counts by site and month, **no locations** |
| 464468 | RTA GTFS | gtfs_2026-10-31 (a zip named Ops_GTFS_11-Sep-2026) |
| 459523 | DM Buildings summary | 211 MB CSV, building level (not used) |
| 467362 | DSC Population cluster | a lookup list only |
Population by community (DSC) was on Dubai Pulse to 2020 (Wayback copy); not found on Data Dubai by search.
DLD area names (`lkp_areas`, 300 areas, January 2026 copy on the Wayback Machine) are a lookup without geometry.

## Layer by layer
**Units.** OSM `admin_level=10` has 127 Dubai communities (1,700 km² of the urban frame) plus 9 at level 8
(Business Bay, DIFC, Jumeirah Islands, Jumeirah Park, The Meadows…). Missing: Dubai Marina, JLT, Al Barsha 1–3 and
South, Al Thanyah, Al Sufouh, Emirates Hills, JVC, Al Quoz, Ras Al Khor, Al Mamzar, the Palm, Jebel Ali 1–3,
Dubai Investments Park, Al Khawaneej and the inland areas (84 OSM place names fall in the gaps). Gaps stay empty on
the map; known-as names cover the everyday names. DM's 224 communities replace them after approval.
**Sectors.** DM's 9 sectors wait for approval. Sides instead: Deira (north and east of the Creek), Bur Dubai
(south and west of it, to Al Safa) and New Dubai (the coast and inland from Al Quoz/Al Barsha to Jebel Ali), from
OSM community polygons and the Creek.
**Regional tier.** OSM emirate boundaries (AE-DU, AE-SH, AE-AJ). Sharjah: 25 OSM level-8 areas (Al Majaz, Al Nahda,
Al Qasimia…). Ajman: 42 districts from Ajman Open Data (CC BY 4.0) and 20 OSM level-8 areas. Umm Al Quwain is
outside the brief's region.
**Streets.** OSM: 4,930 motorway/trunk/primary ways, 13,592 secondary/tertiary. Highways by ref: E11 (Sheikh Zayed
Road), E311 (Sheikh Mohammed bin Zayed Road), E611 (Emirates Road), E44 (Hatta Road), E66 (Al Ain Road), E77, D-roads.
**Transit (RTA GTFS, October 2026).** Metro Red (MRed1, MRed2: the Expo branch) and Green; tram T1; 188 buses
(F feeders, C city, X express, E intercity: E16, E100, E101, E201, E303, E306, E307, E307A, E308, E315, E400, E411,
E700, J Jebel Ali, N night, DH, SH1); 15 marine (BM abra, CR creek ferries, FR ferry, DC water taxi). 2,847 stops.
`frequencies.txt` present. No public GTFS-realtime: RTA feeds Google Maps and Swiftly privately. Live times: no.
**Under construction.** Metro Blue Line: 44 OSM ways (`railway=construction`, `construction=subway`, name
"Blue Line Metro"). Etihad Rail: OSM has the main line, the Sharjah branch and the Jebel Ali extension. Passenger
service: Abu Dhabi–Fujairah from June 30, 2026; Dubai (Al Yalayis, by Jumeirah Golf Estates Metro, footbridge) and
Al Dhaid opened September 30, 2026 (Gulf News, Gulf Business); Sharjah station due March 30, 2027.
**Places (OSM in the metro frame).** Places of worship 1,239 (christian 16, hindu/sikh/buddhist 7: mosques are the
rest); hospitals 140 (`emergency=yes` on 38); schools 430; universities/colleges 69; libraries 23; parks 1,109;
beaches 260; sports centres/stadiums 178; historic 91; EV chargers 49; taxi 21; bike rental 67 (Careem BIKE docks);
community centres 42; cycleways 651 ways.
**Bike share.** Careem BIKE: no public GBFS feed found. Docks from OSM only.
**Parking.** Parkin zones: no open geometry found. Not built.
**Lens.** No census. DSC population by community needs DM units (after approval). DLD rents: Rent contracts on Dubai
Pulse were 56 MB (2022); Data Dubai id not yet found. Lens parked until DM units.

## Content hooks
- The Creek as the old line between Deira and Bur Dubai; abras crossing it for 1 dirham.
- Makani numbers: how Dubai addresses work (a 10-digit entrance number).
- The Blue Line's Creek crossing and Etihad Rail's footbridge to the Red Line at Jumeirah Golf Estates.
- Fun maps to suggest: "Dubai Marina vs the Toronto waterfront" (towers), "the Creek vs the Don", "how far a 1-dirham
  abra gets you", heat-aware walk times (no advice, just times).

## Still open (for the user)
1. **GeoDubai request** for DM communities and sectors (and say population by community). Once approved:
   swap units to DM, add the sectors layer, add the population density lens.
2. Refresh jobs need a UAE address: Actions can't reach Data Dubai. Options: refresh the GTFS by hand from the Mac
   each quarter, or use the Mobility Database mirror (mdb-3359, but its latest copy is August 2025 and expired).
3. Makani card row: bulk entrances (242 MB) could give "nearest Makani entrance" offline. Not built yet.

## Toronto parity checklist (Phase 2, November 17, 2026)
Built = live at layers.city/dubai/ (unlisted). No data = no usable open source yet. N/A = doesn't apply to Dubai.

| Toronto layer or feature | Dubai | How |
|---|---|---|
| Neighbourhoods (units) | Built | 122 OSM communities (L10, plus named L8 areas); about two-thirds of the urban area. Gaps say "Not mapped yet". DM's 224 communities once GeoDubai approves |
| Former municipalities / sides | Built | Deira, Bur Dubai, New Dubai (the Creek and the old side lines) |
| Wards / sectors | No data | DM's 9 sectors wait for GeoDubai |
| Known-as names | Built | 40 (Dubai Marina, JLT, the Palm, Al Barsha, Al Fahidi…) |
| Landmarks | Built | 41 |
| Highways and shields, streets, collectors | Built | OSM; E11, E311, E611, E44, E66, E77 and the rest by ref |
| Regional municipalities | Built | Sharjah (OSM areas) and Ajman (Ajman Open Data districts, CC BY 4.0) as neighbours, the rest of Dubai emirate as one piece |
| Subway | Built | Metro Red and Green, 53 stations (RTA GTFS via Data Dubai) |
| Streetcars | Built | Dubai Tram, 10 stops |
| Buses | Built | 189 routes by family (Frequent, Express, Regular, Night) |
| Ferries | Built | Abras, Dubai Ferry, water taxi; 24 stations (off by default) |
| GO / regional rail | Built | Etihad Rail and Dubai (Al Yalayis) station (OSM) |
| Transit under construction | Built | Blue Line (OSM, opens September 2029 per the RTA) |
| Other rail | Built | Palm Monorail (OSM, off by default) |
| Transit nearby (card) | Built | From the GTFS |
| Routes from here page | Built | /dubai/routes/, timetable only |
| Live arrivals | No data | RTA publishes no GTFS-realtime |
| Parks and beaches | Built | 120 parks and 112 beaches (OSM) |
| Sports & rec | Built | 99 stadiums, sports centres, golf courses, water parks (OSM) |
| Libraries & community centres | Built | 14 (OSM) |
| Hospitals / ERs | Built | 36 hospitals; the ER only where OSM tags it (13) |
| Universities and colleges | Built | 34 campuses (OSM) |
| Schools | Built | 215 (OSM), one category, never ranked. KHDA's list and ratings not used |
| Places of worship | Built | 151 (126 mosques; churches, Hindu temples, gurdwaras) |
| Heritage | Built | 34 historic sites and museums (OSM) |
| Skyscrapers | Built | 81 towers 200 m+ (Wikipedia, placed with OSM) |
| Card: Nearby | Built | nearby.json from the layers above |
| Card: Address (Makani) | No data | Makani is UAE-only and the bulk entrances file is 242 MB; not built |
| Card: representatives | N/A | Appointed offices: no representative rows (brief) |
| Card: where to vote | N/A | No public elections for the city |
| Lens and Living here | No data | No census; DSC population by community needs DM units; DLD rents parked |
| Guide pages, sitemap | N/A | The engine writes none for an unlisted city |
| Fact sheets | No data | Waiting for DM units (OSM units cover two-thirds of the city, with no figures to show) |
| Venues | No data | Ticketmaster doesn't sell in the UAE; the UAE's ticket sellers publish no open feed |
| Events and Happening nearby | No data | Dubai Calendar and Dubai Municipality publish no open events feed |
| Weekend brief | No data | No closures or events inputs |
| Bike lanes, bike share | Not built | OSM has 651 cycleway ways (buildable later); Careem BIKE has no public feed |
| Parking | No data | No open Parkin zone geometry |
| Buildings (3D) | Not built | Overture tiles could cover Dubai; left for a later pass |
| Fun maps | Not built | Suggested only (Content hooks above) |
| Halal / kosher layer | N/A | Not built, per the brief |

### Decisions taken without stopping
- Sides: Deira, Bur Dubai and New Dubai, cut along the Creek's water.
- OSM gaps: the Routes page names a place in a gap by the nearest known-as name (route_areas), never by a far community.
- Mosques get a chip on the map. Places of worship start at zoom 13 so 126 mosques don't crowd the city view.
- Hospitals: all of them, with the ER only where OSM tags it.
- Skyscrapers: 200 m and up; Dubai has more than 100 towers of 150 m and up, too many at that cut.
- Ferries and the Palm Monorail are off by default.
- No sea label: the name of the Gulf is disputed, so the water is left unnamed.
- Etihad Rail is drawn inside the frame only, with no line to the border.
- Venues, Events and fact sheets are recorded as no data rather than built thin.
- Refreshes: Dubai joins the quarterly skyscrapers fetch (Wikipedia). The RTA GTFS needs a UAE address and the OSM
  layers come from a 258 MB Geofabrik extract, so both are refreshed by hand from the Mac (SOURCES.md), not in
  Actions.

## Timing log
- Phase 1: 14:22 to 15:00 (Mac local time, November 17, 2026).
- Stops for the user: 2 during Phase 1 (Dubai Pulse access and KHDA, 14:36; DM approval clause, 14:51).
- What the Mac reached that a cloud sandbox couldn't: Data Dubai and makani.ae (through the user's UAE VPN; no
  cloud sandbox or Actions runner has a UAE address); Geofabrik's 258 MB GCC extract in seconds and local osmium
  processing (no Overpass rate limits; Overpass itself took 32 s just for /status); the 242 MB entrances KML;
  the in-app browser for Data Dubai's session-only catalogue.
- Phase 2, step by step (Mac local time, November 17):
  1. Skeleton, units, sides, known-as, landmarks, streets, region: 14:53 to 15:03
  2. Metro, tram, buses, marine, Etihad Rail, Blue Line, monorail, Routes page: 15:04 to 15:12
  3. Parks, beaches, sports, libraries, hospitals, campuses, schools, worship, heritage, skyscrapers: 15:12 to 15:16
  4. Card Nearby (Makani, lens, Guide and fact sheets recorded as no data / N/A): 15:16 to 15:20
  5. Venues, Events, fun maps (checked, recorded as no data; fun maps suggested): 15:20 to 15:21
  6. Refreshes (skyscrapers workflow): 15:21 to 15:22
  7. FEATURES.md, CHANGELOG, this file: 15:22 to 15:26
- Stops for the user during Phase 2: 0. Total stops: 2.
- Phase 1 to an unlisted, live city: about an hour and five minutes in one session. Melbourne by comparison took
  several cloud sessions over two days and leaned on Actions and WebFetch for portal access.
