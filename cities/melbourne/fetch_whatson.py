"""Scout What's On Melbourne (the City of Melbourne's listings site) through its public MCP server
(https://whatson.melbourne.vic.gov.au/mcp, no key; see /.well-known/mcp.json) and save raw answers under
raw/whatson/, to design the Events page from. Terms (whatson.melbourne.vic.gov.au/disclaimer): content is the
Council's, no commercial reuse; nothing restricts automated access. Run in GitHub Actions (the sandbox can't reach it).
"""
import json, os, sys, time, urllib.request
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'whatson')
os.makedirs(OUT, exist_ok=True)
URL = 'https://whatson.melbourne.vic.gov.au/mcp'
UA = 'layers.city (non-commercial civic map; https://layers.city/)'
session = None
n = 0


def rpc(method, params=None, note=False):
    global session, n
    n += 1
    body = {'jsonrpc': '2.0', 'method': method}
    if not note: body['id'] = n
    if params is not None: body['params'] = params
    h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'User-Agent': UA}
    if session: h['Mcp-Session-Id'] = session
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=60) as r:
        session = r.headers.get('Mcp-Session-Id') or session
        raw = r.read().decode('utf-8', 'replace')
        ctype = r.headers.get('Content-Type', '')
    if note: return None
    if 'event-stream' in ctype:   # SSE: the last "data:" line holds the answer
        datas = [l[5:].strip() for l in raw.splitlines() if l.startswith('data:')]
        raw = datas[-1] if datas else '{}'
    return json.loads(raw)


def save(name, obj):
    json.dump(obj, open(os.path.join(OUT, name), 'w'), ensure_ascii=False, indent=1)


init = rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
                          'clientInfo': {'name': 'layers.city', 'version': '1.0'}})
save('initialize.json', init)
try: rpc('notifications/initialized', note=True)
except Exception as ex: print('initialized note:', ex)
save('tools.json', rpc('tools/list'))
for t in ('get_categories_tool', 'get_sub_categories_tool', 'get_locations_tool', 'get_date_keywords_tool', 'get_tags_tool'):
    try: save(t + '.json', rpc('tools/call', {'name': t, 'arguments': {}}))
    except Exception as ex: print(t, ex)
    time.sleep(1)
d0 = date.today(); d1 = d0 + timedelta(days=30)
for page in range(1, 4):
    try:
        res = rpc('tools/call', {'name': 'search_tool', 'arguments': {
            'query': '', 'category': 'things_to_do', 'date_keyword': 'specific_dates',
            'date_range': f'{d0} to {d1}', 'page_number': page}})
        save(f'search_p{page}.json', res)
        print('page', page, len(json.dumps(res)))
    except Exception as ex:
        print('search page', page, ex)
    time.sleep(2)
print('done')
