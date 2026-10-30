"""Travel time by transit from every San Francisco neighborhood on a weekday morning, to two hubs the viewer picks
between: Montgomery Street (the Financial District; the map's default) and 4th & King (Mission Bay). Run from GitHub
Actions (fetch-sf.yml with script fetch_transit.py: Java 21 and r5py); writes raw/transit_downtown.json. San
Francisco's version of New York's fetch_transit_penn.py.

  1. Schedules: Muni (buses, Metro, streetcars, cable cars), BART and Caltrain, tidied for R5; OpenStreetMap for walking.
     Trips start and end in the city, so the region's other operators (511's regional feed) aren't needed.
  2. Origin points about 400 m apart inside each of the 38 residential Analysis Neighborhoods
     (raw/analysis_neighborhoods.geojson; codes as build.py numbers them, alphabetically from 1).
  3. r5py: walk + transit, leaving between 8:00 and 9:00 on a regular weekday, median trip over that hour, to each
     hub. A neighborhood's figure is the median of its points.
"""
import csv, datetime as dt, io, json, os, statistics, subprocess, sys, time, urllib.request, zipfile

sys.argv += ['--max-memory', '5G']   # r5py reads its JVM settings from the command line; a private repo's runner has 7 GB
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'tmp', 'transit'); os.makedirs(WORK, exist_ok=True)
UA = {'User-Agent': 'city-layers-pipeline (github.com/noumanmkhan/city-layers)'}
HUBS = [  # (key, name, lon, lat)
    ('montgomery', 'Montgomery Street', -122.4018, 37.7894),   # BART and Muni Metro, Market at Montgomery/New Montgomery
    ('missionbay', '4th & King', -122.3947, 37.7766),         # Caltrain terminal and the T Third, Mission Bay
]
FEEDS = [('muni', ['https://muni-gtfs.apps.sfmta.com/data/muni_gtfs-current.zip'], True),
         ('bart', ['https://www.bart.gov/dev/schedules/google_transit.zip'], True),
         ('caltrain', ['https://data.trilliumtransit.com/gtfs/caltrain-ca-us/caltrain-ca-us.zip'], True)]
OSM = 'https://download.bbbike.org/osm/bbbike/SanFrancisco/SanFrancisco.osm.pbf'
STATE = 'https://download.geofabrik.de/north-america/us/california/norcal-latest.osm.pbf'
BBOX = '-122.56,37.68,-122.33,37.85'   # west,south,east,north: the city plus a margin


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
    tables that have a header but no rows (R5 rejects those). Streams row by row, and keeps only trips
    with a stop between 6:30 and 11:00 (the morning window, with room for long trips): the full bus
    feeds don't fit in a 7 GB runner beside R5."""
    out = path.replace('.zip', '-clean.zip')
    secs = lambda t: (lambda h, m, s: int(h) * 3600 + int(m) * 60 + int(s))(*t.split(':')) if t.count(':') == 2 else None
    rd = lambda zi, n: csv.reader(io.TextIOWrapper(zi.open(n), encoding='utf-8-sig'))
    with zipfile.ZipFile(path) as zi, zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zo:
        keep = None
        if 'stop_times.txt' in zi.namelist():
            r = rd(zi, 'stop_times.txt'); h = [v.strip() for v in next(r)]
            ti, di, ai = h.index('trip_id'), h.index('departure_time'), h.index('arrival_time')
            keep = set()
            for row in r:
                if len(row) <= max(ti, di, ai): continue
                t = secs(row[di].strip() or row[ai].strip())
                if t is not None and 6.5 * 3600 <= t <= 11 * 3600: keep.add(row[ti].strip())
            print('  ', os.path.basename(path), len(keep), 'trips in the morning window')
        for n in zi.namelist():
            if not n.endswith('.txt'):
                zo.writestr(n, zi.read(n)); continue
            r = rd(zi, n)
            try: h = [v.strip() for v in next(r)]
            except StopIteration: continue
            ti = h.index('trip_id') if keep is not None and n in ('stop_times.txt', 'trips.txt', 'frequencies.txt') and 'trip_id' in h else None
            count = 0
            tmp = os.path.join(WORK, 'table.tmp')
            with open(tmp, 'w', encoding='utf-8', newline='') as w:
                cw = csv.writer(w, lineterminator='\n'); cw.writerow(h)
                for row in r:
                    row = [v.strip() for v in row]
                    if not any(row): continue
                    if ti is not None and (len(row) <= ti or row[ti] not in keep): continue
                    cw.writerow(row); count += 1
            if count: zo.write(tmp, n)
            else: print('  leaving out empty', n, 'from', os.path.basename(path))
            os.remove(tmp)
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
pbf = os.path.join(WORK, 'sf.osm.pbf')
if not download(OSM, pbf):
    big = download(STATE, os.path.join(WORK, 'norcal.osm.pbf'))
    subprocess.run(['osmium', 'extract', '-b', BBOX, big, '-o', pbf, '--overwrite'], check=True)
    log.append('OSM: Geofabrik Northern California, cut to ' + BBOX)
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
PARKS = {'Golden Gate Park', 'McLaren Park', 'Lincoln Park'}
nbs = sorted((f['properties']['nhood'].strip(), shape(f['geometry']).buffer(0)) for f in json.load(open(os.path.join(HERE, 'raw', 'analysis_neighborhoods.geojson')))['features'])
for code, (name, g) in enumerate(nbs, 1):
    if name in PARKS: continue
    x0, y0, x1, y1 = g.bounds; dx, dy = 400 / 88000, 400 / 111200
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
           'modes': 'walk + transit (Muni buses, Metro, streetcars and cable cars, BART, Caltrain)',
           'sources': log, 'areas': out, 'points': points},
          open(os.path.join(HERE, 'raw', 'transit_downtown.json'), 'w'), separators=(',', ':'))
for key, *_ in HUBS:
    mins = sorted(v[key] for v in out.values() if v[key] is not None)
    print(key, len(mins), 'neighborhoods; minutes min/median/max', mins[0], mins[len(mins) // 2], mins[-1])
