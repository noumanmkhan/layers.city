"""Scout New York's street closure and event permit data for the closures and events layers: columns, value counts
and samples of Street Closures due to construction by block (i6b5-j7bu) and by intersection (478a-yykk), and
NYC Permitted Event Information (tvpp-9vvx). Prints and writes raw/closures_scout.json."""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save

S = 'https://data.cityofnewyork.us/'
out = {}
for i, groups in [('i6b5-j7bu', ['purpose', 'work_on_street']), ('478a-yykk', ['purpose']), ('tvpp-9vvx', ['event_type', 'street_closure_type', 'event_agency', 'event_borough'])]:
    meta = json.loads(get(S + 'api/views/' + i + '.json'))
    cols = [c['fieldName'] for c in meta['columns']]
    print('==', i, meta.get('name'), len(cols), cols)
    rec = {'name': meta.get('name'), 'columns': cols, 'counts': {}}
    for g in groups:
        if g not in cols: print('   no column', g); continue
        q = urllib.parse.urlencode({'$select': g + ', count(*) as n', '$group': g, '$order': 'n DESC', '$limit': 40})
        try: rows = json.loads(get(S + 'resource/' + i + '.json?' + q)); rec['counts'][g] = rows; print('  ', g, rows)
        except Exception as e: print('  ', g, e)
    try:
        smp = json.loads(get(S + 'resource/' + i + '.json?' + urllib.parse.urlencode({'$limit': 3})))
        rec['sample'] = smp; print('   sample', json.dumps(smp)[:2000])
    except Exception as e: print('   sample', e)
    out[i] = rec
save('closures_scout.json', out)
