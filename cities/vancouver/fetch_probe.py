"""One-off probe (October 11, 2026): which Statistics Canada download routes answer from GitHub's runners.
fetch.py got 403 Forbidden from www12.statcan.gc.ca with the map's own User-Agent. Tries a browser
User-Agent, HEAD and ranged GETs, and the alternatives, then prints what answered. Writes raw/probe.json."""
import json, os, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UAS = {'map': 'city-layers/1.0 (https://maps.noumankhan.ca)',
       'browser': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36',
       'curl': 'curl/8.5.0'}
URLS = [
    'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lcsd000b21a_e.zip',
    'https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/files-fichiers/lda_000b21a_e.zip',
    'https://www12.statcan.gc.ca/census-recensement/2021/dp-pd/prof/details/download-telecharger/comp/GetFile.cfm?Lang=E&FILETYPE=CSV&GEONO=006',
    'https://www150.statcan.gc.ca/n1/en/catalogue/98-401-X2021006',
    'https://api.statcan.gc.ca/census-recensement/profile/sdmx/rest/dataflow/STC_CP/DF_DA?references=none',
    'https://open.canada.ca/data/api/action/package_show?id=750e6035-adf8-4426-966f-4c25b12a999e',
    'https://openmaps.gov.bc.ca/geo/pub/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=WHSE_LEGAL_ADMIN_BOUNDARIES.ABMS_MUNICIPALITIES_SP&count=1&outputFormat=json',
    'https://osmdata.openstreetmap.de/download/land-polygons-split-4326.zip',
]
out = []
for u in URLS:
    for ua_name, ua in UAS.items():
        req = urllib.request.Request(u, headers={'User-Agent': ua, 'Accept': '*/*', 'Accept-Language': 'en-CA,en;q=0.9', 'Range': 'bytes=0-2047'})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                res = {'url': u, 'ua': ua_name, 'status': r.status, 'type': r.headers.get('Content-Type'), 'length': r.headers.get('Content-Length'),
                       'range': r.headers.get('Content-Range'), 'head': r.read(300).decode('latin-1')[:200]}
        except Exception as e:
            res = {'url': u, 'ua': ua_name, 'error': str(e)}
        print(json.dumps(res)[:500]); out.append(res)
        if 'status' in res: break
json.dump(out, open(os.path.join(HERE, 'raw', 'probe.json'), 'w'), indent=1)
