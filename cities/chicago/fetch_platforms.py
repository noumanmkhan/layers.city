"""The CTA's own words for each 'L' platform's direction ("O'Hare-bound", "Loop-bound", "Inner Loop"), from the
City of Chicago Data Portal's "CTA - System Information - List of 'L' Stops" (8pix-ypme), into
raw/platform_names.json: {"stops": {stop id: words}}. The CTA's GTFS names platforms without them ("Austin-Blue"),
so the Routes page reads them from here (routes.json "platformNames"). Run by *Fetch Chicago data* when this script
changes, or by hand; the list changes only when a station opens or is rebuilt.
"""
import json, os, re, urllib.request
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://data.cityofchicago.org/resource/8pix-ypme.json?$limit=5000'
rows = json.load(urllib.request.urlopen(urllib.request.Request(URL, headers={'User-Agent': 'layers.city data fetch'}), timeout=120))
out = {}
for r in rows:
    m = re.search(r'\(([^)]+)\)\s*$', r.get('stop_name') or '')
    if r.get('stop_id') and m:
        out[str(r['stop_id'])] = m.group(1).strip()
json.dump({'source': 'City of Chicago Data Portal, CTA List of L Stops (8pix-ypme)', 'fetched': date.today().isoformat(), 'stops': out},
          open(os.path.join(HERE, 'raw', 'platform_names.json'), 'w'), indent=0, ensure_ascii=False, sort_keys=True)
print(len(rows), 'platforms;', len(out), 'with direction words;', sorted(set(out.values()))[:60])
