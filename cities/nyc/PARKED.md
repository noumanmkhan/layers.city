# New York City: what's not built yet

First slice (October 18, 2026): boundaries and units, NTAs, known-as names, landmarks, skyscrapers, historic districts,
BIDs, the subway, commuter rail and PATH, highways, main streets, the community district lens from the ACS, districts.
Next slices, in Toronto's order (sources in the project's nyc-data-scouting.md):

- Built October 18 (dev): the To Penn Station lens, r5py on the MTA GTFS (raw/transit_penn.json, run on Nouman's Mac: the cloud job ran out of memory, then disk, on a 7 GB private-repo runner; the last fix, freeing disk, is untested). Grand Central times are in the file for a hub choice later (engine: one hub per city today). The Staten Island Ferry's GTFS (nyc.gov) answered 403, so North Shore times (81 min) leave the ferry out: find another copy of that feed.
- Built October 18 (dev): the suburban drive lens, OSRM drive times to Penn Station (439 towns).
- Built October 18 (dev): representatives and where to vote. Still to do: a daily refresh of the poll site lists until November 3 and a weekly representatives refresh (both need NYC released to main: refresh jobs commit to main); the November 3 ballot races (candidates); hand positions for the three unplaced sites (Bronx HS for the Visual Arts, 2030 Antin Pl, early voting; Parkside Cornerstone, 2972 Bronx Park E; Vollies Memorial Hall, 43 Seba Ave) in raw/voting/places.json; council members' parties.
- Built October 18 (dev): buses, collectors, How addresses work (Manhattan only), bike lanes, Citi Bike, collection day, parks, sports & rec, libraries and older adult centers, schools, hospitals, colleges, places of worship, LPC individual landmarks, the Second Avenue Subway. Still to do: school zones on the map (raw/places/school_zones_*.geojson are fetched), church denominations (faith.py has them; the worship layer has no groups yet), NYC on the Attributions page (at release), NYCHA and DYCD community centres.
- What’s changing (DOB NOW, ZAP), closures and permitted events, place pages, fact sheets, badges.
- NYC extras: hurricane evacuation zones, the Congestion Relief Zone, ferries.
- Skyscrapers under construction without coordinates: 2 WTC, 37–47 West 57th, 740 Eighth Ave, 570 Fifth Ave, 343 Madison, 80 Flatbush, 70 Hudson Yards, 625 Madison, 24-19 Jackson Ave, One Montague Place.
