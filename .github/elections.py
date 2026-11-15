"""Which cities are inside an election window right now, from .github/elections.json. Prints them space-separated.

  python3 .github/elections.py voting    cities publishing voting places today (voting_from..day, local date) for
                                         which it is early morning (before 10:00 local) now. fetch-voting.yml runs
                                         twice a day (North American and Australian mornings), so each city is
                                         picked once a day, in its own morning.
  python3 .github/elections.py results   cities counting or proclaiming results (day+1..results_until, local date).

Used by fetch-voting.yml and fetch-representatives.yml on their scheduled runs; runs by hand or on a push pick
their cities another way."""
import datetime, json, os, sys
from zoneinfo import ZoneInfo

kind = sys.argv[1] if len(sys.argv) > 1 else ''
if kind not in ('voting', 'results'): sys.exit('usage: elections.py voting|results')
rows = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'elections.json')))['elections']
now = datetime.datetime.now(datetime.timezone.utc)
picked = []
for e in rows:
    local = now.astimezone(ZoneInfo(e['tz']))
    today = local.date().isoformat()
    if kind == 'voting':
        ok = e['voting_from'] <= today <= e['day'] and local.hour < 10
    else:
        ok = 'results_until' in e and e['day'] < today <= e['results_until']
    if ok and e['city'] not in picked: picked.append(e['city'])
print(' '.join(picked))
