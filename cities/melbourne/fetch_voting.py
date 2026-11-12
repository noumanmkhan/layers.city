"""Where Victorians vote in the state election of November 28, 2026 -> cities/melbourne/raw/voting/. Runs in GitHub
Actions (fetch-melbourne-voting.yml); the sandbox can't reach the VEC.

- venues.xlsx: the VEC's venues spreadsheet ("location details and voting estimates" for early, election day, mobile,
  low-sensory and interstate centres), linked from vec.vic.gov.au/voting/2026-state-election/voting-locations.
  CC BY 4.0, "© Victorian Electoral Commission". The link is read from that page each run, since the VEC replaces
  the file when venues change; the address below is the one it had on November 13.
- venues.json: every sheet of it as rows (header row first), so the build and a reader of the diff needn't open Excel."""
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import get

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw', 'voting'); os.makedirs(RAW, exist_ok=True)
PAGE = 'https://www.vec.vic.gov.au/voting/2026-state-election/voting-locations'
KNOWN = 'https://www.vec.vic.gov.au/-/media/19326aa361284a49a69b08194421da96.xlsx'


def link():
    try:
        html = get(PAGE, tries=3).decode('utf-8', 'replace')
        hits = re.findall(r'href="([^"]+\.xlsx[^"]*)"', html)
        if hits:
            u = hits[0].replace('&amp;', '&')
            return u if u.startswith('http') else 'https://www.vec.vic.gov.au' + u
        print('  no .xlsx link on the page; using the known address')
    except Exception as e: print('  page:', e)
    return KNOWN


def main():
    url = link(); print('  venues', url)
    b = get(url, tries=3)
    open(os.path.join(RAW, 'venues.xlsx'), 'wb').write(b)
    try: import openpyxl
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', 'openpyxl']); import openpyxl
    wb = openpyxl.load_workbook(os.path.join(RAW, 'venues.xlsx'), read_only=True, data_only=True)
    out = {'source': url, 'sheets': {}}
    for ws in wb.worksheets:
        rows = [[(c.isoformat() if hasattr(c, 'isoformat') else c) for c in r] for r in ws.iter_rows(values_only=True)]
        rows = [r for r in rows if any(v not in (None, '') for v in r)]
        out['sheets'][ws.title] = rows
        print(f'  sheet {ws.title!r}: {len(rows)} rows; header {rows[0] if rows else None}')
    json.dump(out, open(os.path.join(RAW, 'venues.json'), 'w'), ensure_ascii=False, indent=0, default=str)


if __name__ == '__main__': main()
