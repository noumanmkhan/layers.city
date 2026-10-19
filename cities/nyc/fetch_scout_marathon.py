"""One-off: save the street centerline (inkn-q76z) for every street name the 2025 marathon notice could name, to
raw/scouting/marathon_centerline.json, so fetch_marathon.py's placement can be checked offline. Not part of any build."""
import json, os, re, sys, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from centerline import CL_API, UA, core, norm

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'raw', 'scouting'); os.makedirs(OUT, exist_ok=True)
text = open(os.path.join(HERE, 'raw', 'closures', 'marathon_2025.txt')).read()
words = set()
for line in text.splitlines():
    w = re.sub(r'[^A-Za-z0-9 ]', ' ', line).split()
    for k in range(len(w)):
        for n in (1, 2, 3, 4):
            if k + n <= len(w): words.add(core(norm(' '.join(w[k:k + n]))))
names = sorted(x for x in words if x and len(x) < 30)
rows = []
for i in range(0, len(names), 60):
    q = "street_name in(%s)" % ','.join("'" + n.replace("'", "''") + "'" for n in names[i:i + 60])
    rows += json.load(urllib.request.urlopen(urllib.request.Request(CL_API + '?' + urllib.parse.urlencode({'$select': 'street_name,full_street_name,boroughcode,the_geom', '$where': q, '$limit': 50000}), headers=UA), timeout=300))
like = []
for pat in ('%CENTRAL PARK%', '%AMERICAS%', '%VERRAZ%', '%PULASKI%', '%QUEENSBORO%', '%WILLIS AVE%', '%MADISON AVE%BR%', '%DEEGAN%', '%DAHLGREN%', '%MC GUINNESS%', '%MCGUINNESS%', '%MC CLEAN%', '%MCCLEAN%', '%TORICELLI%', '%FINGERBOARD%', '%RICHMOND TER%', '%SCHOOL RD%', '%MOUNT MORRIS%', '%MT MORRIS%', '%MARCUS GARVEY%', '%FREDERICK DOUGLASS%', '%ADAM CLAYTON%'):
    like += json.load(urllib.request.urlopen(urllib.request.Request(CL_API + '?' + urllib.parse.urlencode({'$select': 'street_name,full_street_name,boroughcode,the_geom', '$where': "upper(full_street_name) like '" + pat + "'", '$limit': 5000}), headers=UA), timeout=300))
out = []
for r in rows + like:
    g = r.get('the_geom') or {}
    parts = (g.get('coordinates') or []) if g.get('type') == 'MultiLineString' else [g.get('coordinates')] if g.get('type') == 'LineString' else []
    for p in parts:
        if p and len(p) > 1: out.append([r.get('boroughcode'), r.get('street_name'), r.get('full_street_name'), [[round(x, 6), round(y, 6)] for x, y in p]])
json.dump(out, open(os.path.join(OUT, 'marathon_centerline.json'), 'w'), separators=(',', ':'))
print(len(names), 'names asked;', len(out), 'segments saved;', len({(o[0], o[2]) for o in out}), 'streets')
