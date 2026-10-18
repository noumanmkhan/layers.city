"""Second round of New York City fetches. Runs in GitHub Actions (fetch-nyc.yml):
- the State Senate districts and BIDs from their tabular datasets (afns-vxeu, 7jdm-inj8): the map-type views
  (h4i2-acfi, ejxk-d93y) answer the resource API empty and have no export
- NJ Transit, PATH and AirTrain route relations with their geometry, and rail stations with positions"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import step, FAILED
import fetch

step('socrata', lambda: fetch.socrata(only={'senate', 'bids'}))
step('stations', fetch.stations)
print('FAILED:', FAILED or 'none')
