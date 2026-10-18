"""Fetch the street tiers below the main streets from OpenStreetMap (ODbL) into cities/nyc/raw/. Runs in GitHub Actions.
- osm_collectors.json: tertiary roads in the five boroughs, for the collector layer (collectors.py)
- osm_manhattan_ew.json: Manhattan's named streets that carry East or West ("East 42nd Street"), any class, for the
  How addresses work layer (Fifth Avenue splits them)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import overpass, step, CITY, FAILED

b = f'({CITY[1]},{CITY[0]},{CITY[3]},{CITY[2]})'
step('collectors', lambda: overpass(f'[out:json][timeout:300];way["highway"="tertiary"]["name"]{b};out tags geom;', 'osm_collectors.json'))
step('manhattan', lambda: overpass('[out:json][timeout:300];way["highway"~"^(trunk|primary|secondary|tertiary|residential|unclassified)$"]'
                                    '["name"~"^(East|West) "](40.70,-74.02,40.88,-73.90);out tags geom;', 'osm_manhattan_ew.json'))
print('FAILED:', FAILED or 'none')
