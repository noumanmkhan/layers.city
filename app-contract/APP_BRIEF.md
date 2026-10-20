# Layers.City for iPhone: what the app is (brief, restart of October 20, 2026)

The first iOS app (repo `city-layers-ios`, MapKit, a port of the web map's "What's here" card) never reached
TestFlight. It is being started over from this brief. `DATA_CONTRACT.md` still holds: it describes the data the
website publishes, and the new app reads the same files. This file says what the app does with them.

## In one sentence

**Know where you are and what's going on around you, without opening anything.**

The website is the deep tool: the map, the layers, Compare, Fact sheets, Venues. The app is the glance: widgets,
a few well-timed notifications, and a home screen of big numbers. Anything that needs a map to explain itself
links out to layers.city rather than being rebuilt in the app.

## Principles

1. **Glance first.** The lock screen widget is the product; the app is what you open when the widget makes you
   curious. Design every feature for the small rectangular lock screen widget (about three short lines) first.
2. **Big, bold, few words.** Numbers and short phrases ("3 closures nearby", "Green bin tomorrow",
   "Ward 11 · University–Rosedale"), never paragraphs. If a screen needs a sentence to explain itself, it belongs
   on the website.
3. **No parity with the website.** The app never tries to show every layer. A web feature joins the app only
   when it has a glanceable form.
4. **Nothing leaves the phone.** Location, saved places and the neighbourhood timeline stay on the device (iCloud
   private sync at most). No accounts, no server that knows who or where anyone is, no ad or tracking SDKs.
   Notifications are scheduled locally from published data wherever possible, so there is no push server to run.
5. **Explicit opt-in, plainly worded.** Background location, notifications and email are each optional, asked for
   at the moment the feature that needs them is turned on, with a one-line reason. Every feature still works
   (less automatically) when the answer is no.
6. **Every city, from `city.json`.** Features read what each city publishes and quietly hide where a city has no
   data for them (no garbage-day row in Vancouver, for example). No city names in the app's code.
7. **Apple Maps finds things; Layers.City explains places** (decided October 20, 2026). Bike share, EV
   chargers, washrooms, parking and other amenities are already in Apple Maps, preinstalled on every iPhone,
   with live availability and hours we can't match or keep current. The app never becomes a place to look
   them up. Where an amenity appears at all, it is a count that describes the neighbourhood ("6 bike share
   stations within 5 minutes"), and tapping it opens Apple Maps on that search near the spot. A map is drawn
   in the app only to show something Apple and Google don't: boundaries (neighbourhood, ward, school board,
   permit area), what's changing, event and transit construction closures with their permit dates, pickup
   areas.
8. **The app uses the data; the website hosts the pages** (decided October 20, 2026). Fact sheets, Venues,
   Compare and place pages stay on layers.city and are never rebuilt as app screens. The app opens them in an
   in-app Safari sheet, which keeps one copy to maintain and sends visits, links and search signals to the
   website. Their data still feeds the glance features: venue events are the "On" half of the weekend brief
   and the event-night alerts.
   - Tapping the neighbourhood name on "Around you" opens its fact sheet.
   - Tapping a collected stamp opens that neighbourhood's fact sheet.
   - Each event item has a "Getting there" link to its venue page.
9. **Planned, not live** (decided October 20, 2026). The app knows what's scheduled: permitted closures,
   event closures, planned subway shutdowns, pickup days. It does not report incidents as they happen
   ("Line 2 delayed, security incident, 5 minutes ago"); transit apps, the TTC's own alerts and Apple Maps do
   that, and doing it well needs a server polling feeds and sending pushes, which the app doesn't have. A
   possible later step, pull-only: the widget and app show the agency's current service alerts when they
   refresh, always with the time they were fetched, and never as a push.
10. **Trust over coverage.** A widget that says a road is closed when it isn't gets removed. Show the data's date,
   prefer fewer items, and drop an item rather than guess.

## What it should be

### 1. "Where am I" widget (lock screen and home screen)
- The spot's neighbourhood (or unit), ward and one live line, chosen by fixed priority: a closure within walking
  distance today, then pickup day tomorrow, then an event at a nearby venue tonight, then nothing.
- Refreshes when the phone moves (significant location change) **only if** the user turns on "Update in the
  background" (needs Always location). Otherwise it uses the location from the last time the app was open, and
  says "as of" when that's old.
- Taps open the app on that spot.

### 2. Neighbourhoods I've been to (on-device timeline)
- Checks off each neighbourhood the phone has spent time in (`CLVisit`, so a pass-through on the highway
  doesn't count). Progress per city: "47 of 158 Toronto neighbourhoods".
- Toronto and New York show each neighbourhood's badge drawing (`badges.json`) as a collected stamp; other cities
  show the unit's outline.
- Opt-in, needs Always location. Manual check-offs allowed for people who say no to background location.
- **Stored with CloudKit's private database, no accounts** (decided October 20, 2026). Stamps follow the user
  to a new phone or iPad through their own iCloud; the developer never sees them and runs no server. Build it
  this way from the first version, not as a later retrofit.
  - iCloud off or signed out: stamps stay on the device, with an Export / Import button that saves a small
    file to Files as a manual backup.
  - "Delete my history" wipes both the device copy and the iCloud copy.
  - No Sign in with Apple or any other sign-in. Revisit only for an Android version, sharing stamps with
    friends, or showing stamps on layers.city (CloudKit JS can do the last one with the user's Apple ID, still
    without a server of our own). Any third-party sign-in would require offering Sign in with Apple too, and
    any account requires in-app account deletion.
- Optional fun extras later: "new this month", a per-city map that fills in as you go, a share image that shows
  progress but never dates or routes.

### 3. The weekend brief (Fridays)
- "What's closed and what's on this weekend" for the user's city: subway and road closures first, then
  closures near big venues, then the biggest venue events. At most five closures and five events.
- Delivered as a widget state from Friday morning to Sunday night, a local notification on Friday morning
  ("Your Toronto weekend is ready"), and, opt-in, an email.
- Needs a new published file on the website side (below). Cities without the inputs don't offer it.

### 4. The app itself: "around you" in numbers
- One screen per city, big tiles with numbers and short phrases. Two kinds:
  - **Identity and what's going on** (the app's own answers): neighbourhood, ward and councillor, next pickup,
    closures nearby, what's changing, voting place in election season. These open a plain list or, only where
    a boundary or closure needs it, a small map.
  - **What the area has** (counts that describe it, from the card's Nearby data): parks and playgrounds,
    bike share stations, libraries, community centres, transit within a short walk. Tapping one opens Apple
    Maps searching for it near the spot. No in-app lists of amenities, no live availability.
- A "See it on layers.city" link for the full picture.
- Pick any spot (search, or a saved place) to see the same tiles there.

### 5. More, in rough order of value
- **Pickup reminders.** "Green bin and recycling tomorrow" the evening before, for a saved home spot. Toronto
  and Dallas from `collection.geojson`, New York where it publishes one, Chicago as **street sweeping: move
  your car** from `sweeping.geojson` (prevents tickets; likely the single most useful notification here).
  Scheduled locally from the published calendar; no server.
- **Saved places.** Home, work, a parent's place. Each gets the tiles, the pickup reminder and closure alerts.
  Kept on the device and synced the same way as the stamps (CloudKit private database).
- **Closures on your routes.** A notification when a new closure or special-event closure in `closures.geojson`
  or `events.geojson` touches a saved place's streets, checked when the app refreshes in the background. Big
  events (the marathon) get a heads-up two days before.
- **Event nights.** "Leafs at Scotiabank Arena tonight, 7 pm" when a saved place or the current spot is near a
  venue with an event (Venues data, Toronto and New York). Expect traffic, pick transit.
- **Changes near home.** A monthly line: "2 new development proposals within 500 m of home", linking to the
  web map's What's changing (`changes.geojson`).
- **Where to vote.** Around an election, a widget state and one notification with the voting place for the
  saved home spot (`voting.geojson`), and on election day only.
- **Arriving somewhere new.** With the timeline on, an optional one-time notification the first time the phone
  stops in a new neighbourhood: its name and one fact from its profile `facts`. Never repeated.
- **Siri and Shortcuts.** "What ward am I in?", "When's garbage day?", "What's closed this weekend?" as App
  Intents, so the answers work hands-free and in Spotlight.
- **Visitor mode.** For someone new to the city: how addresses work (Yonge east and west, Chicago's grid) as
  a single explainer tile, and the city's landmarks near you.

## What it shouldn't be

- **Not a map app.** No competing with Apple or Google Maps, no turn-by-turn, no attempt to draw every layer,
  no amenity lookups. A small map appears only to show something those maps don't (principle 7). The first
  attempt at this app was a map; that was the mistake this restart fixes.
- **Not a transit app.** No live arrivals, trip planning or live incident alerts; Transit, the TTC's own
  apps and Apple Maps do them well (principle 9).
- **Not a copy of the website.** Fact sheets, Venues and Compare are links out (principle 8).
- **Not an amenity directory.** Washrooms, Wi-Fi, water fountains and litter bins are what other city apps
  already do (Toronto: Transit & Amenities); Layers.City adds what they don't: identity (where am I, who
  represents me), what's changing, closures and the weekend, pickup days, and every city.
- **Not a demographic tool.** Language at home and other census fields never drive notifications, sorting,
  colours or tile choices (the data's rules, `DATA_CONTRACT.md` section 2). No ratings, crime or school scores.
- **Not an account.** No sign-in, no profile on a server, no social feed, no ads.
- **Not exhaustive.** Five items beat fifty in a widget or a brief.

## What the website needs to publish for this (later, website side)

- **`weekend.json` per city** (new): built each Thursday evening by a fetch job from `closures.geojson`,
  `events.geojson` and the venues feed, ranked by fixed rules (subway closures, then closures near venues,
  then the largest venue events), at most five closures and five events, each with a short line, dates, a
  point and a link. The same job writes a public `/<city>/weekend/` page and an RSS feed for the email.
  Added to `DATA_CONTRACT.md` when it exists.
- **Subway and rapid transit closures.** The most valuable weekend item and the least reliable input today;
  needs scouting per city before the brief launches.
- Everything else above already exists in the published data.

## Build order (first pass)

1. App shell: city picker from `city.json`, the "around you" tiles for the current spot and a searched spot.
2. "Where am I" widget, home screen then lock screen, using the last known location.
3. Saved home spot and pickup / street sweeping reminders.
4. Opt-in background location: the widget follows the phone; the neighbourhood timeline.
5. The weekend brief, once `weekend.json` is published (Toronto first).
6. Closure and event-night alerts, App Intents, then the rest.

Toronto first for every feature, then the other cities.

## Still open

- Name on the App Store: still "City Layers" from the first submission; the brand is Layers.City. Decide before
  the first TestFlight build. The existing App Store Connect record and bundle id can be reused.
- Whether the email for the weekend brief comes before or after the app version.
- How the app shows a city the user isn't in (browse mode) versus the city they're in.
- `docs/app/` on the website describes the first app; update it when the new one reaches TestFlight.
