# Hyderabad: scouting findings (October 8, 2026)

Verdict: **tabled.** The boundaries the map is mainly about (which municipal corporation, which
ward) aren't published anywhere in a usable form yet. Everything else is available.

Raw results: `out/report.json` and `out/scout.log`, from `scout.py` (run by hand with the
*Scout Hyderabad data* workflow). Boundaries found in OpenStreetMap are in `out/osm/`.

## Blocked: no current files
| Boundary | What exists | Problem |
|---|---|---|
| GHMC, Cyberabad and Malkajgiri corporations (Feb 2026) | Nothing | Not in OpenStreetMap or OpenCity. The corporations' sites (cmc.telangana.gov.in, ghmc.gov.in) didn't answer from GitHub's servers |
| 300 wards (Dec 2025) | Old 150 wards only | OSM's 149 ward relations were imported in October 2023 from OpenCity's 2022 file. OpenCity's "Wards Info" still holds the 2022 map |
| Secunderabad Cantonment | Nothing | No boundary relation in OSM |
| HMDA after the 2025 expansion (10,472 km²) | Old outline | OSM's HMDA relation is 7,649 km², last edited July 2025, so before the expansion |

Rebuilding the corporations from other layers doesn't work: they're made of the new zones, which
follow the new wards; the merged municipalities aren't in OSM (only mandals, which don't line up).

## Available and current
- **Assembly and Lok Sabha constituencies:** DataMeet (CC BY 4.0) has all 24 core-city assembly
  seats and the surrounding Lok Sabha seats, on the 2008 lines that are still in force. Its file
  still labels the state "Andhra Pradesh". OpenCity also has KMLs (2018 assembly, 2019 Lok Sabha).
- **Districts and mandals:** in OSM from the Telangana government's 2023 shapefiles (GODL),
  edited through 2026. Hyderabad district measures 183 km² in OSM against the usual 217; check before use.
- **PIN codes:** OpenCity's "Hyderabad and Secunderabad Pin Codes Map 2025" (KML, November 2025).
  data.gov.in's Department of Posts files refused GitHub's servers (403).
- **Place names:** 1,434 neighbourhood and 170 suburb nodes inside the ORR. 32 of 39 checklist
  names found; the misses (Charminar, Tarnaka, Kompally, Dilsukhnagar, Lakdikapul, Tellapur,
  "Hitech City") are spelling variants or curation work. HITEC City and Financial District exist
  as suburb points, with no outline.

## When to look again
Ward maps should become public before the corporation elections (reported for December 2026 or
December 2027). Re-run the workflow then, or when OpenCity updates "Hyderabad - Wards Info".

## Re-check, October 30, 2026: unchanged
- The workflow re-ran (out/ refreshed): OSM, OpenCity and the PIN code sources are as above. Still no
  corporation, new-ward, Cantonment or expanded-HMDA boundaries.
- Checked by hand from a browser in Hyderabad (the sites block GitHub's servers): cmc.telangana.gov.in and
  ghmc.gov.in load. Their zone, circle and ward maps are JPEG images only (CMCMap.jpeg, NEW ZONES,CIRCLE MAP.jpg,
  zone maps on Google Drive). GHMC also links the 300-ward delimitation notification of 25.12.2025 (a PDF that
  describes boundaries in words). Its elections portal has nothing for the corporation polls yet.
- Civic boundaries are still moving: a June 2026 plan would raise wards from 300 to 400 (GHMC 200, Cyberabad
  100, Malkajgiri 100); GHMC polls were being aimed at November–December 2026, with no notification yet.
- Revenue boundaries are frozen for the census: no district, sub-district (mandal) or village changes from
  January 1, 2026 to March 31, 2027. Ward boundaries aren't covered by the freeze.

## Built October 30, 2026: the revenue-track map (unlisted, /hyderabad/)
The user chose to build the revenue track now and add a revenue/civic picker once civic boundaries are published.
- Overpass timed out on every query that day; OpenStreetMap now comes from Geofabrik's southern India extract
  (`cities/hyderabad/fetch_osm.py`), which took three minutes.
- **Constituencies are not drawn.** Tested against 16 places whose seat is certain: DataMeet's assembly lines were
  wrong for 6 (Charminar and Mecca Masjid in Goshamahal, Jubilee Hills Road 36 in Sanathnagar, Khairatabad in Jubilee
  Hills), OpenCity's 2018 map for 3 (KPHB, Sanathnagar, Secunderabad station). Against GHMC's 2022 ward map (each old
  ward lies inside one seat), the 2018 map splits 59 of 155 wards between seats. Accurate lines would need the
  ward-to-constituency list for the old GHMC area (union of wards) and the 2008 Delimitation Order's mandal and village
  lists outside it. `cities/hyderabad/representatives.json` (MLAs, MPs) is ready for when that's done.
