# Discovery points of interest: brief and task list

Copy of the project doc `claude/discovery-pois-brief.md` (claude.ai Project "Layers.City"), put here on
November 17, 2026 so Claude Code can read it. The project doc is the master: if they disagree, ask the user.

## What this is
Curated points of interest for city discovery, Toronto first, website only for now (whether any of it goes in the
iOS app is undecided). Murals and other public art, independent cafés, bakeries and restaurants, and shops with
character, plus film locations and photo spots later.

## User decisions (November 17, 2026)
- Refresh cadence: public art weekly; everything else monthly.
- Labels allowed: famous, iconic, historic, world-famous, long-running, independent. No "best" (describe, don't rank).
- City descriptions (StrollTO, Cultural Hotspot, Public Art) are **quoted with credit** under the Open Government
  Licence – Toronto, not rewritten.
- Every entry has a **`checked` date** (when its status was last confirmed), shown as "Checked Nov 2026".
- Each place gets a small **"report an issue" flag** that opens a prefilled GitHub issue. The user asked for this,
  so it is the one approved exception to CLAUDE.md's "don't link the site's pages to GitHub".
- **Chains:** only megachains are out (Tim Hortons, Starbucks and the like: places nobody makes plans to go to,
  "I need coffee, where's the nearest Tims"). Small local chains are in (Sam James, ~5 shops).
- **Stories are optional:** stories are sparse, so a missing founding year or lore line never rules a place out.
  Show one when found and cited.

## Kinds (exactly one per place)
| Family | Kinds |
|---|---|
| Public art | Murals & street art · Sculptures & statues · Monuments & memorials · Installations |
| Food & drink | Cafés & roasters · Bakeries · Restaurants · Markets & food halls |
| Character shops | Books · Records & music · Vintage & antiques · Comics, games & toys · Specialty food · Makers & oddities |
| Places | Viewpoints · Laneways & hidden spots · Notable buildings & details |

## Lenses (any number per place, including none)
| Lens | Adds |
|---|---|
| Seen on screen | Title + year |
| Photo spot | Type (skyline, alley, architecture, waterfront, seasonal), time of day, facing direction |
| Local lore | One line: what happened here / used to be / a first |
| Long-running | "Since 1962" |
| Seasonal | Blossoms, winter lights, patio-only, removed in winter |
| Hidden | Off the main drag |
| Famous / iconic / historic / world-famous | Status labels |

## Character test (businesses)
1. **Not a megachain:** national or multinational chains and franchises used for convenience are out.
2. **Somewhere people make plans to go:** a destination for what it sells or how it feels. A curator's call;
   signals: roasts or bakes in-house, a speciality, a distinct concept, longevity, press or guide coverage, a lens.
3. **Verifiably open:** confirmed from a current source, with a `checked` date.
Restaurants get the tightest filter (local institutions and destinations), or the list turns into a directory.

## Fields per place
name · kind · lenses[] · est (optional) · why (one line, our own words) · quote {text, credit} (City places) ·
screen [{title, years}] · status · checked (ISO date) · lat/lon · osm · notes · sources[]

## What scouting found (details in FINDINGS.md)
- City open data (all OGL–Toronto): Public Art (459 works), StrollTO (1,838 places with a paragraph each; ~267
  murals), Cultural Hotspot (845 points in the inner suburbs), Music Locations (record and instrument stores,
  mostly 2020 rows). StreetARToronto publishes no data: don't scrape it.
- OpenStreetMap gives candidates but almost no stories, and it is **stale for shops**: in the trial area, Dufflet's
  Queen West café (closed 2023), Craft Ontario at 1106 Queen W (closed July 2026) and Black Market's basement at
  256 Queen W (moved to 347 Queen W in 2019) are all still listed. Curated businesses need their own rechecks.
- Images: link to the City's image or page; don't rehost until each image's terms are checked.

## Trial batch
`pilot-queen-west-kensington.json`: 15 places in Queen West, Trinity-Bellwoods and Kensington. All are in under
the November 17 rules, including White Squirrel Coffee, Sam James (Ossington) and Moonbean.

## Tasks for Claude Code
Pull main first. One commit per step, plain-English messages, push to main.

1. ~~Add `"checked": "2026-11-17"` to every place in the pilot file.~~ Done (ff20284).
2. ~~Add `.github/ISSUE_TEMPLATE/place-report.yml` (label `place-report`).~~ Done (92478d1). Check the label
   exists and Issues are on (`gh repo view`).
3. Add a helper the future places page or card can call, e.g. `reportUrl(place, city, pageUrl)` in engine JS,
   building `https://github.com/noumanmkhan/layers.city/issues/new?template=place-report.yml&place_id=…&place_name=…&city=…&page_url=…`
   (URL-encoded; field ids must match the form). Keep it free of city names. Test that one URL opens the form
   filled in.
4. Add `scouting/discovery/stale.py`: list entries whose `checked` is over 180 days old; fail if any entry has none.
5. CLAUDE.md: note the place-report issue link as the approved exception to "don't link the site's pages to
   GitHub" (user, November 17, 2026).
6. Pilot file: make White Squirrel Coffee, Sam James (Ossington) and Moonbean regular entries; reword their
   "notes" so they no longer say they're held back (keep missing-year notes as plain facts). Update "_about":
   stories optional, only megachains excluded.
7. `scout.py`: replace the "likely chain" rule (same name at 4+ places) with a MEGACHAINS list (Tim Hortons,
   Starbucks, Second Cup, Aroma Espresso Bar, Country Style, Coffee Time, McCafé, CoCo, Chatime, Gong Cha, Real
   Fruit Bubble Tea, Kung Fu Tea, COBS Bread, Paris Baguette, Swiss Chalet, Pizza Hut, Freshii, Boston Pizza,
   The Keg, Jack Astor's and similar; match on brand, brand:wikidata or a normalised name). Rename the class
   "megachain". Small local brands stay in the candidate CSVs even with a brand tag; keep the old 4+ count as an
   informational column. Pushing reruns scout.yml; then update FINDINGS.md with the new counts.
8. Notion: add the follow-ups to the Notes of the row "Scouted discovery points of interest" (no new row).
