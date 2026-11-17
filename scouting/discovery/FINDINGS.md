# Discovery points of interest: OpenStreetMap scout (November 17, 2026)

What OSM holds inside the City of Toronto (158 neighbourhoods) for the kinds in the project's discovery brief
(claude/discovery-pois-brief.md). Run by `scout.py` through scout.yml, from BBBike's Toronto extract.
Raw results: `out/report.json`; local candidates per kind in `out/<kind>.csv`.
Data © OpenStreetMap contributors, ODbL: anything built from these files needs OSM credit, and a database derived
from them is share-alike.

**Megachain** = a national or multinational chain on scout.py's MEGACHAINS list (matched on brand, brand:wikidata
or normalised name): the only places left out since the November 17 rules. **Local** = everything else, the
candidates in `out/<kind>.csv`, small local chains included. **Brand+** = local candidates that carry a brand tag;
**Name 4+** = local candidates whose name appears 4+ times in the city (the old "likely chain" test, now
information only; `name_count` in the CSVs). **Start / Wiki / Web** = local candidates carrying start_date,
wikidata, website. (Third run, November 17; the first two used brand tags and the 4+ test to split out chains.)

| Kind | Total | Megachain | Local | Brand+ | Name 4+ | Start | Wiki | Web |
|---|---|---|---|---|---|---|---|---|
| Murals | 84 | 0 | 84 | 0 | 0 | 38 | 1 | 3 |
| Sculptures | 244 | 0 | 244 | 0 | 0 | 43 | 23 | 5 |
| Monuments | 112 | 0 | 112 | 0 | 0 | 13 | 16 | 5 |
| Installations | 160 | 0 | 160 | 0 | 15 | 20 | 6 | 10 |
| Cafés | 1,659 | 706 | 953 | 27 | 99 | 1 | 1 | 300 |
| Bakeries | 413 | 18 | 395 | 4 | 19 | 1 | 2 | 102 |
| Restaurants | 3,661 | 152 | 3,509 | 126 | 182 | 10 | 31 | 1,099 |
| Markets | 76 | 0 | 76 | 0 | 0 | 0 | 2 | 8 |
| Books | 107 | 14 | 93 | 1 | 4 | 0 | 9 | 46 |
| Records | 33 | 2 | 31 | 0 | 0 | 0 | 0 | 12 |
| Vintage | 84 | 18 | 66 | 0 | 0 | 0 | 0 | 22 |
| Comics, games, toys | 85 | 12 | 73 | 0 | 0 | 0 | 1 | 23 |
| Specialty food | 300 | 32 | 268 | 0 | 4 | 0 | 0 | 72 |
| Makers & oddities | 195 | 14 | 181 | 0 | 0 | 2 | 0 | 55 |
| Viewpoints | 59 | 0 | 59 | 0 | 0 | 0 | 0 | 0 |

**Megachains vs the old split:** cafés 706 out (was 821 branded or "chain?"), bakeries 18 (was 38), restaurants 152
(was 378), books 14 (was 18). Back in as candidates: Jimmy's, Dark Horse, Balzac's, Pilot, Sam James, Caldense,
Danish Pastry House, Book City, Kinton Ramen, Hooked, Rowe Farms, the 11 Gardiner support-post installations, and
similar. `report.json` lists each kind's `top_megachains` and `top_local_repeats` (names seen twice or more, or
branded, among the candidates) for spotting a chain the list misses.

**Left in for the user's call** (national or multinational, but arguably places people make plans to go):
Ontario franchises Sunset Grill (14), Eggsmart (13), St. Louis Bar & Grill (12), Wild Wing (12), Mr. Greek (7),
Shoeless Joe's (7), Scaddabush, Chuck's Roadhouse, The Works; Quebec's Au Pain Doré, 3 Brasseurs, Café Dépôt;
destination multinationals Nobu, Haidilao, Gyu-Kaku, Hokkaido Ramen Santouka, AFURI, Ruth's Chris, Morton's, STK,
% Arabica, Café Landwer. Add any to MEGACHAINS to drop them.

## What it means
- **OSM finds the candidates, but not the story.** Almost no local business carries start_date or
  wikidata (cafés 1 and 1 of 953). Stories, where there are any, come from curation, not tags (and are optional).
- **Cafés:** 953 local candidates (838 under the old split), too many to show. Tim Hortons (365) and Starbucks
  (134) are most of the 706 megachain cafés. Clusters (second run): Kensington-Chinatown 48, Trinity-Bellwoods 39,
  Yonge-Bay 37, Annex 31, Roncesvalles 26.
- **Bakeries (375) and specialty food (265)** are a manageable size for hand curation by neighbourhood.
- **Restaurants (3,509 local):** only usable as a lookup for curated "local institutions"; no tag selects them.
- **Records:** 31 independents, including the well-known shops (Sonic Boom, Rotate This, Kops, Grasshopper), but
  also karaoke shops, a radio station and music schools: hand-clean. The City's Music Locations list has 41 record stores.
- **Books (93), vintage (66), comics/games/toys (73):** small enough to review whole.
- **Makers & oddities:** the first run counted 508, of which 307 were `craft=*` trades (sign makers, caterers).
  That rule is gone (second run: 195, 181 independent). shop=art is mostly commercial galleries; instrument shops
  are the most characterful part.
- **Public art:** OSM has 84 murals; the City's StrollTO has ~267 and Public Art has 459 works. Use the City
  as the source and OSM only to fill gaps (dedupe by distance).
- **Viewpoints:** 59, only 8 named (Sheldon's Lookout, Chester Hill Lookout, Governor's Bridge Lookout, Sauriol Cliff…).
  A start for the Viewpoints kind, curated by hand.

## Matching to the City's described places (match.py, third run)
`out/matches.csv`: each OSM candidate whose name matches a StrollTO, Cultural Hotspot or Music Locations entry within
80 m, with the City's description and link (to quote with credit, OGL-Toronto). `relation` says what the City wrote about:

| Relation | Rows | Meaning |
|---|---|---|
| same | 43 | The business itself (34 of these are Music Locations rows: a name, no text) |
| inside | 10 | The place it sits in: Paradise Theatre (1937), Peanut Plaza, Music Garden, Fairview Mall… |
| mural | 4 | A mural on or behind it (supercoffee's Polinator mural, St. Clair Gardens murals) |

- **The City has written a story for only about 8 businesses:** Rustic Bakery, Accordions Canada, the Old Mill,
  Miller Tavern, Lula Lounge, David Duncan House, plus Casa Loma and the Sheldon and Chester Hill lookouts. Only 3
  matches carry a founding year in the text.
- Record shops are well confirmed (16 of 31 are on the City's list too), but with no text.
- **So for businesses, "has a story" is hand research**, not a data join. "inside" and "mural" rows give lore
  for the setting, which a card can still use ("in the 1937 Paradise Theatre").
- `out/art_gaps.csv`: OSM artworks with no City art record within 40 m: murals 47 of 84, sculptures 146 of 244,
  monuments 69 of 112, installations 96 of 145. Gap-fill candidates; many sculptures are likely condo-lobby or
  private pieces to check.

## Next
- Curation by hand, by neighbourhood: research each candidate's story (founding year, signature thing, history)
  from citable sources, starting where Along the way needs it.
- Decide on the regional franchises and destination multinationals listed above.

## Trial curation: Queen West, Trinity-Bellwoods, Kensington (November 17, 2026)
`pilot-queen-west-kensington.json`: 15 places, each checked against sources the file lists, with kind, lenses,
founding year, a one-line "why" in our own words and, for the City's places, a credited quote (OGL-Toronto).
- All 15 are in under the November 17 rules (stories optional, only megachains out): Graffiti Alley, Trinity
  Bellwoods Park, the Kensington Garden Car, Sonic Boom (2001), The Beguiling (1987), Rotate This (1991),
  Grasshopper Records (2012), Type Books (2006), Sanagan's (2009), Global Cheese (1970), Blackbird (2014), Black
  Market Vintage (1980), and White Squirrel Coffee, Sam James (Ossington) and Moonbean, which were held back under
  the earlier rules (no founding year; Sam James for having about 5 shops).
- Each place has a `checked` date (2026-11-17). `stale.py` lists places not checked in 180 days and fails on any
  without a date. Readers can flag a problem through the place-report issue form (`reportUrl()` in
  `engine/report.js`, for when the places get a page).
- **OSM is stale for shops.** Of about 19 places checked, 3 had closed or moved while OSM still lists them:
  Dufflet's Queen West café (closed 2023), Craft Ontario Shop at 1106 Queen W (closed July 2026), and Black Market's
  256 Queen W basement (moved to 347 Queen W in 2019). BMV Queen West is unclear. A monthly refresh from OSM
  can't catch closures: curated businesses need their own status check (a per-entry "checked" date and a recheck
  every few months), separate from the OSM refresh.
