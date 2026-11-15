"""2021 Census General Community Profile for Greater Melbourne's suburbs (ABS Suburbs and Localities, SALs), for the
suburb lens and Living here beyond the City -> raw/census_sal.json, the same tables and columns as
raw/census_sa1.json (fetch.py), one row per SAL in raw/sal.geojson. Runs in GitHub Actions (fetch-melbourne.yml runs it
when a push changes it); abs.gov.au refuses the sandbox."""
import csv, io, json, os, re, zipfile
from fetch_lib import RAW, TMP, download, save, step

# The columns fetch.py keeps for SA1s (copied: importing fetch.py would run its fetches).
CENSUS_KEEP = {
    'G01': ['Tot_P_P', 'Age_0_4_yr_P', 'Age_5_14_yr_P', 'Age_15_19_yr_P', 'Age_20_24_yr_P', 'Age_25_34_yr_P', 'Age_35_44_yr_P', 'Age_45_54_yr_P',
            'Age_55_64_yr_P', 'Age_65_74_yr_P', 'Age_75_84_yr_P', 'Age_85ov_P', 'Birthplace_Elsewhere_P', 'Count_psns_occ_priv_dwgs_P'],
    'G02': None, 'G36': None,
    'G37': ['O_OR_Total', 'O_MTG_Total', 'R_Tot_Total', 'R_ST_h_auth_Total', 'R_Com_Hp_Total', 'Oth_ten_type_Total', 'Ten_type_NS_Total', 'Total_Total'],
    'G10C': ['Tot_2016', 'Tot_2017', 'Tot_2018', 'Tot_2019', 'Tot_2020', 'Tot_2021', 'Tot_Tot'],
}


def census_sal():
    want = {'SAL' + str(f['properties']['sal_code_2021']) for f in json.load(open(os.path.join(RAW, 'sal.geojson')))['features']}
    print('  SALs in the box:', len(want))
    z = zipfile.ZipFile(download('https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_SAL_for_VIC_short-header.zip',
                                 os.path.join(TMP, 'gcp_sal.zip')))
    tables = {}
    for n in z.namelist():
        m = re.search(r'2021Census_(G\d+[A-Z]?)_VIC_SAL\.csv$', n)
        if m and (m.group(1) in CENSUS_KEEP or m.group(1).startswith('G13')):
            rows = list(csv.reader(io.TextIOWrapper(z.open(n), 'utf-8-sig')))
            tables[m.group(1)] = (rows[0], [r for r in rows[1:] if r[0] in want])
    print('  tables:', sorted(tables), '· rows', {k: len(v[1]) for k, v in tables.items()})
    out = {}
    for t, cols in CENSUS_KEEP.items():
        h, body = tables[t]
        idx = [0] + ([h.index(c) for c in cols] if cols else list(range(1, len(h))))
        out[t] = {'cols': [h[i] for i in idx], 'rows': [[r[i] for i in idx] for r in body]}
    lc, rows = ['P_Tot_Tot'], {}
    for t in sorted(k for k in tables if k.startswith('G13')):
        h, body = tables[t]
        lc += [c for c in h if re.fullmatch(r'(PSEO|POL_.+)_Tot', c) and '_UOLSE_' not in c and c not in lc]
        for r in body: rows.setdefault(r[0], {}).update(zip(h, r))
    out['G13'] = {'cols': ['SAL_CODE_2021'] + lc, 'rows': [[k] + [d.get(c, '0') for c in lc] for k, d in rows.items()]}
    out['_about'] = 'ABS 2021 Census GCP DataPack, SALs (suburbs and localities) in Greater Melbourne\'s box, trimmed like census_sa1.json.'
    save('census_sal.json', out)
step('census by suburb', census_sal)
