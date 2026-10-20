"""Fetch Chicago's early voting / election day vote centers for the card's election box.

The Chicago Board of Election Commissioners runs early voting at one site in each of the 50 wards (from
October 19) plus two downtown sites (from October 1), through November 2. Any Chicago voter can vote at
any of them. On election day (November 3) voters can vote at their precinct polling place or at any of
51 vote centers, the 50 ward sites and the downtown SuperSite (the Board's page: "Voters can choose whatever
voting site is most convenient for them, including on Election Day"; "Same Day Registration is available ...
including 51 sites on Election Day"; the Board's office "will not be available on Election Day").

Source: the Board's Early Voting/Vote Centers page. It is saved to raw/vote_centers/page.html and parsed
for ward, name and address. If the page can't be read, the list in raw/vote_centers/manual.json (typed
from the Board's October 19 release as reported by CBS Chicago, with spelling fixed) is used and the
log says so. Addresses are placed with the Census batch geocoder (exact match only), then Nominatim.
Writes raw/vote_centers/centers.json: {asof, source, centers: [{ward, name, address, x, y, ed, ev}]}.
"""
import csv, html, io, json, os, re, sys, time, urllib.parse, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.join(HERE, 'raw', 'vote_centers')
UA = {'User-Agent': 'layers.city map (layers.city)'}
PAGES = ['https://chicagoelections.gov/voting/early-votingvote-centers',
         'https://chicagoelections.gov/news/expanded-person-early-voting-opens-today-all-50-chicago-wards-november-3rd-general-election']


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
        return r.read().decode('utf-8', 'replace')


def text_of(h):
    h = re.sub(r'(?is)<(script|style).*?</\1>', ' ', h)
    h = re.sub(r'(?i)<br\s*/?>|</(p|div|li|tr|td|th|h\d)>', '\n', h)
    return html.unescape(re.sub(r'<[^>]+>', ' ', h))


def parse(h):
    """The page's LOCATIONS table: Ward | Site | Address | Bilingual Voting Official Present (may be empty).
    Ward 52 is the downtown SuperSite. Returns [{ward, name, address}] for wards 1-50 and the SuperSite."""
    t = text_of(h)
    L = [re.sub(r'\s+', ' ', l).strip() for l in t.split('\n')]
    L = [l for l in L if l]
    try:
        i = next(j for j, l in enumerate(L) if l.startswith('Bilingual Voting Official')) + 1
    except StopIteration:
        return []
    out = []
    while i + 2 < len(L) and re.fullmatch(r'\d{1,2}', L[i]):
        w, name, addr = int(L[i]), L[i + 1], L[i + 2]
        i += 3
        if i < len(L) and not re.fullmatch(r'\d{1,2}', L[i]) and not re.match(r'\d+ ', L[i]):
            i += 1   # the bilingual officials column
        # Spelled-out street types for the geocoder ("Douglas Bv.", "Northwest Hw.").
        addr = re.sub(r'\bBv\.?$', 'Blvd.', addr); addr = re.sub(r'\bHw\.?$', 'Hwy.', addr)
        out.append({'ward': w if w <= 50 else None, 'name': 'Voting SuperSite' if w > 50 else name, 'address': addr})
    return out


def geocode(rows):
    buf = io.StringIO(); wr = csv.writer(buf)
    for i, r in enumerate(rows):
        wr.writerow([i, r['address'], 'Chicago', 'IL', ''])
    boundary = 'layerscity'
    body = ('--' + boundary + '\r\nContent-Disposition: form-data; name="benchmark"\r\n\r\nPublic_AR_Current\r\n'
            '--' + boundary + '\r\nContent-Disposition: form-data; name="addressFile"; filename="a.csv"\r\nContent-Type: text/csv\r\n\r\n'
            + buf.getvalue() + '\r\n--' + boundary + '--\r\n').encode()
    req = urllib.request.Request('https://geocoding.geo.census.gov/geocoder/locations/addressbatch', data=body,
                                 headers={**UA, 'Content-Type': 'multipart/form-data; boundary=' + boundary})
    got = {}
    with urllib.request.urlopen(req, timeout=300) as r:
        for row in csv.reader(io.StringIO(r.read().decode('utf-8', 'replace'))):
            if len(row) >= 6 and row[2] == 'Match' and row[3] == 'Exact' and row[5]:
                lon, lat = row[5].split(',')
                got[int(row[0])] = (float(lon), float(lat), row[4])
    return got


def nominatim(addr):
    q = urllib.parse.urlencode({'q': addr + ', Chicago, IL', 'format': 'jsonv2', 'limit': 1, 'countrycodes': 'us',
                                'viewbox': '-87.95,42.03,-87.52,41.64', 'bounded': 1})
    time.sleep(1.1)
    r = json.loads(get('https://nominatim.openstreetmap.org/search?' + q))
    return (float(r[0]['lon']), float(r[0]['lat'])) if r else None


def main():
    os.makedirs(V, exist_ok=True)
    rows, source = [], None
    for u in PAGES:
        try:
            h = get(u)
            open(os.path.join(V, 'page%d.html' % PAGES.index(u)), 'w').write(h)
            r = parse(h)
            print('page', u, 'chars', len(h), 'rows', len(r))
            if len(r) >= 50 and not rows:
                rows, source = r, u
        except Exception as e:
            print('page failed', u, e)
    if not rows:
        man = json.load(open(os.path.join(V, 'manual.json')))
        rows, source = man['centers'], man['source']
        print('using manual list:', len(rows), 'rows')
    for r in rows:
        r['ed'], r['ev'] = True, True
    # The downtown sites: the SuperSite (in the page's table as ward 52, else from manual.json) is open on
    # election day too; the Board's office is early voting only ("will not be available on Election Day").
    have = {r['name'] for r in rows}
    for d in json.load(open(os.path.join(V, 'manual.json'))).get('downtown', []):
        if d['name'] not in have:
            rows.append(dict(d))
    # Nothing changed since the last fetch: keep the file (and its date) as it is.
    path = os.path.join(V, 'centers.json')
    old = json.load(open(path)) if os.path.exists(path) else None
    key = lambda rs: [(r.get('ward'), r['name'], r['address'], r.get('ed'), r.get('ev')) for r in rs]
    if old and key(old['centers']) == key(rows):
        print('no change since', old['asof']); return
    known = {r['address']: r for r in (old or {}).get('centers', []) if r.get('x') is not None}
    todo = [r for r in rows if r['address'] not in known]
    for r in rows:
        if r['address'] in known:
            k = known[r['address']]; r['x'], r['y'], r['matched'] = k['x'], k['y'], k.get('matched')
    got = geocode(todo) if todo else {}
    got = {rows.index(todo[i]): v for i, v in got.items()}
    for i, r in enumerate(rows):
        if r.get('x') is not None:
            pass
        elif i in got:
            r['x'], r['y'] = round(got[i][0], 6), round(got[i][1], 6); r['matched'] = got[i][2]
        else:
            try:
                p = nominatim(r['address'])
            except Exception as e:
                p = None; print('  nominatim failed', r['address'], e)
            r['x'], r['y'] = (round(p[0], 6), round(p[1], 6)) if p else (None, None)
            r['matched'] = 'nominatim' if p else None
        print('  ', r.get('ward'), r['name'], '|', r['address'], '->', r['x'], r['y'], r['matched'])
    print('placed', sum(1 for r in rows if r['x'] is not None), 'of', len(rows))
    out = {'asof': datetime.date.today().isoformat(), 'source': source, 'centers': rows}
    json.dump(out, open(path, 'w'), indent=1)


if __name__ == '__main__':
    main()
