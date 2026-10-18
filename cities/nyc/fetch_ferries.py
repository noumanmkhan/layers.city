"""Fetch the ferry timetables into cities/nyc/raw/ferries/: NYC Ferry (its live GTFS zip) and the Staten Island Ferry
(NYC DOT's GTFS on NYC Open Data, b57i-ri22; nyc.gov's own link answers 403). ferries.py draws the routes and
landings from their shapes and stops. Runs in GitHub Actions (fetch-nyc.yml)."""
import io, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, RAW

OUT = os.path.join(RAW, 'ferries'); os.makedirs(OUT, exist_ok=True)
for name, url in [('nycferry', 'http://nycferry.connexionz.net/rtt/public/utility/gtfs.aspx'),
                  ('siferry', 'https://data.cityofnewyork.us/download/b57i-ri22/application/x-zip-compressed')]:
    data = get(url)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        print(name, len(data) // 1024, 'KB', z.namelist())
        for n in ('routes.txt', 'shapes.txt', 'stops.txt'):
            if n in z.namelist(): print('  ', n, z.read(n).decode('utf-8-sig', 'replace').splitlines()[:3])
    open(os.path.join(OUT, name + '.zip'), 'wb').write(data)
