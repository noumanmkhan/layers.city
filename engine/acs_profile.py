"""The American Community Survey figures for one area, shared by the US cities' lens scripts (a neighbourhood's summed
tracts, a ZIP, or a single tract or ZIP beyond the city). setup(labels) reads the tables' variables from the Census
labels once; figures(s, m, name) returns the card's fields from counts s (the core tables: B25003, B08301, B25075,
B25063) and m (the extra tables: B25032, B25036, C16001, B01001, B05005), which are usually the same counts.
Medians of home value and cash rent are read from the summed brackets by linear interpolation."""

# Bracket lower edges (dollars), in table order.
VALUE = [0, 10e3, 15e3, 20e3, 25e3, 30e3, 35e3, 40e3, 50e3, 60e3, 70e3, 80e3, 90e3, 100e3, 125e3, 150e3, 175e3,
         200e3, 250e3, 300e3, 400e3, 500e3, 750e3, 1e6, 1.5e6, 2e6]                      # B25075_E002..E027
RENT = [0, 100, 150, 200, 250, 300, 350, 400, 450, 500, 550, 600, 650, 700, 750, 800, 900, 1000, 1250, 1500,
        2000, 2500, 3000, 3500]                                                          # B25063_E003..E026


def median(counts, edges):
    total = sum(counts)
    if not total: return None
    half, run = total / 2, 0
    for i, c in enumerate(counts):
        if run + c >= half:
            if i == len(edges) - 1: return edges[i]          # open-ended top bracket
            return edges[i] + (half - run) / c * (edges[i + 1] - edges[i])
        run += c


def setup(labels):
    global LAB, UNIT_VARS, BUILT_VARS, LANG_VARS, AGE_VARS, RECENT_PERIOD, RECENT_VARS, ENTRY, leaf, shares, LANG_NAME
    LAB = {k: lab.split('!!') for k, lab in labels.items()}
    leaf = lambda k: LAB[k][-1].rstrip(':')

    def vars_where(table, test):
        return [k for k in sorted(LAB) if k.startswith(table + '_') and test(LAB[k])]

    UNITS = {'1, detached': 0, '1, attached': 1, '2': 2, '3 or 4': 2, '5 to 9': 2, '10 to 19': 2, '20 to 49': 3, '50 or more': 3}
    UNIT_VARS = [(k, UNITS[leaf(k)]) for k in vars_where('B25032', lambda l: len(l) == 4 and l[-1] in UNITS)]
    def band(year_label):
        y = int(year_label.split()[1]) if year_label.split()[1].isdigit() else 0   # "Built 1939 or earlier" -> 1939
        return 0 if y <= 1939 else 1 if y < 1980 else 2 if y < 2000 else 3
    BUILT_VARS = [(k, band(leaf(k))) for k in vars_where('B25036', lambda l: len(l) == 4 and l[-1].startswith('Built '))]
    LANG_VARS = vars_where('C16001', lambda l: len(l) == 3 and (l[-1].endswith(':') or l[-1] == 'Speak only English'))
    LANG_NAME = {'Speak only English': 'English only', 'French, Haitian, or Cajun': 'French or Haitian Creole',
                 'German or other West Germanic languages': 'German or other West Germanic',
                 'Russian, Polish, or other Slavic languages': 'Polish, Russian or other Slavic',
                 'Other Indo-European languages': 'Other Indo-European (e.g. Hindi, Urdu)',
                 'Other Asian and Pacific Island languages': 'Other Asian or Pacific Island',
                 'Chinese (incl. Mandarin, Cantonese)': 'Chinese', 'Tagalog (incl. Filipino)': 'Tagalog (Filipino)'}
    # Ages: B01001's age brackets (men and women alike), by the first age in the label ("Under 5" is 0).
    def age0(lab):
        w = lab.split()
        return 0 if w[0] == 'Under' else int(w[0])
    AGE_BAND = lambda a: 0 if a < 15 else 1 if a < 25 else 2 if a < 45 else 3 if a < 65 else 4
    AGE_VARS = [(k, AGE_BAND(age0(leaf(k)))) for k in vars_where('B01001', lambda l: len(l) == 4)]
    # Recent immigrants: the foreign-born who entered the US in B05005's latest period ("Entered 2010 or later").
    ENTRY = {k: LAB[k][2].rstrip(':') for k in vars_where('B05005', lambda l: len(l) == 4 and l[2].startswith('Entered') and l[3].startswith('Foreign-born'))}
    first_year = lambda t: next((int(w) for w in t.split() if w.isdigit()), 0)   # 'Entered before 1990' -> 1990, earlier than 2010
    RECENT_PERIOD = max(ENTRY.values(), key=first_year) if ENTRY else None
    RECENT_VARS = [k for k, t in ENTRY.items() if t == RECENT_PERIOD]
    assert len(AGE_VARS) == 46 and RECENT_VARS, (len(AGE_VARS), ENTRY)
    assert len(UNIT_VARS) == 16 and len(BUILT_VARS) == 20 and len(LANG_VARS) >= 10, (len(UNIT_VARS), len(BUILT_VARS), len(LANG_VARS))

    def shares(s, pairs, n):
        tot = sum(s[k] for k, _ in pairs)
        if not tot: return None
        out = [0] * n
        for k, i in pairs: out[i] += s[k]
        return [round(100 * x / tot) for x in out]


v = lambda s, tbl, n: s.get(f'{tbl}_E{n:03d}', 0)


def figures(s, m, name):
    hh = v(s, 'B25003', 1)
    com = v(s, 'B08301', 1) - v(s, 'B08301', 21)
    value = median([v(s, 'B25075', i) for i in range(2, 28)], VALUE)
    rent = median([v(s, 'B25063', i) for i in range(3, 27)], RENT)
    d = {
        'name': name,
        'value': int(round(value, -4)) if value else None, 'rent': int(round(rent, -1)) if rent else None,
        'renterPct': round(100 * v(s, 'B25003', 3) / hh) if hh else None,
        'carPct': round(100 * v(s, 'B08301', 2) / com) if com else None,
        'transitPct': round(100 * v(s, 'B08301', 10) / com) if com else None,
        'walkBikePct': round(100 * (v(s, 'B08301', 18) + v(s, 'B08301', 19)) / com) if com else None,
    }
    # Shares of all occupied homes (the denominator includes mobile homes and boats, as Toronto's includes movable dwellings).
    tot = v(m, 'B25032', 1)
    d['homes'] = [round(100 * x / tot) for x in [sum(m[k] for k, i in UNIT_VARS if i == j) for j in range(4)]] if tot else None
    d['built'] = shares(m, BUILT_VARS, 4)
    tot = v(m, 'C16001', 1)
    if tot:
        names = [(LANG_NAME.get(leaf(k), leaf(k)), m[k]) for k in LANG_VARS if m[k] and not leaf(k).startswith('Other and unspecified')]
        d['lang'] = [[nm, round(100 * x / tot)] for nm, x in sorted(names, key=lambda a: -a[1])[:5]]
    d['ages'] = shares(m, AGE_VARS, 5)
    tot = v(m, 'B01001', 1)   # everyone (B05005's own total is only people born outside the US)
    d['pop'], d['hh'] = tot or None, hh or None   # weights for citywide figures (Compare page); card never shows them
    d['recent'] = round(100 * sum(m[k] for k in RECENT_VARS) / tot) if tot else None
    d['recentSince'] = RECENT_PERIOD.replace('Entered ', '')   # "2010 or later"
    return d
