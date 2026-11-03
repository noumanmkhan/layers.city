# Election watcher: scouting findings (November 3, 2026)

Context: the Scarborough North federal by-election (December 7, 2026) wasn't picked up by the site. The weekly
representatives job showed the seat as vacant, but nothing knew a by-election had been called, and the where-to-vote
card only covers each city's own municipal or county election. Two passes in Actions (`scout.py`, `scout2.py`, raw
output in `out/`) checked each election agency for (1) something a weekly job can watch and (2) voting places as data.
The scouts identify themselves; sites that answered with a bot check were left alone.

## Per agency

| Agency | Watchable signal | Voting places as data |
|---|---|---|
| Elections Canada | No RSS. The yearly by-elections page lists each riding with its district number and polling day | **No.** Only per postal code ("Where do I vote?"), posted partway through. Polling division boundaries are open data |
| Elections BC | **RSS works** (elections.bc.ca/feed/) | **Yes.** *Provincial Voting Places* CSV/WMS plus voting-area → voting-place tables |
| Elections Ontario | None readable: answers automated readers with HTTP 406 | Unknown (same block) |
| City of Toronto | City news RSS (toronto.ca/news/feed/) | Yes, already used |
| City of Vancouver | Elections page blocks automated readers (403) | Yes, already used (`voting-places-2026` dataset) |
| NYC Board of Elections | No feed; an "Important Notices" page | PDFs + State GIS points, already used |
| Chicago Board of Elections | rss.xml exists but is empty | Vote centers table, already used; precinct places only via a name + address lookup |
| Dallas, Denton counties; SF Dept of Elections | Sites answer with a bot check | Already used for November 3 (live layers, API, xlsx) |
| Tarrant, Collin counties | No feed found | Already used |

### Elections Canada details
- `content.aspx?section=ele&dir=2026&document=index&lang=e` lists the 2026 by-elections. Each riding links to
  `dir=2026/<district number>`, e.g. Scarborough North = **35095**, which is the same number as in the 2025 federal ridings
  layer. A watcher can match those numbers to the map's ridings directly.
- The Voter Information Service has pages per district that need no postal code (`Scripts/vis/EDInfo?ED=35095&EV=66…`): polling day,
  advance-poll days (Nov 27–30), local Elections Canada office (1250 Markham Rd) and its hours, candidates (nominations close
  Nov 16) and a "Where do I vote?" entry.
- Polling station addresses are only shown for a postal code. Scraping that per postal code would be against the spirit
  of the service, so the card should link to the riding's page rather than name a station.
- Open data: 2025 polling division and advance polling district boundaries (Open Government Licence – Canada; 95 MB and
  42 MB shapefiles; also on geo.ca as a MapServer). These are boundaries only, with no station addresses.
- News releases page (`section=med&dir=pre`) carries "A federal seat is vacant in …" and "by-elections now under way" items.

### Elections BC details
- *Provincial Voting Places* (BC Data Catalogue, Elections BC Open Data Licence, updated October 2026): 5,754 rows with
  address, building, district, type (advance / general), wheelchair access, event name and date, and advance voting days.
  The file holds past events back to the 2017 general election; whether by-elections are included is still to be checked.
- *Provincial Voting Areas to Voting Place Assignment Tables* map each voting area to its general voting place.
- Vancouver's provincial ridings could get a where-to-vote card for any provincial event, by-elections included, built the
  way Toronto's municipal one is.

## Signals that need no agency at all
- **Vacancies.** Every Canadian by-election starts with a vacant seat, and the representatives jobs already notice those
  ("MP not found (seat may be vacant)"). A seat going empty is an early, agency-independent signal: "by-election expected".
- **Google Civic Information API** (US): its Elections endpoint (still supported after the Representatives API was turned
  down in April 2025) lists upcoming US elections by division. It needs a free API key. Its voter-info endpoint returns
  polling places per address, which would send the visitor's address to Google, so it's left out.

## Proposed watcher (not built)
Weekly, Mondays after the representatives refresh:
1. List seats that went vacant since last week (from the representatives outputs).
2. Elections Canada: read the current year's by-elections page and match district numbers to Toronto's and
   Vancouver's federal ridings.
3. Elections BC: read the RSS feed and look for new event names in *Provincial Voting Places*.
4. City of Toronto: news RSS items mentioning "by-election".
5. US cities: Google Civic Elections endpoint (if a key is added), filtered to each city's state and county.
6. For anything new, open one GitHub issue per election (deduplicated by title) with a proposed `presets.elections`
   line for city.json. It doesn't edit the site, so a wrong match never reaches visitors.

Ontario stays manual: Elections Ontario can't be read by a job, but an MPP vacancy still raises the flag.

## Voting places, by election type
- Municipal / county (every city): already built; each fetcher needs its dates updated for the next election.
- BC provincial (Vancouver): buildable from Elections BC open data.
- Federal (Toronto, Vancouver): dates, advance days, local office and a "Where do I vote?" link to the riding's page.
  No station names.
- Ontario provincial (Toronto): dates and a link only, unless Elections Ontario publishes data a job can read.
