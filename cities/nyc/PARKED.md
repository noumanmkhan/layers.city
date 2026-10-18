# New York City: what's not built yet

First slice (October 18, 2026): boundaries and units, NTAs, known-as names, landmarks, skyscrapers, historic districts,
BIDs, the subway, commuter rail and PATH, highways, main streets, the community district lens from the ACS, districts.
Next slices, in Toronto's order (sources in the project's nyc-data-scouting.md):

- Built October 18 (dev): the To Penn Station lens, r5py on the MTA GTFS (raw/transit_penn.json, run on Nouman's Mac: the cloud job ran out of memory, then disk, on a 7 GB private-repo runner; the last fix, freeing disk, is untested). Grand Central times are in the file for a hub choice later (engine: one hub per city today). The Staten Island Ferry's GTFS (nyc.gov) answered 403, so the first run left the ferry out; NYC Open Data's copy (b57i-ri22) worked on the October 19 rerun: next to the St. George terminal, 73 minutes became 64, and the North Shore's district median 81 became 79 (most of the district is a bus ride from the ferry).
- Built October 18 (dev): the suburban drive lens, OSRM drive times to Penn Station (439 towns).
- Built October 18 (dev): representatives and where to vote. Released October 18, with a daily poll-site refresh until November 3 (fetch-nyc-voting.yml) and a weekly representatives refresh (fetch-nyc-representatives.yml). October 19: the three unplaced sites got hand positions (raw/voting/places.json), council members' parties (hand-kept, cities/nyc/council_members.json: check after each council election or vacancy), and the November 3 ballot rows (ballot.py, refreshed daily with the poll sites). No results after election day: the rows go away; judicial races aren't shown.
- Built October 18 (dev): buses, collectors, How addresses work (Manhattan only), bike lanes, Citi Bike, collection day, parks, sports & rec, libraries and older adult centers, schools, hospitals, colleges, places of worship, LPC individual landmarks, the Second Avenue Subway. School zones (the card's Schools section) and church denominations followed the same day. Still to do: NYC on the Attributions page (when it's listed), NYCHA and DYCD community centres, school zones drawn as a map layer.
- What’s changing (DOB NOW, ZAP), closures and permitted events, place pages, fact sheets, badges.
- NYC extras: hurricane evacuation zones, the Congestion Relief Zone, ferries.
- Skyscrapers under construction without coordinates: 2 WTC, 37–47 West 57th, 740 Eighth Ave, 570 Fifth Ave, 343 Madison, 80 Flatbush, 70 Hudson Yards, 625 Madison, 24-19 Jackson Ave, One Montague Place.
