# City Layers: notes for Claude sessions

This repo is the **map** (live at https://layers.city/toronto/) and the small
maps hub page at https://layers.city/. The landing page for
noumankhan.ca is a separate repo and a separate project. If you were opened to work on
the landing page, stop and say so; don't change this repo.

## Branches: work on `main`; `dev` only for experiments
- Since October 19 the user works directly on `main` (his decision): commit and push finished, tested work to
  main. `main` is the live site: every push to it that touches docs/ deploys to layers.city, so test in a browser
  (desktop and phone, light and dark, every city an engine change touches) before each push, as always.
- Keep `dev` for truly experimental features only, and only when the user says a feature is experimental (or asks
  for it on dev). Pushes to dev run no workflows and deploy nothing. To release such a feature: on dev, merge
  origin/main, rebuild and test, then `git checkout main && git merge --ff-only dev` (or a normal merge if main
  has moved) and push main.
- The fetch jobs keep committing data to main every day: `git pull --rebase origin main` before starting and
  again right before pushing. If a built file (docs/<city>/data/*) conflicts, take main's copy and rebuild that
  city rather than hand-merging it.
- An unlisted city (`"unlisted": true` in its city.json) is live at its URL but kept off the hub
  page and sitemap, so it can be built on main.
- **Fact sheets** (printable neighbourhood profiles: `engine/profiles/`, `docs/<city>/profiles/`, at
  /toronto/profiles/ and /nyc/profiles/) launched October 18 (New York October 19). Each city's settings and wording
  are in `cities/<city>/factsheet.json` (and badge colours in `factsheet.css`); keep the engine free of city names.
  The sheets are linked from the hub card and each Guide page (places.py writes those
  links and the sitemap entry). `.github/workflows/refresh-fact-sheets.yml` rebuilds them after the routes, parking
  and bike-lane fetch jobs and monthly re-fetches the walk network, walk times, ramps and drive times; deploy.yml
  lists it, so its commits go live. By hand: `python3 engine/profiles/build.py <city>` after the map's data changes.
- **Venues** (`cities/<city>/venues.json`, `engine/venues.py`, pages at `docs/<city>/venues/`; Toronto October 18, New York
  October 19): each city's big live venues, what's on at each this fortnight from Ticketmaster's Discovery API
  (`engine/fetch_venue_events.py <city>`, secret `TICKETMASTER_KEY`) and how to get to each from across the region
  (`engine/fetch_venue_drives.py <city>`, OSRM). Each city's words, files and fares are in its venues.json "page",
  "feed" and "fares"; the engine names no city. `.github/workflows/refresh-venues.yml` fetches nightly and rebuilds the pages;
  deploy.yml lists it. Facts only: no images, prices, copy or affiliate links (the API terms forbid deriving
  revenue from it). The venue list and the fare figures in venues.json are hand-kept; `engine/places.py` adds the
  pages to the sitemap. By hand: `python3 engine/venues.py <city>`. Notes in the project's claude/venues.md.
- To let the user try an experiment on dev on a phone: run the "Deploy to Cloudflare Pages" workflow by
  hand with branch `dev`; it publishes a preview at https://dev.layers-city.pages.dev. The branch is the
  workflow's `branch` input, not the ref it runs from: `gh workflow run deploy.yml --ref dev -f branch=dev`.
  Without `-f branch=dev` it publishes main to the live site.

## Before changing anything
- Other sessions may have pushed since you last looked. Run `git fetch origin main dev` and
  rebase or merge onto the latest first, and fetch again right before pushing.
- If a push is rejected, rebase onto the new commits and keep both sets of changes.
  Never force-push.
- Before editing a file, read its current version from the repo, not from memory or an
  earlier copy.

## How the site is built
- `docs/` is the published site, served by Cloudflare Pages (project `layers-city`, custom domain layers.city;
  www.layers.city and maps.noumankhan.ca redirect to it). `.github/workflows/deploy.yml` uploads it with Wrangler on
  pushes to main that touch docs/, and after each fetch job that commits to docs/ (listed in its `workflow_run`):
  a new fetch job that writes to docs/ must be added to that list, or its data won't go live until the next push.
  - `docs/index.html`, `docs/fonts/` and the icons are the **maps hub**, hand-written and
    laid out like the noumankhan.ca landing page, in the Layers.City brand (red #C8102E, pin logo).
    The plain pin is the default everywhere; the maple-leaf version (the `-ca` logo, touch icon and
    social image) is only for Canadian cities' pages, picked from `search.country` by assemble.py and places.py.
    Edit them directly, except the logo files and `docs/thumbs/`, which `assets/brand/build.py` and
    `assets/brand/outlines.py` draw: change those scripts and re-run. Print maps get
    added there as cards (a template is commented out in the HTML), with images in `docs/prints/`.
  - `docs/about/` (the "How it's built" write-up for readers such as employers), `docs/privacy/`,
    `docs/attributions/` and `docs/terms/` are hand-written pages; edit them directly. Keep about/ in step
    with the README when the architecture or principles change. The repo is private: link nothing to GitHub.
  - `docs/<city>/` is each city's map (Toronto's is `docs/toronto/`). Don't hand-edit
    `docs/<city>/index.html` or `docs/<city>/data/*`; they are build output.
    The place pages (`docs/<city>/<place>/`, the index page, `docs/sitemap.xml`, `docs/robots.txt`)
    are build output too, from `engine/places.py`.
- The map is one engine with a folder per city:
  - `engine/template.html` (page and styles) and `engine/map.js` (behaviour) are shared by every
    city. Keep them free of city names, places and data sources.
  - `cities/<city>/city.json` holds everything city-specific on the page: text, layer list and
    files, lenses, "What's here" rows, representatives, search area. `city.css` holds the city's
    own colours (fill layers, transit lines, their swatches).
  - `cities/<city>/` also holds that city's fetch and build scripts, `raw/` inputs, `run.sh` and
    `SOURCES.md`.
- Rebuild a city with `cities/<city>/run.sh` (needs Python with shapely, and Node; it runs
  `npm install` at the repo root for mapshaper and Leaflet). After a page-only or config-only
  change, `python3 engine/assemble.py <city>` is enough.
- An engine change affects every city: rebuild and check each one.
- The City of Toronto GIS server (gis.toronto.ca) can't be reached from most sandboxes.
  `.github/workflows/fetch-streets.yml` shows the pattern: fetch it in GitHub Actions and
  commit the raw file. It also rejects bursts of parallel requests, so fetch one layer at a time.

## Apps that read this data
- An iOS app (separate repo, built in Cursor) reads the published `docs/<city>/data/` files and
  `docs/<city>/data/city.json` (written by `engine/assemble.py`). `app-contract/DATA_CONTRACT.md`
  describes them.
- When a change alters a published file, field or card row, update the contract in the same
  commit. Adding things is fine. Renaming, removing or changing the meaning or units of a field or
  file is a breaking change: bump `"schema"` in every `cities/*/city.json` and add a migration
  note at the top of the contract.

## Licence
- The repo is all rights reserved (see `LICENSE`, and `docs/terms/` for visitors); it was MIT before
  October 14, 2026. Don't add licence headers or files that grant reuse rights. Third-party data keeps its own
  licences, so keep the Attributions page and map credit lines complete.

## Conventions
- One change per commit, with a plain-English message saying what changed and why.
- Test in a browser at desktop and phone widths, and in light and dark themes, before pushing.
- Keep the map uncluttered. Landmarks and known-as names are deliberately short, curated
  lists, not exhaustive databases.
- Address search uses OpenStreetMap Nominatim, whose usage policy forbids
  autocomplete-as-you-type. Live suggestions come only from the local landmark list.
- Keep `README.md` current when features change. It doubles as the portfolio write-up.

## Project log in Notion
The user keeps a history and roadmap of this project in a Notion database, "Layers.City Project"
(https://app.notion.com/p/3fc17fd4917e80f088c4f4368c2868f8, data source
`collection://3fc17fd4-917e-80d6-a41a-000b73bcf9bb`). Keep it current as part of finishing work:
- Add a row when something reaches dev or main, is reverted, or is parked, and when the user parks or
  floats an idea in conversation. One row per change the user would recognise (the level of a CHANGELOG
  heading), not per commit; data refreshes by the fetch jobs never get a row.
- When a row moves on (On dev → Shipped, Idea → On dev), update its Status rather than adding a duplicate.
- Fields: **Name** (what changed, in plain words), **Step** (one more than the current highest), **Date**
  (the day it landed; leave empty for ideas), **Thread** (an existing option where one fits; Notion
  select options can't contain commas), **Type** (New feature, Iteration, Fix, Reversal, Scouting,
  Milestone, Infrastructure or Idea), **Cities**, **Status** (Shipped, On dev, Parked, Reverted or
  Idea), **Evolved from step** (the Step this iterates on, if any) and **Notes** (why, in a sentence).
- Read the database first for the highest Step and the Thread options. If the session has no Notion
  connector, say so at the end of the work and list the rows that should be added.
