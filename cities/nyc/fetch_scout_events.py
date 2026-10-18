"""Scout for New York's special-event closures: upcoming permitted events with street closures (tvpp-9vvx) and their
location text, and the columns of the city's street centerline (CSCL, inkn-q76z), to place closures from that text."""
import json, os, sys, urllib.parse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save

S = 'https://data.cityofnewyork.us/'
now = datetime.utcnow()
where = ("street_closure_type in('Full Street Closure','Sidewalk and Street Closure','Curb Lane Only','Sidewalk and Curb Lane Closure') "
         f"AND end_date_time >= '{now:%Y-%m-%dT00:00:00}' AND start_date_time <= '{now + timedelta(days=15):%Y-%m-%dT00:00:00}'")
rows = json.loads(get(S + 'resource/tvpp-9vvx.json?' + urllib.parse.urlencode({'$where': where, '$limit': 5000})))
print('events', len(rows))
from collections import Counter
print(Counter((r.get('event_type'), r.get('street_closure_type')) for r in rows).most_common(30))
for r in rows[:60]: print(' |', r.get('event_type'), '|', r.get('street_closure_type'), '|', r.get('event_name'), '|', r.get('event_location'), '|', r.get('start_date_time'), r.get('end_date_time'))
for i in ('inkn-q76z',):
    try:
        meta = json.loads(get(S + 'api/views/' + i + '.json'))
        print('==', i, meta.get('name'), [c['fieldName'] for c in meta['columns']])
        smp = json.loads(get(S + 'resource/' + i + '.json?' + urllib.parse.urlencode({'$limit': 2})))
        print('  sample', json.dumps(smp)[:1500])
    except Exception as e: print(i, e)
save('events_scout.json', rows)
