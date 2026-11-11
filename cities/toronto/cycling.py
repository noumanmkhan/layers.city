"""Reduce Toronto's cycling sources to the small files the cycling explainer page reads (cities/toronto/cycling/).

Usage: python3 cities/toronto/cycling.py [--bikeshare DIR]

Inputs (notes: scouting/cycling-growth/FINDINGS.md):
- Bike Share Toronto ridership trip files (Toronto Parking Authority, Open Government Licence – Toronto), downloaded
  by hand from the City's open data portal and unzipped into raw/bikeshare_rides/ (gitignored, about 5.5 GB). Any
  folder layout works: every .csv under it is read. Skipped when the folder is missing; bikeshare.json is kept.
- raw/bikes.geojson, the City's Cycling Network (the map's own fetch).
- The City's retired "bikeways" package (2019 and 2023 snapshots of the network), the Permanent Bicycle Counters and
  the Bicycle Cordon Counts, fetched from the open data portal into tmp/ (gitignored) on first run.
- raw/tts/, the Transportation Tomorrow Survey cross-tabs exported by hand from the DMG's iDRS.

Outputs: cycling/bikeshare.json, network.json, tts.json, counts.json. The page build reads only these."""
import csv, glob, json, os, re, sys, urllib.request
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
RAW, TMP, OUT = os.path.join(HERE, 'raw'), os.path.join(HERE, 'tmp', 'cycling'), os.path.join(HERE, 'cycling')
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)
BS_DIR = sys.argv[sys.argv.index('--bikeshare') + 1] if '--bikeshare' in sys.argv else os.path.join(RAW, 'bikeshare_rides')
CKAN = 'https://ckan0.cf.opendata.inter.prod-toronto.ca/api/3/action/package_show?id='


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'  wrote cycling/{name} ({os.path.getsize(os.path.join(OUT, name)) // 1024} KB)')


def resource(package, name):
    """A package resource's file, downloaded once into tmp/."""
    dest = os.path.join(TMP, re.sub(r'[^\w.-]+', '_', name))
    if not os.path.exists(dest):
        pkg = json.load(urllib.request.urlopen(CKAN + package, timeout=60))['result']
        url = next(r['url'] for r in pkg['resources'] if r['name'] == name)
        print('  fetching', name)
        urllib.request.urlretrieve(url, dest)
    return dest


# ---- Bike Share: trips per month, the busiest day, and e-bike trips from 2024 (when the files start naming the bike model) ------------
def parse_date(s):
    """(year, a, b, None) for a d/m or m/d date, or (year, month, None, day) for an ISO one."""
    s = s.strip()
    m = re.match(r'(\d{4})-(\d{2})(?:-(\d{2}))?', s)
    if m:
        return int(m.group(1)), int(m.group(2)), None, int(m.group(3)) if m.group(3) else None
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', s)
    if m:
        y = m.group(3)
        return int('20' + y if len(y) == 2 else y), int(m.group(1)), int(m.group(2)), None
    return None


def bikeshare():
    files = sorted(f for f in glob.glob(os.path.join(BS_DIR, '**', '*.csv'), recursive=True) if not os.path.basename(f).startswith('~'))
    if not files:
        print(f'bikeshare: no trip files in {BS_DIR}; keeping cycling/bikeshare.json')
        return
    trips, ebike, other_model, models, unknown = Counter(), Counter(), Counter(), Counter(), 0
    days = Counter()                                       # trips by the day they began
    for f in files:
        fh = open(f, encoding='latin-1', newline='')      # mixed encodings across years; latin-1 reads every byte
        rd = csv.reader(fh)
        head = [h.strip().lower().lstrip('﻿ï»¿').replace('  ', ' ') for h in next(rd)]
        st = next(i for i, h in enumerate(head) if 'start' in h and 'time' in h)
        md = next((i for i, h in enumerate(head) if 'model' in h), None)
        fm = re.search(r'(20\d\d)-(\d\d)', os.path.basename(f))    # monthly files name their month
        seen, models_f, n = Counter(), [], 0                  # dates kept as written; the day/month order is decided per file
        for r in rd:
            if not any(r):
                continue
            n += 1
            d = parse_date(r[st]) if st < len(r) else None
            if not d and fm:
                d = (int(fm.group(1)), int(fm.group(2)), None, None)
            if not d:
                unknown += 1
                continue
            mk = r[md].strip() if md is not None and md < len(r) else None
            seen[(d, mk)] += 1
        day_first = max((d[1] for d, _ in seen if d[2] is not None), default=0) > 12
        for (d, mk), c in seen.items():
            mo = d[1] if d[2] is None else (d[2] if day_first else d[1])
            m = f'{d[0]}-{mo:02d}'
            trips[m] += c
            dy = d[3] if d[2] is None else (d[1] if day_first else d[2])
            if dy:
                days[f'{m}-{dy:02d}'] += c
            if mk is not None:
                models[mk] += c
                if mk.startswith('EFIT'):
                    ebike[m] += c
                elif mk != 'ICONIC':
                    other_model[m] += c
        fh.close()
        print(f'  {os.path.relpath(f, BS_DIR)}: {n:,} rows{" (day-first dates)" if day_first else ""}')
    months = sorted(m for m in trips if m >= '2017-01')
    allm = [f'{y}-{mo:02d}' for y in range(2017, int(months[-1][:4]) + 1) for mo in range(1, 13) if f'{y}-{mo:02d}' <= months[-1]]
    missing = [m for m in allm if trips[m] == 0]
    days = {k: v for k, v in days.items() if k[:7] in allm}
    top = max(days, key=days.get)
    by_year = {}
    for k, v in days.items():
        if v > by_year.get(k[:4], ('', 0))[1]:
            by_year[k[:4]] = (k, v)
    save('bikeshare.json', {
        'months': [[m, trips[m] or None] for m in allm],
        'ebike': {m: ebike[m] for m in allm if ebike[m]},
        'otherModel': {m: other_model[m] for m in allm if other_model[m]},
        'busiest': {'day': top, 'trips': days[top], 'byYear': {y: list(v) for y, v in sorted(by_year.items())}},
        'models': dict(models), 'missing': missing, 'through': months[-1], 'unparsedDates': unknown,
    })
    print(f'bikeshare: {sum(trips.values()):,} trips, {months[0]} to {months[-1]}, missing months {missing}')
    print(f'bikeshare: busiest day {top}, {days[top]:,} trips; by year', {y: v for y, v in sorted(by_year.items())})


# ---- Cycling network: km by install year, dated snapshots, and the stretch the Province removed -------------------
try:                       # only the network part needs pyproj, so the Bike Share count runs without it
    from pyproj import Geod
    GEOD = Geod(ellps='WGS84')
except ImportError:
    GEOD = None
CLASS = {'Cycle Track': 'prot', 'Bi-Directional Cycle Track': 'prot', 'Cycle Track - Contraflow': 'prot',
         'Bike Lane': 'paint', 'Bike Lane - Buffered': 'paint', 'Bike Lane - Contraflow': 'paint'}


def klass(h):
    h = h or ''
    return CLASS.get(h) or ('trail' if 'Trail' in h or h == 'Park Road' else 'shared')


def lines(geom):
    return [geom['coordinates']] if geom['type'] == 'LineString' else geom['coordinates']


def km(geom):
    return sum(GEOD.line_length([p[0] for p in l], [p[1] for p in l]) for l in lines(geom)) / 1000


def totals(feats, length):
    t = Counter()
    for f in feats:
        if f.get('geometry'):
            t[klass(f['properties'].get('INFRA_HIGHORDER'))] += length(f)
    return {k: round(v, 1) for k, v in t.items()}


def along(coords, start, dist_m, west=True):
    """The part of a polyline from the vertex nearest `start`, running dist_m metres west (or east)."""
    raw = sorted(coords, key=lambda p: p[0], reverse=west)
    pts = [raw[0]]
    for a, b in zip(raw, raw[1:]):                  # densify to ~10 m so the start sits on the corner, not a far vertex
        n = max(1, int(GEOD.line_length([a[0], b[0]], [a[1], b[1]]) // 10))
        pts += [[a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n] for k in range(1, n + 1)]
    i0 =min(range(len(pts)), key=lambda i: (pts[i][0] - start[0]) ** 2 + (pts[i][1] - start[1]) ** 2)
    out, run = [pts[i0]], 0
    for a, b in zip(pts[i0:], pts[i0 + 1:]):
        d = GEOD.line_length([a[0], b[0]], [a[1], b[1]])
        if run + d >= dist_m:
            t = (dist_m - run) / d
            out.append([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
            return out
        out.append(b); run += d
    return out


def network(cfg):
    now = json.load(open(os.path.join(RAW, 'bikes.geojson'), encoding='utf-8'))
    feats = now['features']
    by_year = defaultdict(Counter)
    for f in feats:
        p = f['properties']
        by_year[int(p['INSTALLED'] or 0)][klass(p['INFRA_HIGHORDER'])] += km(f['geometry'])
    asof = re.search(r'modified (\d{4}-\d{2}-\d{2})', open(os.path.join(RAW, 'fetch_bikes.log')).read()).group(1)
    snaps = [{'date': asof, 'km': totals(feats, lambda f: km(f['geometry'])), 'src': 'Cycling Network (current)'}]
    # Retired snapshots. The 2023 file is in degrees; the 2019 one is in a projected system whose Shape__Length runs
    # long by a constant factor, measured here against the 2023 file (the same field, the same segments' units).
    s23 = json.load(open(resource('bikeways', 'Bike network data - 4326.geojson'), encoding='utf-8'))
    geo23 = sum(km(f['geometry']) for f in s23['features'] if f.get('geometry'))
    shp23 = sum(f['properties']['Shape__Length'] for f in s23['features']) / 1000
    factor = shp23 / geo23
    s19 = json.load(open(resource('bikeways', 'Bike network data - 2945.geojson'), encoding='utf-8'))
    last = lambda fc: max(str(f['properties'].get('LAST_EDIT_DATE') or '') for f in fc['features'])[:10]
    snaps.insert(0, {'date': last(s23), 'km': totals(s23['features'], lambda f: km(f['geometry'])), 'src': 'bikeways (retired), 4326 file'})
    snaps.insert(0, {'date': last(s19), 'km': totals(s19['features'], lambda f: f['properties']['Shape__Length'] / 1000 / factor),
                     'src': f'bikeways (retired), 2945 file; Shape__Length / {factor:.3f}', 'approx': True})
    # Removed stretches: drawn along the current file's line for that street, from a known corner for the stated length.
    removed = []
    for r in cfg.get('removed', []):
        seg = [c for f in feats if f['properties']['STREET_NAME'] == r['street'] for l in lines(f['geometry']) for c in l]
        line = along(seg, r['anchor'], r['km'] * 1000, west=r['direction'] == 'west')
        removed.append({**{k: r[k] for k in ('id', 'label', 'from', 'to', 'km', 'start', 'done')}, 'line': [[round(x, 6), round(y, 6)] for x, y in line]})
        print(f'  removed {r["label"]}: {len(line)} points, ends at {line[-1][0]:.5f}, {line[-1][1]:.5f}')
    years = sorted(by_year)
    save('network.json', {
        'asof': asof, 'byYear': {y: {k: round(v, 2) for k, v in by_year[y].items()} for y in years},
        'snapshots': snaps, 'removed': removed, 'shapeFactor': round(factor, 4),
    })
    print('network:', ', '.join(f'{s["date"]} prot {s["km"].get("prot")} paint {s["km"].get("paint")}' for s in snaps))


# ---- TTS: shares and counts, from the hand exports -----------------------------------------------------------------
def tts_table(name):
    rows = list(csv.reader(open(os.path.join(RAW, 'tts', name), encoding='utf-8')))
    i = next(k for k, r in enumerate(rows) if r and r[0] == '' and len(r) > 2)
    head = rows[i][1:]
    return head, {r[0]: [float(x or 0) for x in r[1:]] for r in rows[i + 1:] if r and r[0]}


def by_mode(name, mode_is_row):
    head, d = tts_table(name)
    if mode_is_row:
        return {m: round(sum(v)) for m, v in d.items()}
    return {h: round(sum(v[j] for v in d.values())) for j, h in enumerate(head)}


def bike_by_hour(name):
    head, d = tts_table(name)
    j = head.index('Cycle')
    h = Counter()
    for t, v in d.items():
        h[(int(t) // 100) % 24] += v[j]
    return [round(h[(k + 4) % 24]) for k in range(24)]     # 4 a.m. first, as the survey's day runs


def tts():
    out = {}
    for y, sfx in (('2011', ''), ('2016', ''), ('2022', '_excl2016')):
        head, d = tts_table(f'trips_within_toronto_by_mode_{y}{sfx}.txt')
        j = head.index('PD 1 of Toronto')
        out[y] = {
            'withinToronto': {m: round(sum(v)) for m, v in d.items()},
            'torontoToPd1': {m: round(v[j]) for m, v in d.items()},
            'intoPd1': by_mode(f'trips_into_pd1_by_hour_mode_{y}{sfx}.txt', False),
            'outOfPd1': by_mode(f'trips_out_of_pd1_by_hour_mode_{y}{sfx}.txt', False),
            'withinPd1': by_mode(f'trips_within_pd1_by_hour_mode_{y}{sfx}.txt', True),
            'bikeIntoPd1ByHour': bike_by_hour(f'trips_into_pd1_by_hour_mode_{y}{sfx}.txt'),
        }
    fall = by_mode('trips_within_toronto_by_mode_2022_excl2016_fall.txt', True)
    out['2022fall'] = {'withinToronto': fall}
    save('tts.json', out)
    for y in ('2011', '2016', '2022'):
        w = out[y]['withinToronto']; t = sum(w.values())
        print(f'tts {y}: bike {w["Cycle"]:,} of {t:,} = {100 * w["Cycle"] / t:.2f}%')


# ---- Counts: permanent counters (Apr–Sep averages) and the downtown cordon ----------------------------------------
def counts(cfg):
    daily = resource('permanent-bicycle-counters', 'cycling_permanent_counts_daily.csv')
    locs = {r['location_dir_id']: r for r in csv.DictReader(open(resource('permanent-bicycle-counters', 'cycling_permanent_counts_locations.csv'), encoding='utf-8'))}
    want = set(cfg['counters'])
    day = defaultdict(lambda: defaultdict(dict))      # site -> date -> direction -> volume
    for r in csv.DictReader(open(daily, encoding='utf-8')):
        if r['location_name'] in want:
            day[r['location_name']][r['dt'][:10]][r['direction']] = int(float(r['daily_volume']))
    ndir = Counter()
    for l in locs.values():
        if l['location_name'] in want:
            ndir[l['location_name']] += 1
    sites = []
    for name in cfg['counters']:
        per = defaultdict(list)
        for dt, dirs in day[name].items():
            if len(dirs) == ndir[name] and 4 <= int(dt[5:7]) <= 9:
                per[dt[:4]].append(sum(dirs.values()))
        cal = sorted({l['latest_calibration_study'] for l in locs.values() if l['location_name'] == name and l['latest_calibration_study']})
        sites.append({'name': name, 'calibrated': cal[-1] if cal else None,
                      'aprSep': {y: {'avg': round(sum(v) / len(v)), 'days': len(v)} for y, v in sorted(per.items()) if len(v) >= 175}})
    old = list(csv.DictReader(open(resource('bicycle-cordon-count-2010-2013-2014', 'Cordon Count Summary - 2010 2013 and 2014 - 4326.csv'), encoding='utf-8')))
    new = list(csv.DictReader(open(resource('bicycle-and-micromobility-cordon-count', 'Bicycle and Micromobility Cordon Count 2022 - Count Summary - 4326.csv'), encoding='utf-8')))
    key = lambda r, d: r['Centreline ID'] + r[d]
    keys = {y: {key(r, 'Travel Direction') for r in old if r['Count Year'] == y} for y in ('2010', '2013', '2014')}
    common = keys['2010'] & keys['2013'] & keys['2014'] & {key(r, 'Direction of Travel') for r in new}
    cordon = {y: sum(int(r['Total Volume']) for r in old if r['Count Year'] == y and key(r, 'Travel Direction') in common) for y in keys}
    nb = [r for r in new if key(r, 'Direction of Travel') in common]
    bikes = ('Standard Bicycle Type', 'Cargo Bicycle Type', 'Bike Share Type', 'E-Bicycle Type')
    cordon['2022'] = sum(sum(int(r[b] or 0) for b in bikes) for r in nb)
    cordon['2022all'] = sum(int(r['Total Volume']) for r in nb)
    save('counts.json', {'counters': sites, 'cordon': cordon, 'cordonSites': len(common)})
    print('cordon:', cordon, 'on', len(common), 'site-directions')


if __name__ == '__main__':
    cfg = json.load(open(os.path.join(HERE, 'cycling.json'), encoding='utf-8'))['reduce']
    bikeshare()
    network(cfg)
    tts()
    counts(cfg)
