# Along the way: bringing it to a new city


How to bring Along the way (web page + iOS 1.5 trip companion) to a city that already has a Routes page. Written after Toronto shipped; Chicago is the first city through it (handoff: claude/along-chicago-brief.md). Work runs in Claude Code on the Mac, on the internal drive; chat writes the briefs.

## What is already city-agnostic (checked against main, b855ba8, Nov 18)
- **Engine:** `engine/along/build.py`, `router.js`, `page.html` name no city. A city joins by adding `cities/<city>/along.json`.
- **Refresh:** `refresh-fact-sheets.yml` already rebuilds Along for every city that has an `along.json`.
- **App gating:** the iOS app finds Along through the `along` block in the city's published `city.json` (DATA_CONTRACT.md section 18, written by `along_meta.py`). If 1.5 really keys on that block alone, a new city needs no app release, only data.
- **Universal Links:** `apple-app-site-association` already matches `/*/along/*`, so "Take this trip in the app" works for any city.
- **Toronto status:** `cities/toronto/along.json` now has `"unlisted": false` (public). The "unlisted" status in claude/along-the-way.md is out of date.

## What is Toronto-shaped (fix once, during the first new city)
Items 1 to 4 were fixed for Chicago (commits 6b6cc9a9, bcf0a8b0, 5aeda262 on dev, Nov 18): night-only routes are the only ones dropped; along.json `express` lists a city's express buses (or the `exp` family is used); `attachStrip` holds the name words; each city has its step in `fetch-discover.yml`.
1. **Night routes:** `build.py` drops every route flagged `night`. In Toronto that flag means the overnight-only 300s. In Chicago it marks **24-hour Owl service on trunk routes** (4 Cottage Grove, 9 Ashland, 20 Madison, 22 Clark, 49 Western, 66 Chicago, 77 Belmont, 79 79th and others), so as it stands Chicago's busiest buses would disappear from Along. Drop only night-only routes.
2. **Express speed:** `router.js` treats a bus as express only if its number matches `^9\d\d$` (the TTC's 900s). Chicago's express routes (X4, X9, X49, J14 and others) carry an `exp` flag. Make the rule data-driven, keep Toronto's output identical, and keep router.js plain ES5, since the app runs it byte for byte.
3. **Name matching:** `ATTACH_RX` in `build.py` has "toronto public library" in it. Move it to the city's `along.json`.
4. **Discover workflow:** `fetch-discover.yml` has `ALL="toronto"` and one step per city. Each city adds its step.
5. **Waits:** a boarding's wait is capped at 10 minutes, which suits frequent city transit. If a city ever keeps commuter rail in Along, that cap needs to be per mode, or the router favours the trains. Chicago skips Metra for now (user, Nov 18), so this waits for the regional-transit work.
6. **Speeds:** there's one speed per mode for every city. The CTA 'L' is mode `subway` at 32 km/h. Calibrate it against the agency's scheduled run times before trusting the detour numbers.

## The workflow (stop for the user at each gate)

**0. Preflight (no code).**
- The Routes page exists and is fresh (`docs/<city>/routes/data/stops.json`, `asof`).
- Map each of the city's map layers to Along's kinds (landmark, area, street, heritage, park, campus, library).
- List candidate Discover sources and their licences.
- Collect 3 real commutes from local testers to use as the page's "Try" trips.
- *Gate:* the user approves the mapping, the sources and the mode decisions.

**1. Discover layer.**
- Add `cities/<city>/discover.json` (sources, kind rules, credits) and `viewpoints.json` (hand-checked, each entry with a `checked` date). Add the city's step to `fetch-discover.yml`.
- Describe, don't rank. Quote city text with credit and never rewrite it. No businesses on the web.
- *Gate:* counts by kind, plus 10 sample places the user can sanity-check.

**2. `along.json`.**
- `skipModes`, the `pois` mapping, page wording (kind words, credits, caveat, outside/noMatch/noRoute lines), the 3 tries, `"unlisted": true`.

**3. Build and numeric checks.** Report as a table:
- Stops and patterns.
- Places by kind.
- Share of stops with at least one place within 5 minutes.
- The busiest downtown stop's place count (flood check: skyscrapers were dropped in Toronto for this reason).
- Each try's minutes against the agency's own trip planner (within ±20%).
- Toronto's figures beside the new city's.
- *Gate:* the user reviews the table.

**4. Web QA.**
- Phone dark and light, desktop.
- The three tries, address search scoped to the city, "Here".
- "Open the map", "Take this trip in the app".
- No console errors.

**5. iOS check (layers.city.ios).**
- Confirm that the entry point appears only because of the `along` block.
- In the Simulator, start a trip from the Transit tab on the city's routes.
- Play back a GPX of a real ride.
- Unit-test the detour number against the web for one of the city's trips.
- Check line badges and colours for the agency's route ids (e.g. CTA `Brn`, `Org`).
- If anything needs app code, it goes in a 1.5.x build. Otherwise the city ships as data only.

**6. Testers.**
- Make a TestFlight group per city. External testers need Beta App Review for the build; internal testers must be App Store Connect users.
- Give them a short tester script: two commutes they already ride, one ride "just to see things", and what to report.
- Feedback comes in through TestFlight's screenshot feedback, plus the "report an issue" flag on each place.

**7. Go public (the user decides).**
- Flip `unlisted`, add the map's Getting around row and a hub link.
- Add a Notion row, update the project doc, and optionally make a Reel.

## Learned on Chicago (Nov 18)
- **Express in name only:** the CTA's "Express" routes ran no faster than locals in the schedule (285 vs 291 m/min). Only the 2, 100, 169 and 192 earn the 400 m/min express speed; along.json `express` lists them. The page's green badge still follows the agency's `exp` family (`RS.expBadge`).
- **Loop lines:** the Routes build placed a rapid line's platforms by projecting onto its shape, which scrambles lines that pass a point twice (the Loop). Fixed in `engine/routes/build.py` (first pass along the line); it also corrected Melbourne's City Loop.
- **Badges:** a city whose buses are filled (CTA grey) sets `--rb-ring:none` and `--rb-dark` in `factsheet.css`; the page used to force Toronto's outline on every badge, drawing Chicago's bus legs in white.
- **Map layers:** along.json `page.mapLines` and `page.mapAreas` name the basemap's line and area layers (Toronto: subway_lines, neighbourhoods).
- **Two lists, one building:** a city's landmark list and the National Register name the same building differently. discover.json `sameSpot_m` (16 m in Chicago) merges same-kind places from two sources that close.
- **iOS testing before data is live:** DEBUG builds take `-dataBase http://localhost:8765/` (release/1.5.1) to read the dev site; clear the app group's `refreshed.<city>` default (`xcrun simctl spawn <udid> defaults delete <group plist> refreshed.<city>`) so it re-downloads. `scripts/along-gpx.py --then` chains a second ride.
- **Report flag:** on the web only checked places (viewpoints) have "Report a problem"; the app has none on Along places. Testers report through TestFlight screenshots.

## Per-city sheet (copy one per city)
| Item | Value |
|---|---|
| Routes data asof | |
| skipModes (and why) | |
| Kind mapping (layer → kind, word) | |
| Discover sources + licence | |
| Viewpoints (hand-kept, count) | |
| Tries (from testers) | |
| Speed calibration (mode, model vs schedule) | |
| Web QA date | |
| iOS: data-only or 1.5.x? | |
| TestFlight group | |
| Public on | |

### Chicago
| Item | Value |
|---|---|
| Routes data asof | 2026-11-12 (CTA GTFS) |
| skipModes (and why) | rail (Metra, South Shore): another fare; regional later (user, Nov 18) |
| Kind mapping (layer → kind, word) | landmarks → landmark; known-as → area "Known as"; Special Service Areas → street "Business district" (industrial ones and Stockyards left out); Landmark Districts → heritage "Landmark district"; parks ≥ 1.5 ha → park; universities and colleges → campus; Chicago Public Library → library; Discover → view / art "Murals" / history "Historic places" |
| Discover sources + licence | Mural Registry, Individual Landmarks, National Register list (City of Chicago Data Portal, its Terms of Use, disclaimer on Attributions); 954 places (art 406, history 546, view 2) |
| Viewpoints (hand-kept, count) | 2: Northerly Island, Palmisano Park (checked Nov 18) |
| Tries (from testers) | placeholders until testers send theirs: Logan Square → the Loop, Hyde Park → River North, Andersonville → the West Loop |
| Speed calibration (mode, model vs schedule) | 'L' 1.02 of schedule overall (0.76 to 1.37 by trip); local buses 0.90; express list 2, 100, 169, 192; no speed override |
| Web QA date | Nov 18 (phone light and dark, desktop; screenshots/along-chicago/) |
| iOS: data-only or 1.5.x? | Data only. release/1.5.1 holds test tooling only (DEBUG `-dataBase`, GPX chaining, Chicago model checks) |
| TestFlight group | "Chicago" (external; needs Beta App Review) |
| Public on | (the user decides) |
