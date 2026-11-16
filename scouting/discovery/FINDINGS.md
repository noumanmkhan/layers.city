# Discovery points of interest: OpenStreetMap scout (November 17, 2026)

What OSM holds inside the City of Toronto (158 neighbourhoods) for the kinds in the project's discovery brief
(claude/discovery-pois-brief.md). Run by `scout.py` through scout.yml, from BBBike's Toronto extract.
Raw results: `out/report.json`; independent candidates per kind in `out/<kind>.csv`.
Data © OpenStreetMap contributors, ODbL: anything built from these files needs OSM credit, and a database derived
from them is share-alike.

**Branded** = brand / brand:wikidata tag. **Chain?** = no brand tag, but the same name appears 4+ times in the city.
**Indep.** = everything else (the candidates). **Start / Wiki / Web** = independents carrying start_date, wikidata, website.

| Kind | Total | Branded | Chain? | Indep. | Start | Wiki | Web |
|---|---|---|---|---|---|---|---|
| Murals | 84 | 0 | 0 | 84 | 38 | 1 | 3 |
| Sculptures | 244 | 0 | 0 | 244 | 43 | 23 | 5 |
| Monuments | 112 | 0 | 0 | 112 | 13 | 16 | 5 |
| Installations | 160 | 0 | 15 | 145 | 20 | 6 | 10 |
| Cafés | 1,659 | 719 | 102 | 838 | 0 | 1 | 249 |
| Bakeries | 413 | 21 | 17 | 375 | 1 | 2 | 97 |
| Restaurants | 3,661 | 274 | 104 | 3,283 | 10 | 29 | 1,024 |
| Markets | 76 | 0 | 0 | 76 | 0 | 2 | 8 |
| Books | 107 | 14 | 4 | 89 | 0 | 8 | 43 |
| Records | 33 | 2 | 0 | 31 | 0 | 0 | 12 |
| Vintage | 84 | 17 | 0 | 67 | 0 | 0 | 23 |
| Comics, games, toys | 85 | 11 | 0 | 74 | 0 | 1 | 23 |
| Specialty food | 300 | 27 | 8 | 265 | 0 | 0 | 70 |
| Makers & oddities | 508 | 20 | 0 | 488 | 6 | 1 | 196 |
| Viewpoints | 59 | 0 | 0 | 59 | 0 | 0 | 0 |

## What it means
- **OSM finds the candidates, but not the story.** Almost no independent business carries start_date or
  wikidata (cafés 0 and 1 of 838). The character test's "has a story" step must come from curation, not tags.
- **Cafés:** 838 independents, too many to show. Tim Hortons (365) and Starbucks (134) dominate the branded half.
  Small chains slip through: about 42 independent rows are bubble tea, and chains with 2–3 Toronto shops are
  under the 4-name threshold. Clusters: Kensington-Chinatown 48, Trinity-Bellwoods 39, Yonge-Bay 37, Annex 31,
  Roncesvalles 26.
- **Bakeries (375) and specialty food (265)** are a manageable size for hand curation by neighbourhood.
- **Restaurants (3,283 independents):** only usable as a lookup for curated "local institutions"; no tag selects them.
- **Records:** 31 independents, including the well-known shops (Sonic Boom, Rotate This, Kops, Grasshopper), but
  also karaoke shops, a radio station and music schools: hand-clean. The City's Music Locations list has 41 record stores.
- **Books (89), vintage (67), comics/games/toys (74):** small enough to review whole.
- **Makers & oddities is polluted:** 307 of 488 are `craft=*` with no shop tag (mechanical supply, sign makers,
  caterers). Drop that rule next run and keep shop=art/collector/frame/musical_instrument/craft. shop=art is
  mostly commercial galleries.
- **Public art:** OSM has 84 murals; the City's StrollTO has ~267 and Public Art has 459 works. Use the City
  as the source and OSM only to fill gaps (dedupe by distance).
- **Viewpoints:** 59, only 8 named (Sheldon's Lookout, Chester Hill Lookout, Governor's Bridge Lookout, Sauriol Cliff…).
  A start for the Viewpoints kind, curated by hand.

## Next
- Fix the makers rule; raise or lower the chain threshold after a look at the 2–3-shop chains.
- Join each candidate list to the City's lists (StrollTO, Cultural Hotspot, Music Locations) by name and distance:
  a business the City wrote about already has a story, with a description to quote with credit.
- Then curate by neighbourhood, starting where Along the way needs it.
