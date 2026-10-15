# Vancouver: parked features

What Toronto has that the Vancouver map doesn't, and why. Checked October 16, 2026, while bringing Vancouver to parity.
Each entry says what would unpark it.

## Not built: no usable data

- **Collection day** (Toronto's garbage, green bin and recycling row). The City's two garbage-collection-zone datasets
  on its open data portal (single-family homes and duplexes; multi-unit buildings) have no records and no attached
  files, and were last touched in 2019. The City's own lookup runs on a third-party calendar app, not open data.
  Unpark if the City republishes collection zones with a schedule.
- **Halal and kosher shops** (the toggles under Mosques and Synagogues). Toronto's and Chicago's come from certifiers'
  published lists (HMA, COR; HMS, cRc). No BC certifier publishes the shops it certifies: Kosher Check (BC Kosher)
  offers a product search only, and no halal certifier with a public BC shop list was found. Unpark with a certifier
  list to curate from, as faith_shops.csv does elsewhere.
- **Road closures** (under Transit under construction). Toronto's are closure permits caused by transit construction.
  The Broadway Subway's street work is permitted by the Province, which publishes no closure feed, and the City's
  Road Ahead datasets (`road-ahead-current-road-closures`, 23 rows) list its own projects, carry no start dates and
  were last updated September 17. Unpark with a current, dated closure feed.
- **Development applications** (the Proposed stage of What's changing). Vancouver publishes issued building permits
  only; rezoning and development applications aren't open data. The layer shows permits, all at the Approved stage.
- **Skyscrapers under construction without an address.** Wikipedia lists ten towers under construction with no
  coordinates. 1099 Harwood is placed from its street address; 508 Drake and 1098 Harwood geocode only to the street,
  and the Oakridge and Senákw towers, 1515 by Bosa and Two Burrard Place have no address, so they stay off until
  placed. Add `coords` (or an address Nominatim can match) in skyscrapers.json to place them.

## Not built: doesn't fit Vancouver

- **City wards and school board wards.** Vancouver elects its council, park board and school board at large: there are
  no wards to draw. The card will list the whole council once the October 17 results are in.
- **Focus on a region.** Metro Vancouver has no counties or regional municipalities inside it (Toronto's Peel, York…;
  Chicago's counties), so there is nothing to focus on below the region.
- **Neighbourhood badges.** Hand-drawn art for Toronto's neighbourhoods; not data. Chicago and Dallas don't have them
  either.
- **Place pages and sitemap.** Vancouver is `unlisted` until launch; `engine/places.py vancouver` runs then.

## Partly there

- **Representatives.** MPs are on the card now. The mayor and the ten councillors (October 17) and MLAs (BC votes
  October 24) are wired after the results, from the City's and the Legislature's own pages; then the provincial
  layer gets party colours (`"party": {"table": "prov", "key": "name"}`).
- **Where to vote.** The October 17 voting places (the City's `voting-places-2026`) are on the card until the polls
  close. The October 24 provincial election isn't: Elections BC publishes no open voting-place data.
- **Hospitals.** Acute-care hospitals with a curated list (VGH, St. Paul's, Mount Saint Joseph, BC Children's and
  Women's, UBC Hospital). Holy Family and G.F. Strong (rehabilitation, no emergency) aren't placed: OpenStreetMap
  doesn't tag them as hospitals. The new St. Paul's (False Creek Flats) joins when it opens.
- **Secondary French immersion.** The VSB's three secondary immersion schools are on; its late immersion lives at
  Laura Secord only. CSF schools are placed by Nominatim from the CSF's own addresses.
- **Licences to re-check before any commercial use.** Mobi's GBFS feed (no licence stated with it; listed in
  MobilityData's public catalogue), as Divvy's is for Chicago; TransLink GTFS (see SOURCES.md).
