# Layers.City

**Live:** https://layers.city · **iPhone app:** [Layers.City on the App Store](https://apps.apple.com/ca/app/layers-city/id6825213728) · **By** Nouman Khan

A city is divided up a dozen ways at once: official neighbourhoods, council wards, provincial or state and federal electoral districts, school board wards, business districts, the informal names locals actually use, and the transit lines that tie it together. Each lives in a different dataset on a different website. Layers.City puts them on one interactive map you can switch on and off. Tap any spot, or search an address, and one card tells you every boundary it falls inside, who represents it, what it's like to live there, and what's nearby.

It's built for two people: a resident learning things they didn't know about their own city, and a newcomer getting their bearings.

![Layers.City Toronto: the whole city with former cities, highways and rapid transit](assets/screenshot.png)

## Cities

| City | Map | Notes |
|---|---|---|
| Toronto | [layers.city/toronto](https://layers.city/toronto/) | The reference city: every feature<br>is built here first |
| New York City | [layers.city/nyc](https://layers.city/nyc/) | 59 community districts in a<br>tri-state regional view |
| San Francisco | [layers.city/sf](https://layers.city/sf/) | 41 neighborhoods in a<br>nine-county Bay Area view |
| Chicago | [layers.city/chicago](https://layers.city/chicago/) | 77 community areas; added<br>county focus from local feedback |
| Vancouver | [layers.city/vancouver](https://layers.city/vancouver/) | Includes UBC and the University<br>Endowment Lands |
| Dallas | [layers.city/dallas](https://layers.city/dallas/) | Built first for the November 2026<br>election; ZIP codes as units |
| Melbourne | [layers.city/melbourne](https://layers.city/melbourne/) | The first city outside North America:<br>suburbs, built for Victoria's 2026 election |

An eighth, Hyderabad, is live but unlisted while its civic boundaries are unpublished.

## What it does

- **One card for any spot.** Every boundary it falls inside, its representatives at each level of government, housing and commuting figures from the census, the nearest transit, schools, libraries and parks, garbage day, nearby construction closures and, around an election, where to vote.
- **About 30 layers per city**, grouped by job: places, outdoors, getting around, what's changing, education, parking, representation, community, and lenses that shade neighbourhoods by housing cost, transit time to downtown or tree cover.
- **Live data.** Road closures from transit construction, special-event closures, new development, events, and next-bus times, each refreshed on its own schedule.
- **Pages beyond the map:** printable neighbourhood fact sheets, "Where does my bus go?", venues with how to get there, events, a city-vs-city Compare page, fun maps (Tim Hortons vs Starbucks, each neighbourhood's 311 signature), transit history timelines, and data explainers such as downtown Toronto's population hour by hour.

Every feature, layer and data source is described in **[FEATURES.md](FEATURES.md)**.

## Principles

Most of the work was deciding what the map should *not* do. These rules came first and shaped every feature after.

- **Describe, don't rank.** Demographic data never shades the map, filters a shortlist or feeds a ranking. There are no crime layers, school scores or "best neighbourhood" lists. Bus frequency is a description; a safety score would be a judgement.
- **Map facilities, never people.** The map shows places of worship, but never a "where X community lives" lens.
- **Current or not at all.** If data isn't current and accurate, the feature waits. Toronto school attendance areas and Hyderabad's ward map were both left out for this reason.
- **Honest about uncertainty.** Road closures show permit dates, labelled as not a reopening forecast. Census figures carry their year. Informal neighbourhood names are marked approximate.
- **Private by design.** No accounts, ads or tracking cookies. Location and address lookups run in the browser, and visit counts never include places, pins or searches.
- **Curated, not exhaustive.** Short, deliberate lists of landmarks and names. For street-level detail, Google Maps already exists.

## How it's built

- **One engine, a folder per city.** A shared map engine (`engine/`) knows how to draw kinds of layer. Everything specific to a city (layers, labels, colours, card rows, tour) lives in `cities/<city>/city.json`. Adding a city means adding data and config, not changing code.
- **No server and no database.** Static files on Cloudflare Pages, with a MapLibre GL front end (drawn on the GPU, so it stays smooth on phones) and no framework. The one exception is a small edge function that relays live bus arrivals.
- **Data pipeline.** Python (Shapely) and mapshaper clean, clip, join and simplify each source into small GeoJSON files.
- **Keeps itself current.** About 40 scheduled GitHub Actions jobs pull each source daily, weekly or monthly and redeploy only what changed. A daily health check opens a GitHub issue when a feed goes stale or a job fails, and closes it once the data recovers.
- **Shared with an iOS app.** The native app reads the same published files under a versioned data contract (`app-contract/`).

## Built with AI

I built this with Claude (Anthropic) as the engineering partner. I owned the product: the problem, which layers matter, how each city's informal geography should be described, and what the map should refuse to do. I reviewed every output against what I know of the city. Claude did most of the engineering: finding the datasets, writing the pipeline and front end, and testing at desktop and phone sizes.

Much of the work was data judgement rather than code. A few examples:

- **Stale official data.** The City of Toronto's riding layer still held pre-2018 boundaries, so current ridings come from Elections Canada and Elections Ontario instead. A third-party representatives feed was dropped after it listed an MP six months past her by-election; members are now read weekly from the legislatures themselves.
- **Building data that didn't exist yet.** In 2026 Ontario cut school boards to 12 trustees, which made the City's trustee-ward file obsolete. The Clerk's chart defines each new ward as a group of City wards, so the map builds them by merging wards instead of waiting for a new file.
- **Refusing a misleading answer.** The card counts schools nearby but never names a "nearest school", because in Toronto the board, not distance, decides which school a home is zoned for.
- **Staying neutral.** The election view lists every candidate in ballot order and singles none out. Picking frontrunners would be a political judgement.
- **User feedback.** Chicagoans place themselves by county first, so after a local's feedback the Chicago map gained a county focus picker.

## More

- [FEATURES.md](FEATURES.md): every feature, per-city detail, known limitations and full data sources
- [CHANGELOG.md](CHANGELOG.md): what changed and when
- [How it's built](https://layers.city/about/): the same story for site visitors
- `cities/<city>/SOURCES.md`: the exact queries used to fetch each city's raw data

## Licence

© 2026 Nouman Khan. All rights reserved. The code, page designs and written content aren't licensed for reuse; see `LICENSE` and the [Terms of use](https://layers.city/terms/). Versions published before October 14, 2026 were MIT-licensed, and copies of those keep that licence. The underlying open data keeps its own licences, listed in [FEATURES.md](FEATURES.md#data-sources-and-licences) and on the [Attributions](https://layers.city/attributions/) page. "Layers.City" and the pin logo are trademarks of Nouman Khan. To ask about permission: go@layers.city.
