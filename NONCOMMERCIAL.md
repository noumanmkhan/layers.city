# Sources used under non-commercial terms

Layers.City earns nothing, so it uses some feeds their owners offer for non-commercial use only (the user's call,
November 7, 2026; see CLAUDE.md, Licence). Before the site, the iOS app or anything built on them makes money, each
of these must be licensed for that use or taken out. Each row says what to remove.

| Source | Terms | Used for | To take it out |
|---|---|---|---|
| Dallas Park and Recreation calendars (dallasparks.org CivicPlus iCal feeds) | City of Dallas disclaimer: commercial use prohibited without the City's written permission | Dallas Events page and the card's Happening nearby (`cities/dallas/fetch_happening.py`) | Ask the City for permission, or delete `cities/dallas/fetch_happening.py`, `events_page.json`, `card.nearby.happening` and `docs/dallas/events/` |
| Pace GTFS (pacebus.com/route-timetable-data-services; Mobility Database mdb-2347) | Offered "for non commercial use"; licence to use and redistribute "to assist you with mass transportation"; no Pace name or logo without consent | Chicago's Pace buses: map layer, Transit nearby, frequencies (`cities/chicago/surface.json` feed `pace`) | Put back `"osm": {"box": [41.1, -88.7, 42.55, -87.5], "network": "Pace"}` and `"names"` in place of `"gtfs"` (engine/osm_routes.py: routes and stops from OpenStreetMap, no timetable) |
| City of Vancouver calendar of events (Trumba feed `city-of-vancouver-events.json`) | vancouver.ca terms: feeds for personal, informational and non-commercial use; links must read "City of Vancouver" or "vancouver.ca" | Vancouver card's Happening nearby (`cities/vancouver/fetch_happening.py`) | Delete `cities/vancouver/fetch_happening.py`, `card.nearby.happening` and `docs/vancouver/data/happening.json` |
| What's On Melbourne (whatson.melbourne.vic.gov.au: its public MCP server's search, and each event's own page) | City of Melbourne disclaimer: content © the Council, "no part may be reproduced or reused for any commercial purposes"; nothing on automated access | Melbourne Events page and the card's Happening nearby (`cities/melbourne/fetch_happening.py`) | Ask the City for permission or an open feed, or delete `cities/melbourne/fetch_happening.py`, `events_page.json`, `card.nearby.happening`, `docs/melbourne/events/` and `docs/melbourne/data/happening.json` |
