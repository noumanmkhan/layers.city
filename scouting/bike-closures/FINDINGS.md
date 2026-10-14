# Bike lanes closed by construction: data scouting (October 14, 2026)

Asked on social media: "Can you filter for bike lanes closed due to construction?" Scouting only, nothing built.
Run: `.github/workflows/scout-bike-closures.yml` → `scouting/bike-closures/out/` (summary.json, toronto.json,
chicago.json, scout.log). Permits active today or starting within 7 days, matched against each city's bike network.

## Headline
- Neither city says which lane a permit closes. No field, type or flag for bike lanes in either feed; words like
  "bike lane" appear only in free text, rarely and unreliably (one Chicago fibre job pastes "use of ... bike lanes
  where required" onto every permit; a Toronto note says "northbound bicycle lane open").
- Matching permits to the bike network works and is cheap (both networks are open, line geometry, current).
  What it honestly yields is **"construction on a street with a bike lane"**, plus a closure level
  (Toronto: road closed vs work zone with Low/Medium/High impact; Chicago: Full / Partial / Curb lane).
  It can't promise the lane itself is shut.
- So: possible as "Work on bike routes" (a layer or card rows), not as "bike lanes closed". The strongest
  claim we can make is a **full road closure on a street with a bike facility**: the lane is closed too.
- It means taking in all permits, not just transit ones (today's closures layer keeps transit work only).

## Toronto
- Road restrictions feed: 2,855 records, 2,632 active or starting within a week. Fields: type (CONSTRUCTION
  2,191 / ROAD_CLOSED 661 / HAZARD 3), maxImpact and currImpact (Low/Medium/High), directionsAffected, roadClass,
  daily schedule, source/workEventType (Toronto Hydro, Toronto Water, Enbridge, Metrolinx…), polyline,
  specialEvent. No lane or bike field.
- Bike words in text: 26 active records, mostly projects building bike facilities (a hydro-corridor
  trail in Etobicoke, Morningside Ave cycle track) or one-offs ("cyclists temporarily merged" on Spadina).
- Cycling Network (CKAN cycling-network, refreshed Sept 14, 2026, 1,581 segments; no licence stated on the
  package, so on the commercial re-check list): INFRA_HIGHORDER = Bike Lane, Cycle Track, Bi-Directional,
  Contraflow, Buffered, Sharrows, Signed Route, Multi-Use Trail…
- Match (permit line runs ≥25 m within 15 m of a facility on the same street): 436 permits.
  - 115 of them are this weekend's Waterfront Marathon (specialEvent = Yes); a build would treat events apart.
  - Of the other 321: 215 on bike lanes or cycle tracks (14 full road closures, 201 work zones), the rest on
    sharrows, signed routes and trails. Only 36 run 100 m or more along the lane; most are a single utility cut.
  - By source: Hydro, Water, Enbridge and City road work dominate; Metrolinx is 17.
- Park trails: trail closures (Parks) are mostly not in this feed.

## Chicago
- CDOT permits: 53,645 active rows. streetclosure: blank 38,262, Curblane 5,014, NA 4,857, None 2,901,
  Sidewalk 1,356, Full 768, Partial 485. No lane or bike field.
- Bike words: 367 active rows, mostly one fibre contractor's boilerplate; not usable as a filter.
- Bike Routes (hvv9-38ut, updated Dec 2025, 1,008 segments): Bike Lane 285, Neighborhood Greenway 258,
  Buffered 184, Protected 174, Marked Shared Lane 107.
- Match (permit point within 40 m of a route on the same street): 930 of 6,267 Full/Partial/Curblane permits:
  Full 80, Partial 88, Curblane 762. On protected lanes: 104 (Full 9, Partial 15, Curblane 80).
- "Curblane" is the parking/curb lane. On a protected lane (curbside, behind parked cars) a curb-lane permit
  very likely blocks it; on a painted lane beside parking it may or may not. 657 of 930 have an address range,
  so the 800-a-mile grid can draw the stretch as we do for RLE.
- 737 of 930 are "Opening in the Public Way" (utility cuts), often short.

## If built later (not decided)
- Honest wording: "Work on bike routes" / "Construction on streets with bike lanes", with Full closures shown
  as closed and the rest as "work on this stretch".
- Volume is high compared with today's transit closures (Toronto ~200–300, Chicago ~900 at a time): filter by
  facility (lanes, tracks, protected; skip sharrows/greenways?), by closure level, or by length.
- Daily fetch fits the existing closures job; drop special events (Toronto) or show them separately.
