"""Daily check that the site's live data is still updating (run by .github/workflows/check-feeds.yml).

Two kinds of check:
  1. Files: each live file's own date ("today", "asof", "updated", a schedule feed's last day) against how
     often its job is meant to refresh it.
  2. Jobs: the latest run of every scheduled fetch workflow; a failed, cancelled or timed-out run is reported.

Output: a Markdown report on stdout and, with --json, the list of problems. check-feeds.yml turns that into one
GitHub issue (opened when something is stale, updated when the list changes, closed when all is clear), so the
repo owner gets GitHub's notification emails.

Usage: python3 engine/health.py [--today YYYY-MM-DD] [--no-runs] [--json out.json]
The workflow check needs the gh CLI with GH_TOKEN (Actions provides it); --no-runs skips it for local tests."""
import argparse, datetime as dt, glob, json, os, subprocess, sys
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
ap = argparse.ArgumentParser()
ap.add_argument('--today'); ap.add_argument('--no-runs', action='store_true'); ap.add_argument('--json')
args = ap.parse_args()
# Dates in the files are local to the cities; New York's date is close enough for all of them.
TODAY = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(ZoneInfo('America/New_York')).date()

def load(p):
    try: return json.load(open(os.path.join(ROOT, p)))
    except (OSError, ValueError): return None
def day(s):
    try: return dt.date.fromisoformat(str(s)[:10])
    except ValueError: return None

problems, ok = [], []
def check(key, what, date, max_days, fix):
    """A file date older than max_days is a problem. key identifies the problem across runs."""
    if date is None:
        problems.append((key, f'**{what}**: no date in the file. {fix}')); return
    age = (TODAY - date).days
    if age > max_days: problems.append((key, f'**{what}**: last updated {date} ({age} days ago; expected at least every {max_days} day{'s' if max_days > 1 else ''}). {fix}'))
    else: ok.append(f'{what}: {date}')

CITIES = sorted(c for c in os.listdir(os.path.join(ROOT, 'cities')) if os.path.isfile(os.path.join(ROOT, 'cities', c, 'city.json')))
for c in CITIES:
    C = c.capitalize()
    # Daily: transit construction closures (fetch-closures.yml). A day's grace, since GitHub starts scheduled runs hours late.
    d = load(f'docs/{c}/data/closures.geojson')
    if d: check(f'closures-{c}', f'{C} road closures', day(d.get('today') or d.get('asof')), 1, 'Check the "Fetch transit closures" workflow.')
    # Weekly: What's changing (fetch-changes.yml, Tuesdays).
    d = load(f'docs/{c}/data/changes.geojson')
    if d: check(f'changes-{c}', f"{C} What's changing", day(d.get('asof')), 9, 'Check the "Fetch what\'s changing" workflow.')
    # Representatives aren't checked by date: "updated" only moves when a name changes. Their jobs' runs are checked below.
    # Schedule feeds: the job only commits when an agency publishes a new feed, so check the feed's last day instead.
    for p in sorted(glob.glob(os.path.join(ROOT, 'cities', c, 'raw', 'surface', '**', 'routes.json'), recursive=True)):
        m = load(p) or {}
        name = 'GO bus' if os.sep + 'go' + os.sep in p else 'transit'
        end = day((m.get('feed') or [None, None])[1])
        key = f'feed-{c}-{"go" if name == "GO bus" else "main"}'
        if end is None: continue
        left = (end - TODAY).days
        if left < 7:
            problems.append((key, f'**{C} {name} schedule feed**: the feed fetched {m.get("fetched")} ends {end} '
                                  f'({"ended " + str(-left) + " days ago" if left < 0 else str(left) + " days left"}) and no newer one has come through. '
                                  'Check the "Fetch streetcar and bus routes" workflow, or whether the agency moved its feed.'))
        else: ok.append(f'{C} {name} schedule feed: runs to {end}')
    # Yearly calendars: collection days (Toronto) and street sweeping (Chicago) must be for this year.
    for f, what, months in (('collection.geojson', 'collection calendar', range(1, 13)), ('sweeping.geojson', 'street sweeping schedule', range(4, 12))):
        d = load(f'docs/{c}/data/{f}')
        if not d or TODAY.month not in months: continue
        if d.get('year') != TODAY.year:
            # The cities publish the new year's calendar some weeks into it: only a problem from February.
            if TODAY.month >= 2: problems.append((f'{f}-{c}', f'**{C} {what}**: still the {d.get("year")} calendar. Check whether the city has published {TODAY.year}.'))
        else: ok.append(f'{C} {what}: {d.get("year")}')

# Jobs: the latest finished run of each scheduled workflow.
if not args.no_runs:
    repo = os.environ.get('GITHUB_REPOSITORY', 'noumanmkhan/city-layers')
    def gh(path):
        return json.loads(subprocess.run(['gh', 'api', path], check=True, capture_output=True, text=True).stdout)
    for wf in gh(f'repos/{repo}/actions/workflows?per_page=100')['workflows']:
        src = os.path.join(ROOT, wf['path'])
        if wf['state'] != 'active' or not os.path.exists(src) or 'schedule:' not in open(src).read(): continue
        if os.path.basename(src).startswith(('scout-', 'check-feeds')): continue
        runs = gh(f'repos/{repo}/actions/workflows/{wf["id"]}/runs?status=completed&per_page=1')['workflow_runs']
        if not runs: continue
        r = runs[0]
        if r['conclusion'] in ('failure', 'cancelled', 'timed_out', 'startup_failure'):
            problems.append((f'run-{wf["id"]}', f'**{wf["name"]}**: last run {r["conclusion"].replace("_", " ")} on {r["created_at"][:10]} ([log]({r["html_url"]})).'))
        else: ok.append(f'{wf["name"]}: last run {r["conclusion"]} {r["created_at"][:10]}')

out = [f'Checked {TODAY} by `engine/health.py`.', '']
if problems:
    out += ['### Needs a look', ''] + [f'- {t}' for _, t in problems] + ['']
out += ['<details><summary>Up to date (' + str(len(ok)) + ')</summary>', ''] + [f'- {t}' for t in ok] + ['', '</details>']
print('\n'.join(out))
if args.json: json.dump([{'key': k, 'text': t} for k, t in problems], open(args.json, 'w'), indent=1)
print(f'\n{len(problems)} problem(s)', file=sys.stderr)
