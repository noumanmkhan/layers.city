# Dallas: parked ideas

What Toronto (or Chicago) has that the Dallas map doesn't, and why. Checked October 16, 2026. Each entry says what
would unpark it.

## Elections

- **November 3 ballot rows outside Dallas County.** About 4% of the city (in Collin, Denton, Kaufman and Rockwall
  counties) votes in districts the Dallas County sample ballot doesn't list: TX-3, TX-4 and TX-26, and Texas House
  4, 33, 65, 70 and 89. The card shows no race there. Unpark by adding those counties' sample ballots to
  `fetch_ballot.py` and `ballot.py` (the Texas Secretary of State's candidate search is a web app with no download).
- **Election view for the City Council (May 1, 2027).** Toronto's ward election view (one neutral colour, race
  labels, candidates under the member) fits Dallas's 14 nonpartisan districts. Unpark once the City Secretary
  certifies the ballot (filing closes mid-February 2027): a candidate fetch plus `election` on the council layer and
  `race` on the council office.

## Not built: no usable data

- **Address grid** (Toronto's Address row, Chicago's grid). Dallas's house numbers don't count out from one zero
  point across the city the way Chicago's do, so a "you're about 2400 N · 1200 W" row would mislead. No dataset of numbering zones was found.
- **What's changing** (building permits and development applications within half a mile). The City's open
  building-permit dataset (Dallas Open Data) stops in 2020, and the ArcGIS permit layers (NewPermit, FY23-24) stop in
  2024. A narrower candidate exists: the City's Zoning Cases layers (current-year zoning cases), which would show
  rezonings but not ordinary permits. Unpark with a current permit feed, or build a zoning-cases-only version.
- **Heritage buildings** (one point per individually designated building). The City publishes its landmark
  *districts* (on the map) but no dataset of individually designated Dallas Landmarks with locations. Its
  historical markers list (Dallas Open Data adn6-n59j, 183 rows) is a survey of marker plaques and their condition,
  not designations, so it isn't used. Unpark if the Office of Historic Preservation publishes its landmark list
  with addresses (it could then be geocoded).
- **Schools section** (the school whose attendance zone holds the spot). Dallas ISD's attendance boundaries are
  only in its school locator; no open polygons were found, and the city is split among a dozen-plus ISDs that each
  draw their own. The card names the ISD and the Dallas ISD trustee district instead.
- **Street closures** and **transit construction**. No rail line is being built in the city (DART dropped the D2 downtown
  subway from its long-term plans in 2023, and the Silver Line is running), and the City publishes no open street-closure permit feed.
- **Bike share** (stations and docks). Dallas has no docked system; dockless operators publish no station list.
- **Streetcars**. The Dallas Streetcar and the McKinney Avenue M-Line trolley aren't in DART's GTFS (its rail
  routes are the four light rail lines, the Silver Line and the TRE), so they can't be drawn or timed.
- **School trustee names**. Dallas ISD's trustee districts are drawn, but the district's GIS data carries no
  trustee names. A hand-kept list would go stale after each May election; unpark with a source to check it against.

## Not built: doesn't fit Dallas

- **Getting to work lens.** 43 of 46 ZIP codes have 80% or more of commuters driving, so the lens would paint
  the city one colour. The shares still show on the card under Living here.
- **Neighbourhood badges.** Hand-drawn art for Toronto's neighbourhoods; Dallas has no official neighbourhoods
  (its units are ZIP codes).
- **Faith & Community and French schools.** Curated Toronto lists; Chicago doesn't have them either. Could be
  built from OpenStreetMap, but they need the same curation rules first.
- **Place pages and sitemap.** Dallas is `unlisted` until launch; `engine/places.py dallas` runs then.

## Partly there

- **Party colours on congressional districts.** The map draws the 2025 lines, but the members sitting now were
  elected on the 2021 lines, so colouring the new districts by them would be wrong. Unpark in January 2027, once the
  November 3 winners take office and `card.reps` reads `congress` from the drawn layer: add `"party": {"table":
  "congress", "key": "num"}` to the `congress` layer.

- **Frequent buses.** The bus layer's Frequent family is empty: no DART route runs six trips an hour each way
  through the whole weekday (the rule every city uses). Express routes are marked.
- **Trails in the bike layer.** The City's bike facilities include only five trail segments; the Park Department's
  trails (the Katy Trail, White Rock Lake, the Trinity trails) are in a separate layer (`raw/city/trails.geojson`,
  fetched). Unpark by adding them as the `trail` class, with a monthly fetch.
- **Collection day dates.** Worked out from the weekday; the City publishes no holiday changes as data, so the
  card says holidays can move a day.
- **Skyscrapers under construction.** None at 150 m or more is listed on Wikipedia now; the layer will show them
  when one is.
- **Indoor pools.** The City's Indoor_Pool_2023 layer is empty; Nearby uses the community pools.
- **Where to vote in Rockwall, Ellis, Johnson, Kaufman and Parker counties.** Not fetched yet; the box shows only in
  Dallas, Tarrant, Collin and Denton counties.
- **Transit to downtown.** ZIPs where fewer than half the grid points reach downtown within three hours show as
  "over an hour" with no minutes.
