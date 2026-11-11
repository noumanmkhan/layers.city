# Cycling in Toronto, 2016–2026: data scouting (November 11, 2026)

Asked in the comments on the downtown-weekday Reel (156K views): bike lane removals, and how many Bike Share rides
there have been in 2026. Scouting only: nothing built, the site is unchanged. The aim is a follow-up page and Reel
that answer with sourced numbers, not opinion.

The project's `claude/` notes (`reel-downtown-daily-population.md`, `bike-lanes.md`, `bike-share.md` and others
CLAUDE.md mentions) couldn't be found on November 11, 2026 and may have been lost with a cache folder, so this
note lives here in `scouting/`. Repo context used instead: CLAUDE.md, `cities/toronto/SOURCES.md` (Bike lanes,
Bike Share stations), `cities/toronto/commute.json`, `cities/toronto/raw/tts/`, `scouting/bike-closures/FINDINGS.md`,
NONCOMMERCIAL.md and the CHANGELOG.

## Headline

- Every source below measures something different. **Bike Share rides** are trips on one rental system.
  **TTS trip share** is the share of surveyed weekday trips made by bike. **Census journey-to-work** is people's
  main way of getting to work in one week of May. **Lane km** is infrastructure, not use. **Counters** count only
  riders inside the lane at one spot. None of them can stand in for "how many people cycle in Toronto".
- The strongest series is **Bike Share**: monthly trip files from 2017 to September 2026 on the City's portal under
  the Open Government Licence – Toronto. Rides grew from 1.92 million in 2018 to 7.81 million in 2025. Our own
  counts match the City's published totals except in 2022, where the portal file is missing November.
- **2026 Bike Share, January–September: 6,830,174 rides**, 10.0% more than in January–September 2025
  (6,211,164). The full 2026 total won't exist until the December file is published (likely January 2027).
- **Removals**: the City's network file can't show them. It describes only the current network (no removal
  date or status field), and the latest file (September 14, 2026) predates the first Bill 212 removal
  (Bloor St W, Clissold Rd to Royal York Rd, done October 30, 2026). A before-and-after needs dated snapshots
  plus the Province's work notices. We have three snapshots now, and our monthly fetch will capture the next.
- **TTS**: the City has already published TTS cycling shares for 2001–2022 on a stated definition
  (Toronto origins, people 11+). Our own iDRS exports should reproduce those figures before we use anything new.

## Sources

| Source | What it measures | Years | Format, size | Licence | Usable? |
|---|---|---|---|---|---|
| [Bike Share Toronto Ridership Data](https://open.toronto.ca/dataset/bike-share-toronto-ridership-data/) (TPA) | Every Bike Share trip: start/end station and time, duration, bike id, user type; bike model from 2024 | 2014–15 (station totals only), Jul–Dec 2016, 2017 to Sep 2026 | XLSX (2014–16); ZIP of CSVs (2017+): 24 MB (2017) to 227 MB (2025) zipped, about 1 GB of CSV a year unzipped | [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/) | **Yes**: the best year-on-year series |
| [Bike Share GBFS](https://open.toronto.ca/dataset/bike-share-toronto/) (already in the repo, `raw/bikeshare.json`) | Stations, docks, e-bike charging now; no history | Live | JSON | Portal API says OGL-Toronto; SOURCES.md says none stated (see Licence notes) | Station count today only |
| [Cycling Network](https://open.toronto.ca/dataset/cycling-network/) (our `raw/bikes.geojson`) | Current bikeways, with INSTALLED and UPGRADED year per segment | Snapshot 2026-09-14 | GeoJSON 3.3 MB | Portal API says OGL-Toronto (see Licence notes) | **Yes**, for km by install year (current network only) |
| [Bikeways (retired package)](https://open.toronto.ca/dataset/bikeways/) | Older network snapshots, same schema | Last edits Aug 2019 (2945 file) and Jan 2023 (4326 file); plus an older, undated centreline-based shapefile | GeoJSON 3–4 MB | OGL-Toronto | **Yes**, as dated snapshots for a before-and-after |
| [Permanent Bicycle Counters](https://open.toronto.ca/dataset/permanent-bicycle-counters/) | Riders in the lane at a counter, daily and 15-minute counts | 1994–2019 (retired sites); most current sites from late 2022; 13 added in 2025–26 | CSV: daily 6 MB; 15-minute 29–87 MB per file | OGL-Toronto | **Partly**: a few sites support 2023–2025 comparisons (see Counters) |
| [Bicycle Cordon Count 2010, 2013, 2014](https://open.toronto.ca/dataset/bicycle-cordon-count-2010-2013-2014/) and [Bicycle and Micromobility Cordon Count 2022](https://open.toronto.ca/dataset/bicycle-and-micromobility-cordon-count/) | People crossing the downtown cordon (Bloor, Spadina, Queens Quay, Jarvis), 7 a.m.–7 p.m., one fall weekday | 2010, 2013, 2014, 2022 (a September 2024 count is due in 2026 but not on the portal yet) | CSV, under 3 MB | OGL-Toronto | **Yes**, for downtown counts on 62 matched site-directions |
| [Traffic volumes at intersections (TMC)](https://open.toronto.ca/dataset/traffic-volumes-at-intersections-for-all-modes/) | Bikes through intersections on count days | 1984 to now; bikes not always counted before 2014 | CSV 50–90 MB a decade | OGL-Toronto | Ad hoc locations and dates; not a trend source |
| TTS via the [DMG iDRS](https://dmg.utoronto.ca/idrs/) | Weekday trips by primary mode, from a household survey | 2011, 2016, 2022 (and earlier) | Hand-exported cross-tabs | As credited on the downtown-weekday page | **Yes**, through the hand exports below |
| [City: "Impact of Bill 212: Bike Lanes Framework"](https://www.toronto.ca/legdocs/mmis/2024/cc/bgrd/backgroundfile-250546.pdf) (CC23.1a, made public Dec 18, 2024) | City staff's TTS mode shares, 2001–2022 | 2001–2022 | PDF | City report | **Yes**, as a check on our exports and a citable figure |
| Census journey to work, via the City's [Neighbourhood Profiles](https://open.toronto.ca/dataset/neighbourhood-profiles/) | Main mode of commuting, people with a usual or no fixed workplace | 2011 (NHS), 2016, 2021 | CSV / XLSX (2021 already in `raw/`) | OGL-Toronto (Statistics Canada data) | **Yes**, with the May 2021 caveat |
| [Toronto Cycling Year in Review 2025](https://www.toronto.ca/wp-content/uploads/2026/03/8fa8-2025-Toronto-Cycling-Year-in-Review-FINAL.pdf) (Mar 2026) and [2024](https://www.toronto.ca/wp-content/uploads/2025/04/97a9-2024-Toronto-Cycling-Year-in-Review-FINAL.pdf) | City's annual figures: km installed, network totals, Bike Share, counters | 2019–2025 | PDF | City report | **Yes**, citable; check figures against open data |

## 1. Bike Share ridership

Package `bike-share-toronto-ridership-data`: owner Toronto Parking Authority, licence OGL-Toronto, refresh
"Monthly", last refreshed November 10, 2026. The 2024, 2025 and 2026 zips were all re-uploaded that day.

**Files**: 2014–2015 is station-level totals by quarter (XLSX), not trips. 2016 is one XLSX with Q3 and Q4 only
(585,531 trips): the portal notes a change of software provider in July 2016. 2017–2019 are quarterly CSVs,
2020–2023 monthly CSVs, and 2024, 2025 and 2026 one CSV per year (the 2025 zip has 12 monthly files).

**Fields, in four schemas over the years:**
- 2017–2018: `trip_id`, `trip_start_time`, `trip_stop_time`, `trip_duration_seconds`, `from_station_name`,
  `to_station_name`, `user_type`, plus station ids from 2018. The 2017 H1 files write dates day-first; parse them
  per file.
- 2019–2023: `Trip Id`, `Trip  Duration` (two spaces), `Start Station Id`, `Start Time`, `Start Station Name`,
  `End Station Id`, `End Time`, `End Station Name`, `Bike Id`, `User Type`.
- 2024 onward: `Trip_Id`, `Trip_Duration`, `Start_Station_Id`, `Start_Time`, `Start_Station_Name`,
  `End_Station_Id`, `End_Time`, `End_Station_Name`, `Bike_Id`, `User_Type`, **`Bike_Model`**
  (ICONIC = classic; EFIT and EFIT G5 = e-bikes; ASTRO appears in 2026 and is unidentified).
- No coordinates in the trip files: join station ids to the GBFS `station_information` file. Old ids may be
  missing from today's feed.
- Mixed encodings, and 249 short rows in October 2020. Read the bytes as latin-1 and count every row; DuckDB's
  strict reader rejects some files.
- The readme (XLSX, last updated April 2022) doesn't cover `Bike_Model` or the 2024 schema.

**Rides per year, counted from the open data** (script logic: one row = one trip; trip ids are unique except for
13 duplicates in 2021):

| Year | Rows in open data | City/TPA published | Note |
|---|---|---|---|
| 2017 | 1,492,369 | — | |
| 2018 | 1,922,955 | — | |
| 2019 | 2,439,517 | — | |
| 2020 | 2,911,308 | 2.9 M | |
| 2021 | 3,575,182 | 3.4 M | Published figure is lower than the file count; ask TPA |
| 2022 | 4,300,240 | 4.5 M | **November 2022 file missing from the zip** |
| 2023 | 5,713,141 | 5.7 M | |
| 2024 | 6,953,094 | 6.9 M | |
| 2025 | 7,812,520 | 7.8 M | |
| 2026 Jan–Sep | 6,830,174 | — | Through Sep 30 |

Same months each year (January–September): 2021 2,819,257; 2022 3,620,479; 2023 4,461,078; 2024 5,351,478;
2025 6,211,164; 2026 6,830,174.

E-bike rides (`Bike_Model` EFIT + EFIT G5): 1,073,937 in 2024 and 1,513,762 in 2025. The City reports
1.5 million e-bike rides in 2025, up 40% on 2024, which matches. 2026 to September: 1,449,437 on EFIT, plus 68,322
on ASTRO.

Published figures: the City's [2025 Cycling Year in Review](https://www.toronto.ca/wp-content/uploads/2026/03/8fa8-2025-Toronto-Cycling-Year-in-Review-FINAL.pdf)
lists rides of 2.9, 3.4, 4.5, 5.7, 6.9 and 7.8 million for 2020–2025, 180 new stations in 2025 and 10,161 bikes
(including 2,000 e-bikes). The TPA's [2025 Annual Report item](https://www.toronto.ca/legdocs/mmis/2026/pa/bgrd/backgroundfile-287028.pdf)
gives 7.8 million rides in 2025.

**`User_Type` is unreliable in 2022–2023.** The files give 2,664,495 casual and 1,635,745 annual rides in 2022,
and 5,348,784 casual and 364,357 annual in 2023. In 2024 they give 5,366,185 member and 1,586,909 casual. The
2022–2023 labels look swapped or remapped, so don't chart member versus casual across those years without asking
TPA.

## 2. TTS: the export list

What the 2022 [Data Guide](https://dmg.utoronto.ca/pdf/tts/2022/2022TTS_Data_Guide.pdf) says matters for
comparisons:
- **Ages.** 2022 records trips for people **5 and over**; 2016 and earlier recorded only **11 and over**.
- **Walk trips.** 2022 added non-commute walk trips, which changes every mode's share. The trip variable
  **`excl2016`** handles both: 0 = comparable with 2016; 1 = person aged 5–10; 2 = non-commute walk by someone 11+.
  Use `excl2016 In 0` on every 2022 export meant for comparison.
- **E-scooters.** A new 2022 mode, `mode_prime` E. Code C is "Bicycle". The City's figures use
  "Bicycle / Other Micromobility", so export E as its own column and report it beside C, not inside it.
- **Survey period.** `trip_period`: 1 = fall (Sept 13 to Dec 19, 2022), 3 = spring (Jan 3 to Jul 24, 2023).
  Cycling is seasonal, so a fall-only 2022 run is the fairer match for earlier fall surveys. The guide says the
  2011 cycle ran in fall 2011 and fall 2012; check the 2016 guide for its dates before saying "fall to fall".
- **Weekdays only.** TTS records only weekdays (`trip_day` 1–5, a household variable). Leave it unfiltered unless
  you want Tuesday–Thursday only; downtown-weekday's method note already says the sample leans to Thursday and
  Friday.
- **Expansion.** Keep iDRS's default expanded totals, as in the existing `raw/tts/` files; don't switch to sample
  counts.

Exports: **Trip** table (not Person), one per year. iDRS lists each variable as "description - name" (e.g. "Primary travel mode of trip - mode_prime"); match on the name after the dash (2011, 2016, 2022). Save each as downloaded into `cities/toronto/raw/tts/`, with
the year in the file name, as before. "Toronto" means PD 1–16.

1. **City-wide share, same definition as the City's Figure 1.**
   Row `mode_prime`, Column `pd_dest` (same in all three years; the share needs only the row totals).
   Filters: `pd_orig In 1-16` and `pd_dest In 1-16`; 2022 also `excl2016 In 0`.
   Check: bicycle + micromobility should come to about 3.1% (2016) and 4.4% (2022).
2. **Trips into downtown (the City's Figure 3).** Row `mode_prime`, Column `pd_orig`.
   Filters: `pd_dest In 1`, `pd_orig In 1-16`; 2022 `excl2016 In 0`.
   Check: about 6.4% (2016) and 9.3% (2022).
3. **Trips within downtown** (start and end in PD 1; probably where cycling's share is highest).
   Row `mode_prime`, Column `start_time`. Filters: `pd_orig In 1` and `pd_dest In 1`; 2022 `excl2016 In 0`.
4. **Downtown by hour for 2016 and 2011**, matching the 2022 files we already have:
   - `trips_into_pd1_by_hour_mode_<year>`: Row `start_time`, Column `mode_prime`, Filters `pd_dest In 1` and
     `pd_orig Not In 1`.
   - `trips_out_of_pd1_by_hour_mode_<year>`: the same with origin and destination swapped.
   - Also re-export the 2022 pair with `excl2016 In 0`. Today's 2022 files include ages 5–10 and non-commute
     walks, so they can't be set beside 2016 as they are.
5. **Fall-only check for 2022**: repeat exports 1 and 2 with `trip_period In 1` added. Report both runs if they
   differ by more than a few tenths of a point.
6. **Optional, work trips only** (the City's Figures 2 and 4): exports 1 and 2 with `trip_purp In 1` (2022) or the
   home-based-work purpose pair (2011, 2016).

PD 1's boundary: the City's report compares PD 1 directly from 2001 to 2022, so treat it as stable. To check, the
2022 trip table also carries `gta06_orig` / `gta06_dest`, so trips into PD 1 can be counted on 2006 zones in
both years.

**Return-to-office caveat (fall 2022).** Downtown commuting was still recovering, so total trips into PD 1 fell
between 2016 and 2022. A higher cycling share can come from fewer trips by other modes as well as from more
trips by bike, so always show the trip counts beside the share. The City's
[Figure 6](https://www.toronto.ca/legdocs/mmis/2024/cc/bgrd/backgroundfile-250546.pdf) gives the count
city-wide: 139,057 daily bicycle and micromobility trips in 2016 and 172,441 in 2022 (people 11+).

### Results (exports received November 11, 2026)

Files in `cities/toronto/raw/tts/`, as downloaded. Export 2 wasn't needed: the PD 1 column of export 1 is trips
from across Toronto into downtown. Export 5 (fall only) was run for within-Toronto; export 6 wasn't run.

**Our exports reproduce the City's figures** (bike share of trips, people 11+; 2022 adds e-scooters as the City does):

| | 2011 | 2016 | 2022 |
|---|---|---|---|
| Within Toronto, ours | 2.09% | 3.10% | 4.38% (bike alone 4.15%) |
| Within Toronto, City | 2.1% | 3.1% | 4.4% |
| From Toronto into downtown, ours | 5.11% | 6.41% | 9.24% (bike alone 8.93%) |
| From Toronto into downtown, City | 5.1% | 6.4% | 9.3% |
| Daily bike trips within Toronto, ours | 95,312 | 139,059 | 163,658 + 8,781 e-scooter |

**Fall only (2022)** changes little: within Toronto 4.16% by bike (4.35% with e-scooters); into downtown 8.78%
(9.03%). The rise since 2016 is not a seasonal effect. The fall-only file's trip totals are only fall's part of the
weighted year (2.83 M against 3.94 M), so use it for shares, never counts.

**Downtown counts tell a different story from the shares** (all origins, 2022 on the excl2016 definition):

| Trips by bike | 2011 | 2016 | 2022 |
|---|---|---|---|
| Into downtown from outside it | 17,210 | 26,197 | 25,780 (+901 e-scooter) |
| Out of downtown | 17,027 | 25,600 | 25,485 (+917) |
| Within downtown | 23,145 | 34,895 | 39,385 (+1,505) |
| All trips into downtown, every mode | 713,611 | 751,917 | 551,176 |
| Bike share of trips into downtown | 2.4% | 3.5% | 4.7% |
| Bike share of trips within downtown | 7.6% | 8.2% | 11.6% |

Between 2016 and 2022, bike trips into downtown held level (−2%) while all trips into downtown fell 27% (the
return-to-office year), so the share rose without more riders. Within downtown, bike trips rose 13%. Say "held
their ground while other trips fell" for trips into downtown; never "more people cycle downtown" on these figures.

## 3. Cycling network: km by year, and removals

From our `raw/bikes.geojson` (City snapshot of 2026-09-14, 1,581 segments). Lengths are geodesic centreline km,
not lane km: a street with a lane on each side counts once. Classes are `bikes.json`'s: protected = cycle tracks
incl. bi-directional and contraflow; painted = bike lanes incl. buffered and contraflow.

- **Total now**: protected 110.5, painted 141.6, shared 185.8, trails 401.5 = 839.3 km. The City's own end-2025
  figures are 110.1 km of cycle tracks, 143.8 km of bike lanes and **745.3 km in total**
  ([2025 Year in Review](https://www.toronto.ca/wp-content/uploads/2026/03/8fa8-2025-Toronto-Cycling-Year-in-Review-FINAL.pdf)).
  The total differs because the City leaves some types out (likely signed routes, park roads and trail entrances).
  **Quote the City's 745 km, not ours.**
- **Km by INSTALLED year (protected / painted), 2014–2025**: 2014 3.8 / 3.2 · 2015 3.9 / 2.4 · 2016 3.4 / 0.8 ·
  2017 3.0 / 6.0 · 2018 4.4 / 4.2 · 2019 1.8 / 0.6 · **2020 27.1** / 2.9 · 2021 4.6 / 11.7 · 2022 5.9 / 4.3 ·
  2023 7.4 / 2.0 · **2024 11.5** / 4.5 · 2025 5.3 / 3.1.
- **Km by UPGRADED year** (an existing facility made better), protected: 2020 16.5, 2021 5.4, 2023 4.0, 2024 5.8,
  2025 5.0.
- **Limits of the install years.**
  - 2001 is a catch-all: 274 km of trail and 14 km of "protected" carry INSTALLED 2001, the amalgamation default.
  - INSTALLED is when a segment first got any facility, and the type is today's. A 2007 painted lane upgraded to a
    cycle track in 2020 counts as protected km installed in 2007.
  - Some UPGRADED values are `1`.
  - Removed segments aren't in the file at all.
  - The City's own install figures (17.8, 19.6, 26.7 and 14.1 km in 2022–2025) count new installs differently.
    Quote theirs for "built per year" and use ours only for the shape over time.
- **Dated snapshots of the whole network** (protected / painted km):
  - About 16 / 111 km, from the 2945 GeoJSON in the retired `bikeways` package, last edited Aug 15, 2019.
    Geometry is in a projected CRS; length is `Shape__Length` ÷ 1.383, the Web-Mercator factor checked against
    the 2023 file, so it's approximate.
  - 73.9 / 131.5 km on Jan 25, 2023 (the 4326 GeoJSON in the same package).
  - 110.5 / 141.6 km on Sep 14, 2026 (today's file).
- **Diff, Jan 2023 → Sep 2026** (each 2023 protected or painted segment checked for the same class within 20 m):
  - Kept: 71.0 km protected, 129.3 km painted.
  - Reclassified or downgraded: 1.9 km protected (Bayview Ave bi-directional) and 2.2 km painted
    (West Rd, Colborne Lodge Dr, Victoria Park Ave, Norway Ave).
  - Missing: about 1.0 km (Villiers St, Port Lands rebuild).
  - So through mid-September 2026 the City's file shows essentially no lane removals.

**Removals (Bill 212, which amended the Highway Traffic Act).**
- Timeline, from news reports:
  - Removals on Bloor, Yonge and University were blocked by injunction in April 2025 and by a Superior Court ruling
    on July 30, 2025.
  - The Court of Appeal reversed that ruling in August 2026
    ([Cycle Toronto v Ontario (AG), 2026 ONCA 582](https://www.mondaq.com/article/1840770/court-of-appeal-reaffirms-the-limited-role-of-the-courts-in-charter-claims)).
  - In December 2025 the Province had already reconfigured a 600 m stretch of Bloor St W (a car lane added, the
    bike lane kept).
  - It then removed the lanes on **1.2 km of Bloor St W between Clissold Rd and Royal York Rd: work began
    October 13–14 and was declared complete October 30, 2026**
    ([CBC, Oct 8](https://www.cbc.ca/news/canada/toronto/bike-lane-removal-work-etobicoke-9.7374696);
    [CP24, Oct 30](https://www.cp24.com/local/toronto/2026/10/30/bloor-west-bike-lane-removal-complete-ontario-transportation-minister-confirms/)).
  - The Minister said more removals would come in the next construction season. Reports put the targeted total
    at 19 km across the three streets.
- In our September file that stretch is still "Cycle Track", inside two long segments: Runnymede Rd → Aberfoyle
  Cres (3.66 km, installed 2023) and Aberfoyle Cres → Resurrection Rd (1.0 km, installed 2024). Yonge
  (Hayden–Davisville) and University are also still in the file.
- **No source records removals as data**: no status field or "removed" date in any City package, and no provincial
  open dataset was found.
- A before-and-after can be built only from dated snapshots (2019, 2023, Sep 2026, then our monthly
  *Fetch bike lanes* commits of `raw/bikes.geojson`). Clip the long segments to the limits in the Province's
  construction notice, and date each change from MTO notices and news, not from the City's file. The City file's
  refresh is "Semi-annually", so it may lag the street by months. Check the next file for whether the stretch was
  deleted or reclassified (for example to painted).

## 4. Counts

**Permanent counters** (package `permanent-bicycle-counters`, OGL-Toronto, monthly; daily file to Oct 8, 2026).
- 59 location-direction rows. Retired sites run 1994–2021 (Bloor E at Castle Frank from 1994, Sherbourne
  2014–2019, Bloor W 2018–2021). Current sites mostly from Oct–Nov 2022; 13 more were added in 2025–26 (Adelaide,
  Richmond, Queens Quay, Lake Shore W, Dundas E, Sheppard E, Steeles E…).
- The City's caveats: counts include e-bikes and e-scooters; only riders inside the lane are counted; blockages
  show as 0; **many detectors were down 2019–2022**; and calibration can change counts retroactively.
- **Nearly every site was recalibrated in June–July 2026** (`latest_calibration_study`).
- Average daily riders, April–September, days with both directions counted:

| Counter | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|
| Bloor St W, east of Palmerston | 4,629 | 4,813 | 5,475 | 4,310 |
| Yonge St, north of Bloor | 1,528 | 2,079 | 2,176 | 1,687 |
| Sherbourne St, north of Gerrard | 1,915 | 1,998 | 1,942 | 1,883 |
| Yonge St, north of St Clair | 1,156 | 1,486 | 1,491 | — |

- The 2026 drop on Bloor and Yonge is steady in every month (not zero days), but not on Sherbourne. It may be the
  2026 recalibration, construction or a real change. **Don't publish 2026 versus 2025 counter changes until the
  City confirms**; 2023 → 2025 is safer.
- The City's own figures: Bloor W west of Huron averaged 3,524 a day in 2025, with a peak of 7,953 on Sept 16.

**Cordon counts.** Downtown inner cordon, 7 a.m.–7 p.m., one mid-week early-fall day each year. On the 62
site-directions counted in all four years:

| Year | Riders |
|---|---|
| 2010 | 28,392 |
| 2013 | 31,216 |
| 2014 | 31,362 |
| 2022, bicycles (standard, cargo, Bike Share, e-bike) | 31,544 |
| 2022, all devices incl. e-scooters and mopeds | 34,662 |

These are single days, so weather matters. The September 2024 count isn't published yet.

**TMC intersection counts** have bikes from 2014 on, at ad hoc places and dates. Use them only for a specific
corner, not a trend.

## 5. Census and City reports

**Census main mode of commuting, City of Toronto**, from the City's Neighbourhood Profiles (OGL-Toronto;
Statistics Canada data; 25% sample):

| Year | By bicycle | All commuters | Share | Note |
|---|---|---|---|---|
| 2011 | 25,350 | 1,174,610 | 2.2% | National Household Survey, voluntary; less comparable |
| 2016 | 34,355 | 1,251,055 | 2.7% | |
| 2021 | 15,705 | 791,510 | 2.0% | Sum of the 158 neighbourhoods (rounded values) |

The 2021 count was taken in May 2021, during pandemic lockdowns, so it shows the pandemic, not a trend; don't
chart 2016 → 2021 as a decline in cycling. Statistics Canada's own City-level table couldn't be fetched from
here; take the official 2021 figure from the Census Profile (CSD 3520005) by hand before publishing.

**City cycling reports, Year in Review 2024 and 2025.**
- Km installed per year: 17.8 (2022), 19.6 (2023), 26.7 (2024), 14.1 (2025); plus 9.0 km upgraded in 2025.
- Network: 745.3 km, including 110.1 km of cycle tracks.
- Cycling budget: $192.5 M across 2019–2025.
- Bike Share figures as in section 1.
- Cycling deaths and serious injuries by year 2016–2025 (2025 provisional).
- The 2024 report notes a daily Bike Share record of 35,000 trips on September 19, 2024.

## What we could verify (headline numbers)

1. Bike Share: 1.92 M rides (2018) → 7.81 M (2025), from the open data and matching the City's figures.
   January–September 2026: 6.83 M, +10.0% on the same months of 2025.
2. E-bike rides on Bike Share: 1.07 M (2024) → 1.51 M (2025).
3. Protected bike lanes on the City's map: about 16 km (2019 data) → 74 km (Jan 2023) → 110 km (Sep 2026).
   City's end-2025 figure: 110.1 km.
4. TTS, City-published, people 11+:
   - Bike/micromobility share of trips within Toronto: 3.1% (2016) → 4.4% (2022).
   - Share of trips from Toronto into downtown: 6.4% (2016) → 9.3% (2022).
   - Daily trips: 139,057 → 172,441.
   - Our own exports reproduce all three (see section 2, Results).
   - Bike trips into downtown from outside it: 26,197 (2016) → 25,780 (2022), while all trips into downtown fell 27%.
     Bike trips within downtown: 34,895 → 39,385.
5. Census bicycle commuters: 34,355 (2016); the May 2021 count isn't comparable.
6. Downtown cordon (62 matched sites): 28,392 (2010) → 31,544 bicycles (2022).
7. Bloor St W, Clissold–Royal York: 1.2 km of protected lanes removed by the Province, October 13–30, 2026. This
   is from news reports, not yet in the City's data.

## Commenters' numbers

The comments include their own figures for 2026 Bike Share rides. None of them is used. The 2026 figure above is
counted from the TPA files (to September 30). Re-check it when the October file lands.

## Recommended page and Reel (same style as downtown-weekday)

Path `/toronto/cycling-since-2016/` (or `/toronto/bikes-by-the-numbers/`). An Explainers card on the hub. A new
engine module would follow `engine/commute`: `cities/toronto/cycling.json` for the words, with small files
committed and reduced from the raw data (like `rideshare/`).

- **Title idea**: "Toronto's bike boom, counted" or "How much more does Toronto cycle than in 2016?"
- **Lede**: one number per measure, each with its unit. For example: "Bike Share riders took 7.8 million trips in
  2025, four times 2018. One in eleven trips from across Toronto into downtown is now made by bike or e-scooter,
  up from one in sixteen in 2016."
- **Section 1, Bike Share by month, 2017–2026.**
  - A line chart with a 2026-so-far marker and the missing November 2022 shown as a gap.
  - A toggle for classic versus e-bike from 2024.
  - Seasonality is the visual hook (the winter dip, a summer peak above 1.2 M a month).
- **Section 2, the network over time.**
  - Map of today's bikeways coloured by install year, with a timeline slider like ttc-history.
  - Inset bars of protected km by year (the 2020 jump is when the City added 27 km of protected lanes).
  - A "removed in 2026" stretch drawn dashed, with its date and source, once the October snapshot or the
    Province's notice gives its exact limits.
- **Section 3, who rides where (TTS).**
  - Share and count of trips into downtown by mode, 2011 / 2016 / 2022, on the comparable definition.
  - The downtown-weekday dots, but bikes only, 2016 versus 2022.
- **Section 4, counters.** Bloor at Palmerston and Yonge at Bloor, by day of year, 2023–2025 (2026 once the City
  explains the recalibration).
- **Method** ("How this was counted"): one paragraph per source, saying what it counts and what it misses.
- **Credits**: Bike Share Toronto ridership data (Toronto Parking Authority), City of Toronto Cycling Network,
  Permanent Bicycle Counters and Cordon Counts (all Open Government Licence – Toronto); Transportation Tomorrow
  Survey (DMG, University of Toronto); Statistics Canada via City Neighbourhood Profiles.

**Reel (about 45 s, 4K portrait; Elle voiceover, burned-in captions):**
1. Hook: the comments asked how many Bike Share rides there have been this year. "6.8 million by the end of
   September." Number on screen with the source line.
2. Monthly line building from 2017 to 2026.
3. Map: bikeways appear year by year, protected lanes in lime; 2020 flashes.
4. Bloor West, October 2026: the stretch fades to dashed. "1.2 km removed by the Province, October 13–30." Say
   nothing about why.
5. Downtown share: 1 in 16 trips (2016) → 1 in 11 (2022), with the caveat card "fall 2022: offices still half
   empty".
6. Close: "Every number has a source. Link in bio."

## Wording rules (for cycling.json `_about`)

- Always name the measure: "Bike Share trips", "trips by bike in the TTS", "people who mainly cycle to work",
  "km of bikeways", "riders counted at the Bloor St counter". Never "cyclists in Toronto" or "ridership" unqualified.
- Bike Share is one system. Don't use its growth as the growth of all cycling.
- Don't say lanes "caused" more riding, or that removal "caused" anything. Show dates and counts side by side.
- Removals: "removed by the Province of Ontario under the Highway Traffic Act, as amended by Bill 212", with the
  date and length. No "ripped out", "war on", "gridlock" or "congestion" claims, and no opinion from either side.
  No politicians' quotes.
- TTS: "share of weekday trips" with the year and its caveat. "Bike or e-scooter" for 2022 if E is included; keep
  people 11+ in comparisons.
- 2021 Census: always "May 2021, during the pandemic".
- Counters: "riders counted in the lane", and mention the 2026 recalibration whenever a 2026 count appears.
- Km: "centreline km", and quote the City's total (745 km), not our sum.
- Round as the City does (millions to one decimal) unless the exact count is the point.
- No commenter numbers. Re-derive or drop.

## Licence notes

- Everything proposed is OGL-Toronto, Statistics Canada (via the City) or TTS as already credited. Nothing needs
  NONCOMMERCIAL.md.
- **Licence status to re-check.** SOURCES.md says the `cycling-network` and `bike-share-toronto` (GBFS) packages
  state no licence. The portal API (`package_show`) now returns `license_id: open-government-licence-toronto` for
  both. Check the packages' web pages; if they match, update SOURCES.md and the commercial re-check list
  (a separate change).

## Re-run

Downloads and scripts used here were scratch, kept outside the repo.
- Bike Share: the CKAN `package_show` for `bike-share-toronto-ridership-data`, then each `opendata.toronto.ca`
  zip (about 1.75 GB). Count rows per file with a latin-1 CSV reader. DuckDB needs latin-1 decoding and padding for
  short rows; the Actions pattern from `rideshare.py` would also work.
- Network: geodesic length per segment by INSTALLED and UPGRADED; class map as in `bikes.json`.
- Snapshot diff: segments projected to EPSG:2952, 20 m buffer, 60% coverage rule.
- Counters: daily CSV; April–September window; only days with every direction present.
