"""Travel time by transit from every Vancouver local area to Waterfront Station, on a weekday morning.
Run from GitHub Actions (.github/workflows/fetch-transit-waterfront.yml: needs Java 21, r5py and internet
access); writes raw/transit_waterfront.json. Vancouver's version of cities/toronto/fetch_transit_union.py.

How it works:
  1. Download TransLink's schedules (GTFS: SkyTrain, buses, SeaBus and the West Coast Express; one agency
     runs the whole region) and an OpenStreetMap extract for walking.
  2. Scatter origin points about 400 m apart inside each of the 22 local areas (raw/local_areas.geojson,
     numbered 1-22 in alphabetical order, as build.py numbers them), so a big area isn't judged by one spot.
  3. Route every point with r5py (Conveyal R5): walk + any transit, leaving between 8:00 and 9:00 on a regular
     weekday, median trip over that hour, to Waterfront Station, where SkyTrain's Expo and Canada Lines,
     the SeaBus and the West Coast Express meet.
  4. A local area's figure is the median over its points.
"""
import csv, datetime as dt, io, json, os, statistics, subprocess, sys, time, urllib.request, zipfile

sys.argv += ['--max-memory', '12G']   # r5py reads its JVM settings from the command line
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'tmp', 'transit'); os.makedirs(WORK, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}
LOOP = [('Waterfront Station', -123.1116, 49.2856)]   # one destination (the list keeps Chicago's shape)
TRANSLINK = ['https://gtfs-static.translink.ca/gtfs/google_transit.zip']
OSM = 'https://download.bbbike.org/osm/bbbike/Vancouver/Vancouver.osm.pbf'
PROVINCE = 'https://download.geofabrik.de/north-america/canada/british-columbia-latest.osm.pbf'
BBOX = '-123.30,49.12,-122.90,49.36'    # west,south,east,north: the city plus a margin


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
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
        for n in zi.namelist():
            if not n.endswith('.txt'):
                zo.writestr(n, zi.read(n)); continue
            rows = [[v.strip() for v in row] for row in csv.reader(io.TextIOWrapper(zi.open(n), encoding='utf-8-sig')) if any(v.strip() for v in row)]
            if len(rows) < 2:
                print('  leaving out empty', n, 'from', os.path.basename(path)); continue
            buf = io.StringIO(); csv.writer(buf, lineterminator='\n').writerows(rows)
            zo.writestr(n, buf.getvalue())
    return out


feeds, log = [], []
for name, urls, needed in (('translink', TRANSLINK, True),):
    for u in urls:
        p = download(u, os.path.join(WORK, name + '.zip'))
        if p and gtfs_ok(p):
            feeds.append(tidied(p)); log.append(name.upper() + ': ' + u); break
    else:
        if needed: raise SystemExit('No ' + name + ' GTFS found')
        print('WARNING: no', name, 'feed; going on without it')

# Walking network.
pbf = os.path.join(WORK, 'vancouver.osm.pbf')
if not download(OSM, pbf):
    big = download(PROVINCE, os.path.join(WORK, 'bc.osm.pbf'))
    subprocess.run(['osmium', 'extract', '-b', BBOX, big, '-o', pbf, '--overwrite'], check=True)
    log.append('OSM: Geofabrik British Columbia, cut to ' + BBOX)
else:
    log.append('OSM: ' + OSM)


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
las = sorted(json.load(open(os.path.join(HERE, 'raw', 'local_areas.geojson')))['features'], key=lambda f: f['properties']['name'].strip())
for code, f in enumerate(las, 1):
    g = shape(f['geometry']).buffer(0)
    x0, y0, x1, y1 = g.bounds; dx, dy = 400 / 72600, 400 / 111000
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
json.dump({'to': 'Waterfront Station', 'destinations': [[n, x, y] for n, x, y in LOOP],
           'departure': depart.isoformat(), 'window_minutes': 60, 'modes': 'walk + transit (TransLink: SkyTrain, buses, SeaBus, West Coast Express)',
           'sources': log, 'areas': out, 'points': points},
          open(os.path.join(HERE, 'raw', 'transit_waterfront.json'), 'w'), separators=(',', ':'))
mins = sorted(v['minutes'] for v in out.values() if v['minutes'] is not None)
print('wrote raw/transit_waterfront.json:', len(out), 'local areas; minutes min/median/max', mins[0], mins[len(mins) // 2], mins[-1])
for k, v in sorted(out.items(), key=lambda kv: int(kv[0])): print('  ', k, las[int(k) - 1]['properties']['name'], v)
