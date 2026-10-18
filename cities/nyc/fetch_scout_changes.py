"""Scout the sources for New York's What's changing layer: column names and value counts of DOB NOW Job
Application Filings (w9ak-ipjd), the legacy DOB Job Application Filings (ic3t-wcy2) and ZAP projects (hgx4-8ukb), so
changes.json can be written against the real fields. Prints only; writes raw/changes_scout.json."""
import json, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get, save

S = 'https://data.cityofnewyork.us/'
out = {}
for i, groups in [('w9ak-ipjd', ['job_type', 'filing_status', 'borough']), ('ic3t-wcy2', ['job_type', 'job_status_descrp']),
                  ('hgx4-8ukb', ['public_status', 'ulurp_non', 'project_status'])]:
    meta = json.loads(get(S + 'api/views/' + i + '.json'))
    cols = [(c['fieldName'], c.get('dataTypeName')) for c in meta['columns']]
    print('==', i, meta.get('name'), meta.get('rowsUpdatedAt'), len(cols), 'columns'); print('  ', cols)
    rec = {'name': meta.get('name'), 'columns': cols, 'counts': {}, 'sample': None}
    for g in groups:
        if g not in [c for c, _ in cols]: print('   no column', g); continue
        q = urllib.parse.urlencode({'$select': g + ', count(*) as n', '$group': g, '$order': 'n DESC', '$limit': 40})
        try:
            rows = json.loads(get(S + 'resource/' + i + '.json?' + q)); rec['counts'][g] = rows; print('  ', g, rows)
        except Exception as e: print('  ', g, e)
    try:
        rec['sample'] = json.loads(get(S + 'resource/' + i + '.json?$limit=2&$order=:id DESC'))
        print('   sample', json.dumps(rec['sample'][0])[:2500])
    except Exception as e: print('   sample', e)
    out[i] = rec
save('changes_scout.json', out)
