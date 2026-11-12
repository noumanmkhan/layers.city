"""The Yarra's course through the City (OpenStreetMap, ODbL), which build.py uses to split the locality "Melbourne"
into the CBD and St Kilda Road. fetch.py's own try hit three busy Overpass servers in a row on November 12, 2026."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import CITY, FAILED, step, overpass

bb = '%s,%s,%s,%s' % (CITY[1], CITY[0], CITY[3], CITY[2])
step('osm yarra', lambda: overpass(f'[out:json][timeout:120];way["waterway"="river"]["name"="Yarra River"]({bb});out tags geom;', 'osm_yarra.json'))
print('done; failed:', FAILED or 'none')
