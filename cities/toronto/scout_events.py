"""Scout special-event road closures (e.g. the Waterfront Marathon) in the City of Toronto's live
Road Restrictions feed, for a "Special events" layer. One-off: writes every record flagged as a
special event (any field named like "specialEvent" saying yes/true), with its full geometry, to
raw/scouting/events.json, plus a survey of the feed's field names and of the event records' values.
The sandbox can't reach secure.toronto.ca; Actions (scout-toronto.yml) can.
"""
import json, os, re, urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
URL = 'https://secure.toronto.ca/opendata/cart/road_restrictions/v3?format=json'
OUT = os.path.join(HERE, 'raw', 'scouting')
os.makedirs(OUT, exist_ok=True)

req = urllib.request.Request(URL, headers={'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'})
raw = urllib.request.urlopen(req, timeout=180).read().decode('utf-8', 'replace')
raw = re.sub(r'\\(["\\/bfnrtu]?)', lambda m: m.group(0) if m.group(1) else '\\\\', raw)
data = json.loads(raw, strict=False)
recs = [r for v in data.values() if isinstance(v, list) for r in v]
keys = Counter(k for r in recs for k in r)
print('records', len(recs))
print('fields', sorted(keys))
skeys = [k for k in keys if 'special' in k.lower() or 'event' in k.lower()]
for k in skeys:
    print(k, Counter(str(r.get(k)) for r in recs).most_common(12))


def yes(v):
    return str(v).strip().lower() in ('yes', 'y', 'true', '1')


ev = [r for r in recs if any(yes(r.get(k)) for k in keys if 'special' in k.lower())]
print('special-event records', len(ev))
for k in ('name', 'type', 'subType', 'source', 'workEventType', 'permitType', 'contractor', 'roadClass',
          'eventName', 'specialEventName', 'organization'):
    if k in keys:
        print(k, Counter(str(r.get(k)) for r in ev).most_common(15))
txt = Counter()
for r in ev:
    for w in re.findall(r'[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*', r.get('description') or ''):
        txt[w] += 1
print('description words', txt.most_common(30))
json.dump({'fields': sorted(keys), 'records': ev}, open(os.path.join(OUT, 'events.json'), 'w'), indent=0)
