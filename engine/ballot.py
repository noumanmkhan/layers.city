"""Ballot rows for the card: a city's races on one election's ballot (raw/ballot/candidates.json, written by the
city's ballot.py), turned into representatives.json tables, plus where each sitting member stands.

  ballot_tables(candidates, members) -> tables to merge into representatives.json:
    "race_congress" / "race_house" / "race_senate": {district: {candidates: [names], parties: [party]}}, and for a
        Senate district the ballot covers but has no race, {notUp: true} (staggered terms: the seat isn't up).
    "race_statewide": {"ussenate": {...}, "governor": {...}}
  and sets, on each member record in members[kind] (kind: congress, house, senate), "runs":
    {"office": kind, "district": d} where their name is on a ballot for a seat of that kind, {"office": "statewide",
    "race": key} for a statewide race, or null where it's on none (their seat being up or not is the card's call).

Names are matched loosely, because the sources spell them differently ("Aarón Ortíz" / "Aaron M. Ortiz",
"Bob Rita" / 'Robert "Bob" Rita', "Emil Jones III" / "Emil Jones, III"): same last name, and the same first
name, first initial or quoted nickname. Every match is printed so a run can be checked by eye."""
import re, unicodedata

SUFFIX = {'jr', 'sr', 'ii', 'iii', 'iv'}


def parts(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    nick = re.findall(r'"([^"]+)"', s)
    s = re.sub(r'"[^"]+"', ' ', s.split('&')[0])   # a governor's ticket: the governor
    w = [x for x in re.sub(r'[^a-z\- ]+', ' ', s).split() if x not in SUFFIX]
    return (w[0] if w else '', w[-1] if w else '', [n.split()[0] for n in nick])


# Common short forms of given names, both ways ("Mike Reilly" / "Michael W. Reilly Jr.").
NICK = {'ed': 'edward', 'eddie': 'edward', 'mike': 'michael', 'misha': 'michael', 'joe': 'joseph', 'bob': 'robert',
        'bill': 'william', 'jim': 'james', 'tom': 'thomas', 'dan': 'daniel', 'steve': 'steven', 'chris': 'christopher',
        'alex': 'alexander', 'sam': 'samuel', 'tony': 'anthony', 'nick': 'nicholas', 'liz': 'elizabeth', 'toby': 'toby'}


def words(name):
    s = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
    return [x for x in re.sub(r'[^a-z\- ]+', ' ', re.sub(r'"[^"]+"', ' ', s.split('&')[0])).split() if x not in SUFFIX]


def same(a, b):
    fa, la, na = parts(a); fb, lb, nb = parts(b)
    wa, wb = words(a), words(b)
    # The last name, or a two-part surname shortened to its first part ("Rodneyse Bichotte Hermelyn" / "Rodneyse Bichotte").
    if not la or not (la == lb or len(wa) > 2 and wa[-2] == lb or len(wb) > 2 and wb[-2] == la): return False
    norm = lambda f: NICK.get(f.split('-')[0], f.split('-')[0])   # a hyphenated given name by its first part
    firsts_a, firsts_b = {norm(fa), *map(norm, na)}, {norm(fb), *map(norm, nb)}
    if firsts_a & firsts_b: return True
    if (len(fa) == 1 or len(fb) == 1) and fa[:1] == fb[:1]: return True
    # A first initial before the name used ("J. Gustavo Rivera" / "Gustavo Rivera").
    return len(fa) == 1 and len(wa) > 2 and wa[1] == fb or len(fb) == 1 and len(wb) > 2 and wb[1] == fa


def ballot_tables(cand, members):
    R = cand['races']
    t = {'race_' + k: {d: {'candidates': [c[0] for c in cs], 'parties': [c[1] for c in cs]} for d, cs in R[k].items()}
         for k in ('congress', 'house', 'senate')}
    for d in cand.get('covered', {}).get('senate', []):
        t['race_senate'].setdefault(d, {'notUp': True})
    t['race_statewide'] = {k: {'candidates': [c[0] for c in cs], 'parties': [c[1] for c in cs]} for k, cs in R['statewide'].items()}
    for kind, seats in members.items():
        for d, m in seats.items():
            if not m or not m.get('name'): continue
            runs = None
            for k2 in ('congress', 'house', 'senate'):
                for d2, cs in R[k2].items():
                    hit = next((c[0] for c in cs if same(m['name'], c[0])), None)
                    if hit and (runs is None or (k2 == kind and d2 == d)):
                        runs = {'office': k2, 'district': d2}
                        print('  %s %s: %s = %s %s on the ballot' % (kind, d, m['name'], k2, d2), '' if hit == m['name'] else '(%s)' % hit)
            for k2, cs in R['statewide'].items():
                hit = next((c[0] for c in cs if same(m['name'], c[0])), None)
                if hit and runs is None:
                    runs = {'office': 'statewide', 'race': k2}; print('  %s %s: %s running for %s' % (kind, d, m['name'], k2))
            m['runs'] = runs
    return t
