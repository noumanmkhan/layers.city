"""Travel time by transit from every New York City community district to Midtown, on a weekday morning, to two hubs:
Penn Station (the map's default) and Grand Central (a choice offered later). Run from GitHub Actions (fetch-nyc.yml
with script fetch_transit_penn.py: Java 21 and r5py); writes raw/transit_penn.json. NYC's version of Chicago's
fetch_transit_loop.py.

  1. Schedules: the MTA subway (with the Staten Island Railway), the six MTA bus feeds, the LIRR and Metro-North
     (and the Staten Island Ferry from NYC DOT's GTFS when it downloads), tidied for R5; OpenStreetMap for walking.
  2. Origin points about 400 m apart inside each of the 59 community districts (raw/community_districts.geojson).
  3. r5py: walk + transit, leaving between 8:00 and 9:00 on a regular weekday, median trip over that hour, to
     Penn Station (34 St-Penn Station, 7 Av / 8 Av) and Grand Central (42 St). A district's figure is the median of
     its points.
"""
import csv, datetime as dt, io, json, os, statistics, subprocess, sys, time, urllib.request, zipfile

sys.argv += ['--max-memory', '12G']   # r5py reads its JVM settings from the command line
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'tmp', 'transit'); os.makedirs(WORK, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}
HUBS = [  # (key, name, lon, lat)
    ('penn', 'Penn Station', -73.9935, 40.7506),
    ('gct', 'Grand Central', -73.9772, 40.7527),
]
B = 'https://rrgtfsfeeds.s3.amazonaws.com/'
FEEDS = [('subway', [B + 'gtfs_subway.zip'], True), ('bx', [B + 'gtfs_bx.zip'], True), ('b', [B + 'gtfs_b.zip'], True),
         ('m', [B + 'gtfs_m.zip'], True), ('q', [B + 'gtfs_q.zip'], True), ('si', [B + 'gtfs_si.zip'], True),
         ('busco', [B + 'gtfs_busco.zip'], True), ('lirr', [B + 'gtfslirr.zip'], True), ('mnr', [B + 'gtfsmnr.zip'], True),
         ('siferry', ['https://www.nyc.gov/html/dot/downloads/misc/siferry-gtfs.zip'], False),
         ('nycferry', ['http://nycferry.connexionz.net/rtt/public/utility/gtfs.aspx'], False)]
OSM = 'https://download.bbbike.org/osm/bbbike/NewYork/NewYork.osm.pbf'
STATE = 'https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf'
BBOX = '-74.30,40.45,-73.65,40.95'    # west,south,east,north: the five boroughs plus a margin


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
for name, urls, needed in FEEDS:
    for u in urls:
        p = download(u, os.path.join(WORK, name + '.zip'))
        if p and gtfs_ok(p):
            feeds.append(tidied(p)); log.append(name.upper() + ': ' + u); break
    else:
        if needed: raise SystemExit('No ' + name + ' GTFS found')
        print('WARNING: no', name, 'feed; going on without it')

# Walking network.
pbf = os.path.join(WORK, 'nyc.osm.pbf')
if not download(OSM, pbf):
    big = download(STATE, os.path.join(WORK, 'newyork.osm.pbf'))
    subprocess.run(['osmium', 'extract', '-b', BBOX, big, '-o', pbf, '--overwrite'], check=True)
    log.append('OSM: Geofabrik New York, cut to ' + BBOX)
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


ranges = [service_range(f) for f in feeds[:9]]   # the MTA feeds; the ferries' calendars can run short
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
sys.path.insert(0, HERE)
from names import CD_NAMES
for f in json.load(open(os.path.join(HERE, 'raw', 'community_districts.geojson')))['features']:
    code = int(float(f['properties']['boro_cd']))
    if code not in CD_NAMES: continue   # parks and airports
    g = shape(f['geometry']).buffer(0)
    x0, y0, x1, y1 = g.bounds; dx, dy = 400 / 84400, 400 / 111200
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
dest = gpd.GeoDataFrame([{'id': i, 'geometry': Point(x, y)} for i, (_, _, x, y) in enumerate(HUBS)], crs='EPSG:4326')
print(len(origins), 'origin points,', len(dest), 'hubs')

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
times = {(int(r['from_id']), int(r['to_id'])): float(r[col]) for _, r in tt.iterrows()}
out, points = {}, []
for code, grp in origins.groupby('code'):
    rec = {'points': len(grp)}
    for h, (key, name, _, _) in enumerate(HUBS):
        vals = [times[(i, h)] for i in grp['id'] if (i, h) in times]
        rec[key] = round(statistics.median(vals)) if vals else None
        rec[key + 'Reached'] = len(vals)
    out[str(code)] = rec
    for _, r in grp.iterrows():
        points.append([round(r.geometry.x, 4), round(r.geometry.y, 4)] + [None if (r['id'], h) not in times else int(times[(r['id'], h)]) for h in range(len(HUBS))])
json.dump({'hubs': [[k, n, x, y] for k, n, x, y in HUBS], 'departure': depart.isoformat(), 'window_minutes': 60,
           'modes': 'walk + transit (MTA subway, Staten Island Railway, buses, LIRR, Metro-North, ferries where available)',
           'sources': log, 'areas': out, 'points': points},
          open(os.path.join(HERE, 'raw', 'transit_penn.json'), 'w'), separators=(',', ':'))
for key, *_ in HUBS:
    mins = sorted(v[key] for v in out.values() if v[key] is not None)
    print(key, len(mins), 'districts; minutes min/median/max', mins[0], mins[len(mins) // 2], mins[-1])
