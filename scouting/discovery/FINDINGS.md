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
| Makers & oddities | 195 | 14 | 0 | 181 | | | |
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
- **Makers & oddities:** the first run counted 508, of which 307 were `craft=*` trades (sign makers, caterers).
  That rule is gone (second run: 195, 181 independent). shop=art is mostly commercial galleries; instrument shops
  are the most characterful part.
- **Public art:** OSM has 84 murals; the City's StrollTO has ~267 and Public Art has 459 works. Use the City
  as the source and OSM only to fill gaps (dedupe by distance).
- **Viewpoints:** 59, only 8 named (Sheldon's Lookout, Chester Hill Lookout, Governor's Bridge Lookout, Sauriol Cliff…).
  A start for the Viewpoints kind, curated by hand.

## Matching to the City's described places (match.py, second run)
`out/matches.csv`: each OSM candidate whose name matches a StrollTO, Cultural Hotspot or Music Locations entry within
80 m, with the City's description and link (to quote with credit, OGL-Toronto). `relation` says what the City wrote about:

| Relation | Rows | Meaning |
|---|---|---|
| same | 43 | The business itself (34 of these are Music Locations rows: a name, no text) |
| inside | 9 | The place it sits in: Paradise Theatre (1937), Peanut Plaza, Music Garden, Fairview Mall… |
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
- Review chains with 2–3 Toronto shops (bubble tea and small local chains) and decide whether they count.

## Trial curation: Queen West, Trinity-Bellwoods, Kensington (November 17, 2026)
`pilot-queen-west-kensington.json`: 15 places, each checked against sources the file lists, with kind, lenses,
founding year, a one-line "why" in our own words and, for the City's places, a credited quote (OGL-Toronto).
- 12 are ready (or nearly): Graffiti Alley, Trinity Bellwoods Park, the Kensington Garden Car, Sonic Boom (2001),
  The Beguiling (1987), Rotate This (1991), Grasshopper Records (2012), Type Books (2006), Sanagan's (2009),
  Global Cheese (1970), Blackbird (2014), Black Market Vintage (1980).
- 3 are on hold: White Squirrel Coffee (no opening year yet), Sam James (about 5 locations, over the 3-location
  rule), Moonbean (no dated source).
- **OSM is stale for shops.** Of about 19 places checked, 3 had closed or moved while OSM still lists them:
  Dufflet's Queen West café (closed 2023), Craft Ontario Shop at 1106 Queen W (closed July 2026), and Black Market's
  256 Queen W basement (moved to 347 Queen W in 2019). BMV Queen West is unclear. A monthly refresh from OSM
  can't catch closures: curated businesses need their own status check (a per-entry "checked" date and a recheck
  every few months), separate from the OSM refresh.
