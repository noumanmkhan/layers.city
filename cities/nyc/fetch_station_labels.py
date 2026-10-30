"""Fetch the MTA's direction labels for each subway platform into cities/nyc/raw/station_labels.json, for the Routes
page (engine/routes/build.py, routes.json "platformLabels"). Runs in GitHub Actions (fetch-nyc.yml).

The MTA Subway Stations dataset (data.ny.gov 39hk-dx4f) gives each station's GTFS stop id and the words the MTA's
signs use for its two directions: "Uptown & The Bronx" and "Downtown & Brooklyn", "Manhattan" and "Canarsie -
Rockaway Pkwy". The schedule's platforms are the stop id with N or S on the end (101N, 101S)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

rows = json.loads(get('https://data.ny.gov/resource/39hk-dx4f.json?$limit=5000', tries=3))
out = {}
for r in rows:
    sid = (r.get('gtfs_stop_id') or '').strip()
    if not sid: continue
    out[sid] = {'N': (r.get('north_direction_label') or '').strip(), 'S': (r.get('south_direction_label') or '').strip()}
if len(out) < 400: raise SystemExit(f'only {len(out)} stations: not saved')
json.dump({'source': 'MTA Subway Stations (data.ny.gov 39hk-dx4f)', 'fetched': time.strftime('%Y-%m-%d'), 'stations': out},
          open(os.path.join(RAW, 'station_labels.json'), 'w'), indent=0, ensure_ascii=False)
print(len(out), 'stations;', list(out.items())[:5])
