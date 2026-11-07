"""Scout Chicago's open event sources for the Events page, "Happening nearby" and the Special events layer
(the Toronto features, ported). Writes raw/scouting/events.json: for each dataset its columns, row count in the
next 30 days, the most common values of its category fields, and a sample of rows. Run in GitHub Actions
(*Scout Chicago data*); the sandbox can't reach the portal.

Datasets: Chicago Public Library Events (vsdy-d8k7), Chicago Park District Activities (tn7v-6rnw), Public Health
Department Events (38sz-xyf4), Special Events (xgse-8eg7), and CDOT Transportation Department Permits (pubx-yq2d)
with an event work type (Festival, Athletic, Parade, Block Party), grouped by application.
"""
import collections, json, os, urllib.parse, urllib.request
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'scouting')
os.makedirs(OUT, exist_ok=True)
BASE = 'https://data.cityofchicago.org/resource/'
now = datetime.now(ZoneInfo('America/Chicago'))
d0, d30 = now.strftime('%Y-%m-%dT00:00:00'), (now + timedelta(days=30)).strftime('%Y-%m-%dT00:00:00')


def get(rid, **q):
    url = BASE + rid + '.json?' + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={'User-Agent': 'layers.city data scout'})
    try:
        return json.load(urllib.request.urlopen(req, timeout=180))
    except Exception as e:
        print(rid, 'failed:', e)
        return None


def meta(rid):
    req = urllib.request.Request(f'https://data.cityofchicago.org/api/views/{rid}.json', headers={'User-Agent': 'layers.city data scout'})
    try:
        m = json.load(urllib.request.urlopen(req, timeout=60))
        return {'name': m.get('name'), 'description': (m.get('description') or '')[:1500], 'license': (m.get('license') or {}).get('name'),
                'attribution': m.get('attribution'), 'rowsUpdatedAt': m.get('rowsUpdatedAt'),
                'columns': [[c['fieldName'], c.get('dataTypeName'), (c.get('description') or '')[:200]] for c in m.get('columns', [])]}
    except Exception as e:
        return {'error': str(e)}


def profile(rid, rows, cats):
    out = {'meta': meta(rid), 'n': len(rows or [])}
    if rows:
        out['fields'] = sorted({k for r in rows for k in r})
        out['common'] = {c: collections.Counter(str(r.get(c)) for r in rows).most_common(25) for c in cats}
        out['sample'] = rows[:25] + rows[len(rows) // 2:len(rows) // 2 + 10]
    print(rid, out['n'], 'rows')
    return out


res = {'asof': now.isoformat()}

# Discover the date column of each dataset first: take one row and look.
for rid, key in [('vsdy-d8k7', 'library'), ('tn7v-6rnw', 'parks'), ('38sz-xyf4', 'health'), ('xgse-8eg7', 'special')]:
    one = get(rid, **{'$limit': 3}) or []
    res[key + '_head'] = one
    datecols = [k for k in (one[0] if one else {}) if any(w in k.lower() for w in ('date', 'start', 'time'))]
    rows = None
    for dc in datecols:
        rows = get(rid, **{'$where': f"{dc} >= '{d0}' AND {dc} < '{d30}'", '$limit': 50000, '$order': dc})
        if rows is not None:
            res[key + '_datecol'] = dc
            break
    if rows is None:
        rows = get(rid, **{'$limit': 5000}) or []
    cats = [k for k in (rows[0] if rows else {}) if any(w in k.lower() for w in ('type', 'categ', 'audience', 'age', 'location', 'branch', 'park', 'program', 'fee', 'cost', 'free', 'status'))]
    res[key] = profile(rid, rows, cats)

# CDOT event permits with a street closure, next 30 days, grouped by application.
rows = get('pubx-yq2d', **{'$where': "worktypedescription in ('Festival', 'Athletic', 'Parade', 'Block Party', 'Street Closure', 'Assembly') "
                                     f"AND applicationenddate >= '{d0}' AND applicationstartdate < '{d30}'", '$limit': 50000}) or []
groups = collections.defaultdict(list)
for r in rows:
    groups[(r.get('worktypedescription'), r.get('applicationname'))].append(r)
res['permits'] = {
    'n': len(rows),
    'fields': sorted({k for r in rows for k in r}),
    'closure': collections.Counter(r.get('streetclosure') for r in rows).most_common(),
    'worktype': collections.Counter(r.get('worktypedescription') for r in rows).most_common(),
    'status': collections.Counter(r.get('applicationstatus') for r in rows).most_common(),
    'groups': sorted(([wt, name, len(g), min(x.get('applicationstartdate', '') for x in g), max(x.get('applicationenddate', '') for x in g),
                       collections.Counter(x.get('streetclosure') for x in g).most_common(),
                       sorted({' '.join(filter(None, [x.get('streetnumberfrom'), '-', x.get('streetnumberto'), x.get('direction'), x.get('streetname'), x.get('suffix')])) for x in g})[:8],
                       {k: g[0].get(k) for k in g[0] if k not in ('streetnumberfrom', 'streetnumberto', 'direction', 'streetname', 'suffix', 'location')}]
                      for (wt, name), g in groups.items()), key=lambda x: x[3]),
}
print('permits', len(rows), 'rows,', len(groups), 'applications')

json.dump(res, open(os.path.join(OUT, 'events.json'), 'w'), indent=1, default=str)
