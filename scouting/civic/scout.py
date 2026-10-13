"""Scouting (October 14, 2026) for v1.2's civic rows: garbage day, drop-in programs, beach water
quality and snow clearing, in Toronto and Chicago. Read-only: lists what each open dataset holds,
how current it is and whether it can be tied to a spot on the map. Writes scouting/civic/out/
(one JSON per question plus summary.json); nothing here feeds the map.

Run in Actions (scout-civic.yml): the sandbox can't reach the City of Toronto's CKAN downloads, its
GIS server or the Chicago Data Portal.
"""
import csv, io, json, os, re, struct, time, urllib.parse, urllib.request, zipfile
from collections import Counter
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out'); os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (city-layers-pipeline; github.com/noumanmkhan/city-layers)'}
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca'
GIS = 'https://gis.toronto.ca/arcgis/rest/services'
SOC = 'https://data.cityofchicago.org'
TODAY = date.today()
summary = {}


def fetch(url, raw=False, tries=3, timeout=120):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b)
        except Exception as e:
            print('  retry', i + 1, url[:150], e); time.sleep(4 * (i + 1))
    return None


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w'), indent=1, ensure_ascii=False, default=str)


def step(name, fn):
    print('\n==', name)
    try:
        summary[name] = fn()
    except Exception as e:
        print('  FAILED', repr(e)); summary[name] = {'error': repr(e)}
    save('summary.json', summary)


def dbf(b):
    """Minimal DBF reader (shapefile attributes): field names and rows as dicts."""
    n, hl = struct.unpack('<IH', b[4:10]); rl = struct.unpack('<H', b[10:12])[0]
    fields, p = [], 32
    while b[p] != 0x0D:
        fields.append((b[p:p + 11].split(b'\0')[0].decode('latin-1'), b[p + 16])); p += 32
    rows = []
    for i in range(n):
        r = b[hl + i * rl: hl + (i + 1) * rl]
        if r[:1] == b'*': continue
        o, d = 1, {}
        for name, ln in fields:
            d[name] = r[o:o + ln].decode('latin-1').strip(); o += ln
        rows.append(d)
    return [f[0] for f in fields], rows


def shape_attrs(url):
    z = zipfile.ZipFile(io.BytesIO(fetch(url, raw=True)))
    names = z.namelist()
    out = {'files': names}
    for n in names:
        if n.lower().endswith('.dbf'):
            fields, rows = dbf(z.read(n))
            out[n] = {'fields': fields, 'rows': len(rows), 'sample': rows[:5],
                      'distinct': {f: Counter(r[f] for r in rows).most_common(40) for f in fields if len({r[f] for r in rows}) <= 60}}
        if n.lower().endswith('.prj'):
            out[n] = z.read(n).decode('latin-1')[:200]
    return out


def ckan_dump(rid, fmt='csv'):
    b = fetch(f'{CKAN}/datastore/dump/{rid}', raw=True, timeout=300)
    return list(csv.DictReader(io.StringIO(b.decode('utf-8-sig')))) if b else []


# ---------------- Toronto: garbage day ----------------
def toronto_garbage():
    rows = ckan_dump('47416395-fb31-4252-9737-2367f5a56953')   # pickup-schedule-2026
    cal = Counter(r['Calendar'] for r in rows)
    weeks = sorted({r['WeekStarting'] for r in rows})
    print('  schedule 2026:', len(rows), 'rows; calendars', dict(cal))
    out = {'schedule2026': {'rows': len(rows), 'calendars': cal, 'first': weeks[:2], 'last': weeks[-2:], 'sample': rows[:6]}}
    out['areas'] = shape_attrs(f'{CKAN}/dataset/17bf9ed3-aa5f-4932-9335-a560db0fea93/resource/bf6ef3d7-72d7-4adb-acb2-34b584841d74/download/swms-daytime-curbside-wgs84-latitude-longitude.zip')
    out['districts'] = shape_attrs(f'{CKAN}/dataset/56074ddb-d229-4626-b615-eb97ccef5243/resource/470ca3a8-aaec-4278-933a-706e737fdae3/download/swms-districts-wgs84.zip')
    for k in ('areas', 'districts'):
        for n, v in out[k].items():
            if isinstance(v, dict): print(' ', k, n, v['rows'], 'rows; fields', v['fields'])
    save('toronto_garbage.json', out)
    return {'calendars': cal, 'areas_fields': [v['fields'] for v in out['areas'].values() if isinstance(v, dict)],
            'areas_distinct': [v['distinct'] for v in out['areas'].values() if isinstance(v, dict)]}


# ---------------- Toronto: GIS server layers on collection, snow, beaches ----------------
WANT = re.compile(r'collect|garbage|solid ?waste|swm|recycl|green ?bin|yard|snow|plow|plough|salt|windrow|beach|swim|drop.?in', re.I)


def toronto_gis():
    root = fetch(f'{GIS}?f=json') or {}
    services = list(root.get('services', []))
    for folder in root.get('folders', []):
        services += (fetch(f'{GIS}/{folder}?f=json') or {}).get('services', []); time.sleep(1)
    hits = []
    for s in services:
        if s.get('type') not in ('MapServer', 'FeatureServer'): continue
        url = f"{GIS}/{s['name']}/{s['type']}"
        info = fetch(url + '?f=json'); time.sleep(1)   # the server rejects bursts
        if not info: continue
        for l in info.get('layers', []) + info.get('tables', []):
            if WANT.search(l.get('name', '')):
                meta = fetch(f"{url}/{l['id']}?f=json") or {}; time.sleep(1)
                cnt = fetch(f"{url}/{l['id']}/query?" + urllib.parse.urlencode({'where': '1=1', 'returnCountOnly': 'true', 'f': 'json'})) or {}
                smp = fetch(f"{url}/{l['id']}/query?" + urllib.parse.urlencode({'where': '1=1', 'outFields': '*', 'returnGeometry': 'false', 'resultRecordCount': 5, 'f': 'json'})) or {}
                time.sleep(1)
                h = {'service': url, 'id': l['id'], 'name': l['name'], 'geometry': meta.get('geometryType'),
                     'fields': [f.get('name') for f in meta.get('fields') or []], 'count': cnt.get('count'),
                     'editDate': (meta.get('editingInfo') or {}).get('lastEditDate'),
                     'sample': [f.get('attributes') for f in smp.get('features', [])]}
                hits.append(h); print('  HIT', l['name'], url, l['id'], h['count'], h['fields'][:12])
    save('toronto_gis.json', {'services': len(services), 'hits': hits})
    return {'services': len(services), 'hits': [(h['name'], h['service'].split('/services/')[1], h['id'], h['count']) for h in hits]}


# ---------------- Toronto: drop-in programs ----------------
def toronto_dropins():
    rows = ckan_dump('c99ec04f-4540-482c-9ee4-efb38774eab4')   # Drop-in
    locs = ckan_dump('f23ac1ad-6f46-4b59-811f-eb34be9b1f7a')   # Locations
    print('  drop-in rows', len(rows), 'locations', len(locs))
    def iv(s):
        try: return int(float(s))
        except Exception: return None
    firsts = sorted(r['First Date'][:10] for r in rows if r.get('First Date'))
    soon = [r for r in rows if r.get('First Date') and TODAY.isoformat() <= r['First Date'][:10] <= (TODAY + timedelta(days=7)).isoformat()]
    kids = [r for r in soon if (iv(r['Age Max']) or 99) <= 12 or (iv(r['Age Min']) or 0) <= 6]
    out = {
        'rows': len(rows), 'fields': list(rows[0].keys()) if rows else [],
        'dates': [firsts[:1], firsts[-1:]], 'next7days': len(soon), 'next7days_kids': len(kids),
        'sections': Counter(r['Section'] for r in rows).most_common(60),
        'titles_kids_next7': Counter(r['Course Title'] for r in kids).most_common(60),
        'ageMin': Counter(r['Age Min'] for r in rows).most_common(30), 'ageMax': Counter(r['Age Max'] for r in rows).most_common(30),
        'locations_fields': list(locs[0].keys()) if locs else [], 'locations_sample': locs[:4],
        'locations_with_dropins': len({r['Location ID'] for r in rows}),
        'sample': rows[:5],
    }
    save('toronto_dropins.json', out)
    return {k: out[k] for k in ('rows', 'dates', 'next7days', 'next7days_kids', 'locations_fields', 'locations_with_dropins')}


# ---------------- Toronto: beaches ----------------
def toronto_beaches():
    q = urllib.parse.urlencode({'resource_id': '8102bd4c-83cd-4354-9788-eecc0c7a09b4', 'limit': 2000, 'sort': 'collectionDate desc'})
    rec = ((fetch(f'{CKAN}/api/3/action/datastore_search?{q}') or {}).get('result') or {}).get('records', [])
    season = [r for r in rec if (r.get('collectionDate') or '')[:4] == str(TODAY.year)]
    per = {}
    for r in season:
        b = per.setdefault(r['beachName'], {'id': r['beachId'], 'dates': set(), 'with_value': 0, 'sites': set()})
        b['dates'].add(r['collectionDate'][:10]); b['sites'].add(r['siteName']); b['with_value'] += r.get('eColi') is not None
    per = {k: {'id': v['id'], 'days': len(v['dates']), 'first': min(v['dates']), 'last': max(v['dates']), 'sites': len(v['sites']), 'with_value': v['with_value']} for k, v in per.items()}
    obs = fetch(f'{CKAN}/api/3/action/datastore_search?' + urllib.parse.urlencode({'resource_id': 'b1b87de1-e021-43c2-a80e-69028fe9fafa', 'limit': 5, 'sort': '_id desc'})) or {}
    # The City's own beach page: look for the feed behind its status table.
    page = fetch('https://www.toronto.ca/community-people/health-wellness-care/health-programs-advice/beach-water-quality/', raw=True) or b''
    feeds = sorted(set(re.findall(rb'https?://[^"\'\s<>]+(?:json|api|beach)[^"\'\s<>]*', page)))[:40]
    out = {'season_rows': len(season), 'beaches': per, 'observations_fields': [f['id'] for f in (obs.get('result') or {}).get('fields', [])],
           'observations_sample': (obs.get('result') or {}).get('records', []), 'page_links': [f.decode('latin-1') for f in feeds]}
    save('toronto_beaches.json', out)
    return {'season_rows': len(season), 'beaches': len(per), 'page_links': out['page_links'][:15]}


# ---------------- Chicago ----------------
def soda(view, **q):
    return fetch(f'{SOC}/resource/{view}.json?' + urllib.parse.urlencode(q)) or []


def meta(view):
    m = fetch(f'{SOC}/api/views/{view}.json') or {}
    return {'name': m.get('name'), 'rowsUpdatedAt': datetime.utcfromtimestamp(m['rowsUpdatedAt']).isoformat() if m.get('rowsUpdatedAt') else None,
            'columns': [(c.get('fieldName'), c.get('name')) for c in m.get('columns', [])], 'license': (m.get('license') or {}).get('name'),
            'attribution': m.get('attribution')}


def chicago_activities():
    v = 'tn7v-6rnw'
    m = meta(v)
    cols = {n: f for f, n in m['columns']}
    sd, cat, age, typ = cols.get('Start Date'), cols.get('Category'), cols.get('Age Range'), cols.get('Activity Type')
    n = soda(v, **{'$select': 'count(*)'})
    span = soda(v, **{'$select': f'min({sd}),max({sd})'}) if sd else []
    nxt = soda(v, **{'$where': f"{sd} between '{TODAY}T00:00:00' and '{TODAY + timedelta(days=14)}T23:59:59'", '$limit': 50000}) if sd else []
    out = {'meta': m, 'count': n, 'span': span, 'next14': len(nxt),
           'categories': Counter(r.get(cat) for r in nxt).most_common(40), 'ages': Counter(r.get(age) for r in nxt).most_common(40),
           'types': Counter(r.get(typ) for r in nxt).most_common(20),
           'with_coords': sum(1 for r in nxt if r.get(cols.get('Latitude', 'latitude'))), 'sample': nxt[:5]}
    save('chicago_activities.json', out)
    return {k: out[k] for k in ('count', 'span', 'next14', 'with_coords')} | {'updated': m['rowsUpdatedAt'], 'license': m['license']}


def chicago_beaches():
    out = {}
    for v in ('2ivx-z93u', 'xvsz-3xcj', 't62e-8nvc'):
        m = meta(v); cols = {n: f for f, n in m['columns']}
        when = cols.get('DNA Sample Timestamp') or cols.get('Culture Sample 1 Timestamp') or cols.get('Date')
        rows = soda(v, **{'$order': f'{when} DESC', '$limit': 40}) if when else []
        out[v] = {'meta': m, 'latest': rows[:40]}
        print(' ', v, m['name'], m['rowsUpdatedAt'], 'latest', rows[0].get(when) if rows else None)
    save('chicago_beaches.json', out)
    return {v: {'name': o['meta']['name'], 'updated': o['meta']['rowsUpdatedAt'], 'latest': (o['latest'][0] if o['latest'] else None)} for v, o in out.items()}


def chicago_catalog(qs):
    res = {}
    for q in qs:
        c = fetch('https://api.us.socrata.com/api/catalog/v1?' + urllib.parse.urlencode({'domains': 'data.cityofchicago.org', 'q': q, 'limit': 25})) or {}
        res[q] = [(r['resource']['name'], r['resource']['id'], r['resource'].get('data_updated_at')) for r in c.get('results', [])]
        for x in res[q][:12]: print(' ', q, '|', x)
    return res


def chicago_sweep_snow():
    cat = chicago_catalog(['street sweeping 2026', 'sweeping zones', 'snow route', 'winter overnight parking', 'garbage', 'sanitation', 'recycling', 'blue cart'])
    sched = {'meta': meta('u5ai-3efk'), 'sample': soda('u5ai-3efk', **{'$limit': 8})}
    out = {'catalog': cat, 'sweep2026': sched}
    save('chicago_sweep_snow.json', out)
    return {'catalog': {k: v[:8] for k, v in cat.items()}, 'sweep2026_columns': sched['meta']['columns'], 'sweep2026_sample': sched['sample'][:3]}


step('toronto_garbage', toronto_garbage)
step('toronto_dropins', toronto_dropins)
step('toronto_beaches', toronto_beaches)
step('chicago_activities', chicago_activities)
step('chicago_beaches', chicago_beaches)
step('chicago_sweep_snow', chicago_sweep_snow)
step('toronto_gis', toronto_gis)   # last: slow (one request a second across ~85 services)
print('\ndone')
