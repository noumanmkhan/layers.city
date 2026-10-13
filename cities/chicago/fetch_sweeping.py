"""Fetch Chicago's street sweeping zones and schedule for the card's Street sweeping row.

City of Chicago Data Portal (Streets and Sanitation): "Street Sweeping Zones - <year>" (polygons by
ward section) and "Street Sweeping Schedule - <year>" (ward section, month, dates such as "13,14").
A new year's pair is published each spring under new ids: the Socrata catalog is searched for the
newest year, with 2026's ids as the fallback. Writes raw/sweeping/zones.geojson, schedule.json and
meta.json. Runs in Actions (fetch-chicago.yml); the sandbox can't reach the portal.
"""
import json, os, re, time, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'sweeping'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (city-layers-pipeline; github.com/noumanmkhan/city-layers)'}
SOC = 'https://data.cityofchicago.org'
FALLBACK = {'year': 2026, 'zones': '2r7q-emq3', 'schedule': 'u5ai-3efk'}


def get(url, raw=False):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except Exception as e:
            print('  retry', i + 1, url[:140], e); time.sleep(6 * (i + 1))
    raise SystemExit('could not fetch ' + url)


# Newest year with both a zones table and a schedule table (not the "- Map" views).
pick = dict(FALLBACK)
try:
    cat = get('https://api.us.socrata.com/api/catalog/v1?' + urllib.parse.urlencode({'domains': 'data.cityofchicago.org', 'q': 'street sweeping', 'limit': 100}))
    found = {}
    for r in cat.get('results', []):
        n, i = r['resource']['name'], r['resource']['id']
        m = re.fullmatch(r'Street Sweeping (Zones|Schedule) - (\d{4})', n.strip())
        if m: found.setdefault(int(m.group(2)), {})[m.group(1).lower()] = i
    years = [y for y, v in found.items() if 'zones' in v and 'schedule' in v]
    if years:
        y = max(years); pick = {'year': y, 'zones': found[y]['zones'], 'schedule': found[y]['schedule']}
except SystemExit:
    print('catalog unreachable; using', FALLBACK)
print('using', pick)

zones = get(f"{SOC}/resource/{pick['zones']}.geojson?$limit=5000")
sched = get(f"{SOC}/resource/{pick['schedule']}.json?$limit=50000")
print('zones', len(zones['features']), 'schedule rows', len(sched))
print('zone fields', sorted(zones['features'][0]['properties'].keys()) if zones['features'] else None)
print('schedule sample', sched[:2])
if len(zones['features']) < 100 or len(sched) < 100: raise SystemExit('too little data; keeping the last copy')
json.dump(zones, open(os.path.join(OUT, 'zones.geojson'), 'w'), separators=(',', ':'))
json.dump(sched, open(os.path.join(OUT, 'schedule.json'), 'w'), separators=(',', ':'))
json.dump(dict(pick, fetched=datetime.now(timezone.utc).isoformat(timespec='minutes')), open(os.path.join(OUT, 'meta.json'), 'w'), indent=1)
