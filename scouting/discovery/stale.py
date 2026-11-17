"""List discovery places that are due for another check.

Reads every curated batch in this folder (*.json with a "places" list) and prints each place whose "checked" date
is more than MAX_DAYS old, oldest first. Exits non-zero if any place has no "checked" date (or one that isn't
YYYY-MM-DD), so a new entry can't slip in unchecked. Stale places are listed but don't fail the run.

  python3 scouting/discovery/stale.py            # all batches
  python3 scouting/discovery/stale.py FILE ...   # just these"""
import datetime, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAX_DAYS = 180


def main(paths):
    today = datetime.date.today()
    stale, missing = [], []
    for path in paths:
        places = json.load(open(path, encoding='utf-8')).get('places')
        if not isinstance(places, list): continue
        for p in places:
            where = '%s: %s' % (os.path.basename(path), p.get('name', '(no name)'))
            try:
                d = datetime.date.fromisoformat(p['checked'])
            except (KeyError, TypeError, ValueError):
                missing.append(where); continue
            age = (today - d).days
            if age > MAX_DAYS: stale.append((age, d, where))
    for age, d, where in sorted(stale, reverse=True):
        print('stale  %s  (checked %s, %d days ago)' % (where, d, age))
    for where in missing:
        print('NO CHECKED DATE  %s' % where)
    print('%d stale (over %d days), %d without a checked date' % (len(stale), MAX_DAYS, len(missing)))
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:] or sorted(glob.glob(os.path.join(HERE, '*.json')))))
