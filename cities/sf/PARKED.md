# San Francisco: next slices (October 30, 2026)

First build (unlisted at /sf/): parts of the city, 41 Analysis Neighborhoods (units) and SF Find's 117, known-as
names, landmarks, historic and cultural districts, BART, Muni Metro and cable cars, regional trains, freeways, main
streets, supervisor / Assembly / State Senate / congressional (AB 604) districts, the 9-county regional view, and
the neighborhood lens (ACS). Toronto parity, in Toronto's order:

1. Skyscrapers 150 m+ (engine/fetch_skyscrapers.py with a cities/sf/skyscrapers.json) and Article 10 landmark buildings (heritage_buildings).
2. Card: representatives (Board of Supervisors, Assembly, Senate, House), "How addresses work" (Market St / the Avenues), Nearby.
3. Buses: Muni bus routes by frequency (engine/fetch_surface.py), transit nearby, Bay Wheels stations, bike network (MTA ygmz-vaxd).
4. Parks (Rec & Park gtr9-ntp6 + facilities ib5c-xgwu), schools (7e7j-59qk) and SFUSD attendance areas, colleges, hospitals (HCAI), libraries (City Facilities nc68-ngbr).
5. Parking: SFMTA garages (vqzx-t7c4), RPP areas (dissolve i886-hxz9 by area letter), EV chargers (AFDC), street sweeping card row (yhqp-riqs).
6. What's changing: Development Pipeline (6jgi-cpb4), Temporary Street Closures and special events (8x25-yybr: geometry included).
7. Lenses: suburban drive lens, tree canopy; Fact sheets, Venues. (Transit lens done October 30: Montgomery St or 4th & King. Muni's "current" GTFS ran only to August 28, 2026, so the trips were timed on Tuesday, August 11: re-run fetch_transit.py when SFMTA publishes a newer feed.)
8. Live: beach water quality (v3fv-x3ux). SF extras: tsunami and seismic hazard zones, soft-story buildings, Slow Streets.
9. Voting card: SF assigns polling places but no open precinct→site list was found; the Bay Area's VCA counties vote anywhere in the county.
