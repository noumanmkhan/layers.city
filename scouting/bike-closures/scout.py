"""Scouting run: can we show bike lanes closed or narrowed by construction (Toronto and Chicago)?

Not a city build; nothing here feeds the map. Asked on social media (October 14, 2026):
"Can you filter for bike lanes closed due to construction?"

Questions:
  1. Does either city's permit feed flag bike lanes itself (a field, a type, or words in the text)?
  2. If not, can we find them by matching ALL active permits (not just transit ones) against the
     city's bike network? How many, what kind of closure, which kind of bike facility?
  3. How noisy is the match (does a curb-lane permit on a street with a painted lane really block it)?

  Toronto: City Road Restrictions live feed (v3 JSON, polylines) x Cycling Network (CKAN cycling-network,
           4326 GeoJSON; INFRA-HIGH / INFRA-LOW types).
  Chicago: CDOT Transportation Department Permits (Socrata pubx-yq2d; a point at the start of an address
           range, street name, closure Full/Partial/Curblane/Sidewalk) x Bike Routes (hvv9-38ut; displayrou).

Writes scouting/bike-closures/out/: summary.json, toronto.json, chicago.json (matched records, trimmed).
Run by .github/workflows/scout-bike-closures.yml (the sandbox can't reach these hosts).
"""
import json, math, os, re, time, urllib.parse, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone

from shapely.geometry import LineString, Point, shape
from shapely.ops import transform
from shapely.strtree import STRtree

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
OUT = os.path.join(ROOT, 'scouting', 'bike-closures', 'out')
os.makedirs(OUT, exist_ok=True)
UA = 'city-layers-scout/1.0 (+https://layers.city; one-off bike lane closure data check)'
NOW = datetime.now(timezone.utc)
TODAY = NOW.date()
SOON = TODAY + timedelta(days=7)
BIKE_RE = re.compile(r'BIKE|BICYC|CYCL|BIKEWAY|CYCLE TRACK|BIKE ?LANE|MULTI.?USE', re.I)
BUF_M = 15          # a permit line "runs along" a bike facility if this close
MIN_OVERLAP_M = 25  # ...for at least this long (or most of a short permit)


def http(url, timeout=240, accept='application/json'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def retry(fn, tries=4, label=''):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            print(f'  {label} attempt {i + 1} failed: {e}')
            time.sleep(6 * (i + 1))
    raise SystemExit(f'{label}: gave up')


def projector(lat0):
    kx = 111320 * math.cos(math.radians(lat0))
    return lambda x, y, z=None: (x * kx, y * 110540)


def norm_street(s):
    s = (s or '').upper()
    s = re.sub(r'\b(N|S|E|W|NORTH|SOUTH|EAST|WEST)\b', ' ', s)
    s = re.sub(r'\b(AVE|AV|AVENUE|ST|STREET|RD|ROAD|BLVD|BOULEVARD|DR|DRIVE|PKWY|PARKWAY|HWY|PL|CT|TER|WAY|CRES|CIR)\b', ' ', s)
    return re.sub(r'[^A-Z0-9]+', ' ', s).strip()


def top(c, n=30):
    return dict(Counter(c).most_common(n))


def key_survey(recs, limit_vals=15):
    """Every key seen, how often it's non-empty, and its most common values (short ones only)."""
    seen = {}
    for r in recs:
        for k, v in r.items():
            e = seen.setdefault(k, {'n': 0, 'vals': Counter()})
            if v not in (None, '', [], {}):
                e['n'] += 1
                if isinstance(v, (str, int, float, bool)) and len(str(v)) <= 60:
                    e['vals'][str(v)] += 1
    return {k: {'nonempty': e['n'], 'distinct_short': len(e['vals']),
                'top': dict(e['vals'].most_common(limit_vals)) if len(e['vals']) <= 400 else 'many'}
            for k, e in sorted(seen.items())}


def text_hits(recs, fields=None):
    """Records whose text mentions bikes, by field."""
    by_field, hits = Counter(), []
    for r in recs:
        found = [k for k, v in r.items() if (fields is None or k in fields) and isinstance(v, str) and BIKE_RE.search(v)]
        if found:
            by_field.update(found)
            hits.append(r)
    return hits, dict(by_field)


# ---------- Toronto ----------
def toronto():
    print('Toronto: road restrictions feed')
    raw = retry(lambda: http('https://secure.toronto.ca/opendata/cart/road_restrictions/v3?format=json'), label='toronto feed')
    text = re.sub(r'\\(["\\/bfnrtu]?)', lambda m: m.group(0) if m.group(1) else '\\\\', raw.decode('utf-8', 'replace'))
    data = json.loads(text, strict=False)
    recs = [r for k, v in data.items() if isinstance(v, list) for r in v]
    print('  records', len(recs))

    ms = lambda t: datetime.fromtimestamp(int(t) / 1000, timezone.utc).date() if t else None

    def active(r):
        s, e = ms(r.get('startTime')), ms(r.get('endTime'))
        return (s is None or s <= SOON) and (e is None or e >= TODAY)

    act = [r for r in recs if active(r)]
    hits, hit_fields = text_hits(act)
    print('  active', len(act), 'bike words', len(hits))

    print('Toronto: cycling network')
    gj = json.loads(retry(lambda: http('https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/abbe5ee3-e249-4f86-a219-f0022eaddcc9/resource/023da9a2-8848-4e10-9cad-e7f9119cd874/download/cycling-network-4326.geojson'), label='cycling network'))
    feats = gj['features']
    props0 = feats[0]['properties'] if feats else {}
    infra_keys = [k for k in props0 if 'INFRA' in k.upper()]
    name_key = next((k for k in props0 if 'STREET' in k.upper() and 'NAME' in k.upper()), None) or \
        next((k for k in props0 if 'STREET' in k.upper()), None)
    hi_key = next((k for k in infra_keys if 'HIGH' in k.upper()), infra_keys[0] if infra_keys else None)
    print('  features', len(feats), 'infra keys', infra_keys, 'name key', name_key)

    P = projector(43.7)
    bike_geoms, bike_props = [], []
    for f in feats:
        if not f.get('geometry'):
            continue
        bike_geoms.append(transform(P, shape(f['geometry'])))
        bike_props.append(f['properties'])
    tree = STRtree(bike_geoms)

    def geom_of(r):
        pts = []
        if r.get('geoPolyline'):
            try:
                pts = json.loads('[' + r['geoPolyline'] + ']')
            except Exception:
                pts = []
        if len(pts) >= 2:
            return transform(P, LineString(pts)), 'line'
        try:
            return transform(P, Point(float(r['longitude']), float(r['latitude']))), 'point'
        except (KeyError, TypeError, ValueError):
            return None, None

    matched, no_geom = [], 0
    for r in act:
        g, kind = geom_of(r)
        if g is None:
            no_geom += 1
            continue
        best = None
        for i in tree.query(g.buffer(BUF_M)):
            b = bike_geoms[i]
            if kind == 'line':
                ov = g.intersection(b.buffer(BUF_M)).length
                ok = ov >= min(MIN_OVERLAP_M, 0.6 * g.length)
            else:
                ov = 0.0
                ok = g.distance(b) <= BUF_M
            if ok and (best is None or ov > best[1]):
                best = (i, ov)
        if best is None:
            continue
        p = bike_props[best[0]]
        same_name = norm_street(p.get(name_key)) == norm_street(r.get('road')) if name_key else None
        desc = (r.get('description') or '').replace('Toronto-TMC: ', '')
        matched.append({
            'id': r.get('id'), 'road': r.get('road'), 'from': r.get('fromRoad'), 'to': r.get('toRoad'),
            'type': r.get('type'), 'subType': r.get('subType'), 'maxImpact': r.get('maxImpact'),
            'roadClass': r.get('roadClass'), 'source': r.get('source'), 'workEventType': r.get('workEventType'),
            'contractor': r.get('contractor'), 'start': str(ms(r.get('startTime'))), 'end': str(ms(r.get('endTime'))),
            'workPeriod': r.get('workPeriod'), 'geom': kind, 'overlap_m': round(best[1]),
            'bike_street': p.get(name_key), 'bike_infra': p.get(hi_key), 'bike_infra_all': {k: p.get(k) for k in infra_keys},
            'same_street': same_name, 'mentions_bike': bool(BIKE_RE.search(desc)),
            'mentions_curb': bool(re.search(r'CURB', desc, re.I)), 'description': desc[:300],
        })
    along = [m for m in matched if m['same_street']]
    print('  matched', len(matched), 'same street', len(along))

    summ = {
        'records_in_feed': len(recs),
        'active_or_within_7_days': len(act),
        'feed_keys': key_survey(recs),
        'bike_words_in_active': {'count': len(hits), 'by_field': hit_fields,
                                 'examples': [{k: r.get(k) for k in ('road', 'fromRoad', 'toRoad', 'type', 'subType', 'source', 'description')} for r in hits[:40]]},
        'cycling_network': {'features': len(feats), 'keys': list(props0), 'infra_key_used': hi_key,
                            'by_infra': top(Counter(p.get(hi_key) for p in bike_props), 40)},
        'match': {
            'no_geometry': no_geom,
            'touching_bike_facility': len(matched),
            'same_street_as_facility': len(along),
            'same_street_by_type': top(f"{m['type']}/{m['subType']}" for m in along),
            'same_street_by_impact': top(m['maxImpact'] for m in along),
            'same_street_by_infra': top(m['bike_infra'] for m in along),
            'same_street_by_source': top(m['source'] for m in along),
            'same_street_by_workEventType': top(m['workEventType'] for m in along),
            'same_street_mentions_bike': sum(m['mentions_bike'] for m in along),
            'same_street_mentions_curb': sum(m['mentions_curb'] for m in along),
            'same_street_roads': top((m['road'] for m in along), 60),
            'cross_street_only': len(matched) - len(along),
        },
    }
    json.dump({'same_street': along, 'other_touching': [m for m in matched if not m['same_street']],
               'bike_words': hits}, open(os.path.join(OUT, 'toronto.json'), 'w'), indent=1, default=str)
    return summ


# ---------- Chicago ----------
PERMITS = 'https://data.cityofchicago.org/resource/pubx-yq2d.json'


def soql(params):
    url = PERMITS + '?' + urllib.parse.urlencode(params)
    return json.loads(retry(lambda: http(url), label='socrata'))


def chicago():
    print('Chicago: CDOT permits')
    lo, hi = TODAY.isoformat(), SOON.isoformat()
    active = f"applicationenddate >= '{lo}T00:00:00' AND applicationstartdate <= '{hi}T00:00:00'"
    total = soql({'$select': 'count(*) AS n', '$where': active})
    sample = soql({'$where': active, '$limit': 2000})
    by_closure = soql({'$select': 'streetclosure, count(*) AS n', '$where': active, '$group': 'streetclosure', '$order': 'n DESC', '$limit': 50})
    by_work = soql({'$select': 'worktypedescription, count(*) AS n', '$where': active, '$group': 'worktypedescription', '$order': 'n DESC', '$limit': 80})

    cols = sorted({k for r in sample for k in r})
    textcols = [c for c in cols if c in ('applicationname', 'comments', 'detail', 'worktypedescription', 'applicationdescription', 'parkingmeterpostingorbagging', 'placement')]
    bike_kw = ' OR '.join(f"upper({c}) like '%{w}%'" for c in textcols for w in ('BIKE', 'BICYC', 'CYCLE'))
    bike_rows = soql({'$where': f'{active} AND ({bike_kw})', '$limit': 5000}) if textcols else []
    print('  active', total, 'bike words', len(bike_rows))

    rows = soql({'$where': f"{active} AND streetclosure in ('Full', 'Partial', 'Curblane', 'FULL', 'PARTIAL', 'CURBLANE')", '$limit': 50000})
    print('  closing rows', len(rows))

    print('Chicago: bike routes')
    gj = json.loads(retry(lambda: http('https://data.cityofchicago.org/resource/hvv9-38ut.geojson?$limit=50000'), label='bike routes'))
    feats = [f for f in gj['features'] if f.get('geometry')]
    P = projector(41.85)
    geoms = [transform(P, shape(f['geometry'])) for f in feats]
    props = [f['properties'] for f in feats]
    tree = STRtree(geoms)
    print('  bike route features', len(feats))

    def street_of(r):
        return ' '.join(x for x in (r.get('streetname'), r.get('suffix')) if x)

    matched, no_point = [], 0
    for r in rows:
        try:
            pt = transform(P, Point(float(r['longitude']), float(r['latitude'])))
        except (KeyError, TypeError, ValueError):
            no_point += 1
            continue
        best = None
        for i in tree.query(pt.buffer(40)):
            d = pt.distance(geoms[i])
            if d <= 40 and norm_street(props[i].get('street') or props[i].get('st_name')) == norm_street(street_of(r)):
                if best is None or d < best[1]:
                    best = (i, d)
        if best is None:
            continue
        p = props[best[0]]
        txt = ' '.join(r.get(c) or '' for c in ('applicationname', 'comments', 'detail'))
        matched.append({
            'app': r.get('applicationnumber'), 'closure': r.get('streetclosure'), 'worktype': r.get('worktypedescription'),
            'type': r.get('applicationdescription'), 'street': ' '.join(x for x in (r.get('direction'), street_of(r)) if x),
            'from_no': r.get('streetnumberfrom'), 'to_no': r.get('streetnumberto'), 'placement': r.get('placement'),
            'start': (r.get('applicationstartdate') or '')[:10], 'end': (r.get('applicationenddate') or '')[:10],
            'applicant': r.get('primarycontactlast'), 'route': p.get('displayrou'), 'contraflow': p.get('contraflow'),
            'dist_m': round(best[1]), 'mentions_bike': bool(BIKE_RE.search(txt)), 'text': txt[:300],
        })
    print('  matched', len(matched))

    summ = {
        'active_window': [lo, hi],
        'active_rows': total,
        'columns': cols,
        'sample_key_survey': key_survey(sample),
        'by_streetclosure': by_closure,
        'by_worktype': by_work,
        'bike_words_in_active': {'count': len(bike_rows),
                                 'by_closure': top(r.get('streetclosure') for r in bike_rows),
                                 'by_worktype': top(r.get('worktypedescription') for r in bike_rows),
                                 'examples': [{k: r.get(k) for k in ('applicationname', 'worktypedescription', 'streetclosure', 'streetname', 'comments', 'detail')} for r in bike_rows[:40]]},
        'bike_routes': {'features': len(feats), 'keys': sorted({k for p in props for k in p}),
                        'by_route_type': top(p.get('displayrou') for p in props)},
        'match': {
            'closing_rows': len(rows), 'no_point': no_point,
            'on_bike_route_same_street': len(matched),
            'by_closure': top(m['closure'] for m in matched),
            'by_route_type': top(m['route'] for m in matched),
            'closure_x_route': top(f"{m['closure']} / {m['route']}" for m in matched),
            'by_worktype': top(m['worktype'] for m in matched),
            'by_placement': top(m['placement'] for m in matched),
            'mentions_bike': sum(m['mentions_bike'] for m in matched),
            'streets': top((m['street'] for m in matched), 60),
            'with_address_range': sum(1 for m in matched if m['from_no'] and m['to_no'] and m['from_no'] != m['to_no']),
        },
    }
    json.dump({'matched': matched, 'bike_words': bike_rows}, open(os.path.join(OUT, 'chicago.json'), 'w'), indent=1)
    return summ


summary = {'run_utc': NOW.isoformat(timespec='seconds')}
for name, fn in (('toronto', toronto), ('chicago', chicago)):
    try:
        summary[name] = fn()
    except SystemExit as e:
        summary[name] = {'error': str(e)}
        print('  ', e)
    except Exception as e:
        import traceback; traceback.print_exc()
        summary[name] = {'error': repr(e)}
json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1, default=str)
print(json.dumps({c: summary[c].get('match', summary[c]) for c in ('toronto', 'chicago')}, indent=1, default=str)[:8000])
