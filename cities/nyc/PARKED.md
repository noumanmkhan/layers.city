# New York City: what's not built yet

First slice (October 18, 2026): boundaries and units, NTAs, known-as names, landmarks, skyscrapers, historic districts,
BIDs, the subway, commuter rail and PATH, highways, main streets, the community district lens from the ACS, districts.
Next slices, in Toronto's order (sources in the project's nyc-data-scouting.md):

- To Midtown lens: r5py on the MTA GTFS set to Penn Station (raw/transit_penn.json; profiles.py reads it). Grand Central as a user choice later (engine: one hub per city today).
- Suburban lens: OSRM drive times to Penn Station (engine/drive.py).
- Built October 18 (dev): representatives and where to vote. Still to do: a daily refresh of the poll site lists until November 3 and a weekly representatives refresh (both need NYC released to main: refresh jobs commit to main); the November 3 ballot races (candidates); hand positions for the three unplaced sites (Bronx HS for the Visual Arts, 2030 Antin Pl, early voting; Parkside Cornerstone, 2972 Bronx Park E; Vollies Memorial Hall, 43 Seba Ave) in raw/voting/places.json; council members' parties.
- Buses (six MTA GTFS files), collectors, How addresses work (Fifth Avenue divide, per-borough text), bike lanes, Citi Bike.
- Collection day (DSNY Frequencies), parks and sports (DPR), libraries and community centres (FacDB), schools and zones, hospitals, colleges.
- What's changing (DOB NOW, ZAP), closures and permitted events, heritage buildings (LPC individual landmarks), canopy, place pages, fact sheets, badges.
- NYC extras: hurricane evacuation zones, the Congestion Relief Zone, ferries.
- Skyscrapers under construction without coordinates: 2 WTC, 37–47 West 57th, 740 Eighth Ave, 570 Fifth Ave, 343 Madison, 80 Flatbush, 70 Hudson Yards, 625 Madison, 24-19 Jackson Ave, One Montague Place.
