"""Second round of New York City fetches. Runs in GitHub Actions (fetch-nyc.yml):
- the two map-type datasets the resource API answered empty on October 18 (State Senate h4i2-acfi, BIDs ejxk-d93y),
  taken from the geospatial export
- NJ Transit, PATH and AirTrain route relations with their geometry (the first query asked for tags only)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import step, FAILED
import fetch

step('socrata', lambda: fetch.socrata(only={'senate', 'bids'}))
step('rail', fetch.rail)
print('FAILED:', FAILED or 'none')
