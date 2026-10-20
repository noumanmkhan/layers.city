"""Scout: where can planned TTC subway closures (weekend shutdowns) be read as data?

Run in Actions (scout-toronto.yml); the sandbox can't reach ttc.ca. For the iOS app's weekend brief
(weekend.json): the most valuable item is "Line 1 closed Sat-Sun, Finch to Sheppard-Yonge".
Writes cities/toronto/raw/scouting/subway/ with each response (trimmed) and summary.json.
"""
import json, os, re, urllib.request
from html import unescape

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw', 'scouting', 'subway')
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'Mozilla/5.0 (Layers.City scouting; go@layers.city)', 'Accept': '*/*'}

def get(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read()
    except Exception as e:
        return getattr(e, 'code', None), '', str(e).encode()

CANDIDATES = {
    'alerts_api': 'https://alerts.ttc.ca/api/alerts/list',
    'gtfsrt_alerts': 'https://bustime.ttc.ca/gtfsrt/alerts',
    'advisories_subway': 'https://www.ttc.ca/service-advisories/subway-service',
    'advisories_all': 'https://www.ttc.ca/service-advisories',
    'service_changes': 'https://www.ttc.ca/service-advisories/Service-Changes',
}
summary = {}
for key, url in CANDIDATES.items():
    status, ctype, body = get(url)
    ext = 'json' if 'json' in ctype else ('html' if 'html' in ctype else 'bin')
    open(os.path.join(OUT, f'{key}.{ext}'), 'wb').write(body[:400000])
    info = {'url': url, 'status': status, 'type': ctype, 'bytes': len(body)}
    text = body.decode('utf-8', 'replace')
    if ext == 'json':
        try:
            d = json.loads(text)
            info['top_keys'] = list(d.keys())[:20] if isinstance(d, dict) else f'list of {len(d)}'
            items = []
            for k in ('routes', 'alerts', 'planned', 'plannedAlerts', 'siteWideCustom', 'generalCustom', 'stations'):
                v = d.get(k) if isinstance(d, dict) else None
                if isinstance(v, list):
                    info[f'n_{k}'] = len(v)
                    items += [(k, x) for x in v[:400]]
            subway = [(k, x) for k, x in items if re.search(r'subway|line ?[1-4]\b|closure|shuttle', json.dumps(x), re.I)]
            info['subway_like'] = len(subway)
            info['subway_samples'] = [{'from': k, 'item': x} for k, x in subway[:8]]
        except Exception as e:
            info['json_error'] = str(e)
    elif ext == 'html':
        links = sorted(set(re.findall(r'href="(/service-advisories/[^"#?]+)"', text)))
        info['advisory_links'] = links[:80]
        info['title'] = unescape((re.search(r'<title>(.*?)</title>', text, re.S) or [None, ''])[1]).strip()[:200]
        info['json_endpoints'] = sorted(set(re.findall(r'https?://[a-z0-9.-]*ttc\.ca/[^"\'\s<>]*(?:api|json|feed|rss)[^"\'\s<>]*', text, re.I)))[:30]
    summary[key] = info
    print(key, status, ctype, len(body))

# Follow up to 6 subway advisory pages to see what one advisory holds.
pages = [l for l in summary.get('advisories_subway', {}).get('advisory_links', []) if '/subway-service/' in l][:6]
details = []
for path in pages:
    status, ctype, body = get('https://www.ttc.ca' + path)
    text = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', body.decode('utf-8', 'replace'), flags=re.S)
    plain = re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', text))).strip()
    i = plain.find('closure')
    details.append({'path': path, 'status': status, 'excerpt': plain[max(0, i - 600): i + 1500]})
summary['advisory_pages'] = details
json.dump(summary, open(os.path.join(OUT, 'summary.json'), 'w'), indent=1, ensure_ascii=False)
print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ('status', 'type', 'bytes', 'top_keys', 'subway_like')} for k, v in summary.items() if isinstance(v, dict)}, indent=1))
