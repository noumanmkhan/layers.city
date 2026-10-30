"""Main streets in San Francisco from OpenStreetMap (ODbL), with tertiary roads: OpenStreetMap files several of the
City's main streets (Valencia, Church, 24th, Irving, Judah, Taraval...) as tertiary. build.py keeps a tertiary road
only when it's on names.py MAJOR_STREETS. Runs in Actions (fetch-sf.yml). Writes raw/osm_streets.json."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

b = lambda bb: f'({bb[1]},{bb[0]},{bb[3]},{bb[2]})'
step('streets', lambda: overpass(f'[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary|tertiary)$"]["name"]{b(CITY)};out tags geom;', 'osm_streets.json'))
print('FAILED:', FAILED or 'none')
