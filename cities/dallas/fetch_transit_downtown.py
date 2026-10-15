"""Travel time by transit from every Dallas ZIP code (inside the city) to downtown Dallas, on a weekday morning.
Run from GitHub Actions (needs Java 21, r5py and internet access); writes raw/transit_downtown.json.
Dallas's version of cities/vancouver/fetch_transit_waterfront.py.

How it works:
  1. Download DART's schedules (GTFS: light rail, the Silver Line, the TRE, buses) and an OpenStreetMap extract.
  2. Scatter origin points about 400 m apart inside each ZIP code unit (docs/dallas/data/zips.geojson).
  3. Route every point with r5py (Conveyal R5): walk + any transit, leaving between 8:00 and 9:00 on a regular
     weekday, median trip over that hour, to the quickest of four downtown points: Akard, St. Paul, West End
     and EBJ Union Station (downtown is a district, as Chicago's Loop is).
  4. A ZIP's figure is the median over its points.
"""
import csv, datetime as dt, io, json, os, statistics, subprocess, sys, time, urllib.request, zipfile

sys.argv += ['--max-memory', '12G']   # r5py reads its JVM settings from the command line
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'tmp', 'transit'); os.makedirs(WORK, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}
LOOP = [('Akard Station', -96.7984, 32.7820), ('St. Paul Station', -96.7929, 32.7853), ('West End Station', -96.8053, 32.7814), ('EBJ Union Station', -96.8075, 32.7760)]
DART = ['https://www.dart.org/transitdata/latest/google_transit.zip']
PROVINCE = 'https://download.geofabrik.de/north-america/us/texas-latest.osm.pbf'
BBOX = '-97.15,32.50,-96.40,33.12'    # west,south,east,north: the city plus a margin


def download(url, path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=600) as r, open(path, 'wb') as f:
                while True:
                    b = r.read(1 << 20)
                    if not b: break
                    f.write(b)
            print('  got', url, os.path.getsize(path) // 1024, 'KB')
            return path
        except Exception as e:
            print('  retry', i + 1, url, e); time.sleep(10 * (i + 1))
    return None


def gtfs_ok(path):
    try:
        with zipfile.ZipFile(path) as z:
            return 'stop_times.txt' in z.namelist()
    except Exception:
        return False


def tidied(path):
    """Rewrite a GTFS zip with every header and value stripped of surrounding spaces, leaving out
    tables that have a header but no rows (R5 rejects those)."""
    out = path.replace('.zip', '-clean.zip')
    # R5 also refuses a shape with a single point (TransLink's feed has some): drop those shapes, and the
    # trips that point at them lose their shape (R5 then draws them stop to stop).
    with zipfile.ZipFile(path) as zi:
        n_pts = {}
        if 'shapes.txt' in zi.namelist():
            for v in csv.DictReader(io.TextIOWrapper(zi.open('shapes.txt'), encoding='utf-8-sig')):
                k = (v.get('shape_id') or '').strip(); n_pts[k] = n_pts.get(k, 0) + 1
    bad = {k for k, n in n_pts.items() if n < 2}
    print('  shapes with fewer than 2 points, dropped:', len(bad))
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            if not n.endswith('.txt'):
                zo.writestr(n, zi.read(n)); continue
            if n.startswith('fare_'):   # DART's monthly-pass transfer durations are past R5's one-day limit; fares aren't used here
                print('  leaving out', n); continue
            rows = [[v.strip() for v in row] for row in csv.reader(io.TextIOWrapper(zi.open(n), encoding='utf-8-sig')) if any(v.strip() for v in row)]
            if bad and n in ('shapes.txt', 'trips.txt') and rows and 'shape_id' in rows[0]:
                k = rows[0].index('shape_id')
                if n == 'shapes.txt': rows = [rows[0]] + [r for r in rows[1:] if r[k] not in bad]
                else: rows = [rows[0]] + [r[:k] + [''] + r[k + 1:] if r[k] in bad else r for r in rows[1:]]
            if len(rows) < 2:
                print('  leaving out empty', n, 'from', os.path.basename(path)); continue
            buf = io.StringIO(); csv.writer(buf, lineterminator='\n').writerows(rows)
            zo.writestr(n, buf.getvalue())
    return out


feeds, log = [], []
for name, urls, needed in (('dart', DART, True),):
    for u in urls:
        p = download(u, os.path.join(WORK, name + '.zip'))
        if p and gtfs_ok(p):
            feeds.append(tidied(p)); log.append(name.upper() + ': ' + u); break
    else:
        if needed: raise SystemExit('No ' + name + ' GTFS found')
        print('WARNING: no', name, 'feed; going on without it')

# Walking network.
pbf = os.path.join(WORK, 'dallas.osm.pbf')
# bbbike's Dallas extract stops near 33.0° N, short of far North Dallas (75252, 75287 reached nothing), so cut the
# area from Geofabrik's Texas file instead.
big = download(PROVINCE, os.path.join(WORK, 'texas.osm.pbf'))
subprocess.run(['osmium', 'extract', '-b', BBOX, big, '-o', pbf, '--overwrite'], check=True)
log.append('OSM: Geofabrik Texas, cut to ' + BBOX)


# A regular weekday that every feed covers: the second Tuesday from today, checked against calendars.
def service_range(path):
    lo, hi = [], []
    with zipfile.ZipFile(path) as z:
        for fn in ('calendar.txt', 'calendar_dates.txt'):
            if fn not in z.namelist(): continue
            for v in csv.DictReader(io.TextIOWrapper(z.open(fn), encoding='utf-8-sig')):
                v = {k.strip(): (x or '').strip() for k, x in v.items()}
                for k in ('start_date', 'date'):
                    if v.get(k): lo.append(v[k])
                for k in ('end_date', 'date'):
                    if v.get(k): hi.append(v[k])
    return min(lo), max(hi)


ranges = [service_range(f) for f in feeds]
print('feed ranges', ranges)
start = max(dt.datetime.strptime(a, '%Y%m%d').date() for a, b in ranges)
end = min(dt.datetime.strptime(b, '%Y%m%d').date() for a, b in ranges)
day = max(start, dt.date.today()) + dt.timedelta(days=7)
while day.weekday() != 1: day += dt.timedelta(days=1)          # Tuesday
if day > end:
    day = start
    while day.weekday() != 1: day += dt.timedelta(days=1)
depart = dt.datetime.combine(day, dt.time(8, 0))
print('departure', depart)

# Origin points.
import geopandas as gpd
from shapely.geometry import Point, shape
pts = []
las = json.load(open(os.path.join(HERE, '..', '..', 'docs', 'dallas', 'data', 'zips.geojson')))['features']
for f in las:
    code = int(f['properties']['code'])
    g = shape(f['geometry']).buffer(0)
    x0, y0, x1, y1 = g.bounds; dx, dy = 400 / 93600, 400 / 111000
    mine = []
    y = y0 + dy / 2
    while y < y1:
        x = x0 + dx / 2
        while x < x1:
            if g.contains(Point(x, y)): mine.append((x, y))
            x += dx
        y += dy
    if len(mine) < 3:
        rp = g.representative_point(); mine.append((rp.x, rp.y))
    for i, (x, y) in enumerate(mine):
        pts.append({'id': code * 10000 + i, 'code': code, 'geometry': Point(x, y)})
origins = gpd.GeoDataFrame(pts, crs='EPSG:4326')
dest = gpd.GeoDataFrame([{'id': i, 'geometry': Point(x, y)} for i, (_, x, y) in enumerate(LOOP)], crs='EPSG:4326')
print(len(origins), 'origin points,', len(dest), 'destination')

import r5py
from r5py import TransportNetwork, TransportMode
net = TransportNetwork(pbf, feeds)
kw = dict(origins=origins[['id', 'geometry']], destinations=dest, departure=depart,
          departure_time_window=dt.timedelta(hours=1), transport_modes=[TransportMode.TRANSIT, TransportMode.WALK],
          max_time=dt.timedelta(minutes=180))
try:
    tt = r5py.TravelTimeMatrix(net, **kw)
except (AttributeError, TypeError):
    tt = r5py.TravelTimeMatrixComputer(net, **kw).compute_travel_times()
col = 'travel_time' if 'travel_time' in tt.columns else [c for c in tt.columns if c.startswith('travel_time')][0]
tt = tt[tt[col].notna()]
best = tt.groupby('from_id')[col].min().to_dict()                       # quickest of the Loop points
via = tt.loc[tt.groupby('from_id')[col].idxmin()].set_index('from_id')['to_id'].to_dict()

out, points, used = {}, [], {}
for code, grp in origins.groupby('code'):
    vals = [float(best[i]) for i in grp['id'] if i in best]
    for (_, r) in grp.iterrows():
        v = best.get(r['id'])
        points.append([round(r.geometry.x, 4), round(r.geometry.y, 4), None if v is None else int(v)])
        if r['id'] in via: used[LOOP[int(via[r['id']])][0]] = used.get(LOOP[int(via[r['id']])][0], 0) + 1
    out[str(code)] = {'minutes': round(statistics.median(vals)) if vals else None,
                      'best': round(min(vals)) if vals else None, 'points': len(grp), 'reached': len(vals)}
json.dump({'to': 'downtown Dallas', 'destinations': [[n, x, y] for n, x, y in LOOP],
           'departure': depart.isoformat(), 'window_minutes': 60, 'modes': 'walk + transit (DART: light rail, Silver Line, TRE, buses)',
           'sources': log, 'areas': out, 'points': points},
          open(os.path.join(HERE, 'raw', 'transit_downtown.json'), 'w'), separators=(',', ':'))
mins = sorted(v['minutes'] for v in out.values() if v['minutes'] is not None)
print('wrote raw/transit_downtown.json:', len(out), 'ZIPs; minutes min/median/max', mins[0], mins[len(mins) // 2], mins[-1])
for k, v in sorted(out.items()): print('  ', k, v)
