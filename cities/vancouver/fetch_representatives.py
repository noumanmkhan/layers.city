"""Fetch Vancouver's current elected representatives into raw/representatives/. Run weekly from GitHub Actions
(fetch-vancouver-representatives.yml); the sandbox can't reach these sites.

  ourcommons.xml   House of Commons, current members (ourcommons.ca/Members/en/search/XML), as Toronto's.

Not yet: the mayor and councillors (Vancouver elects them at large on October 17, 2026) and MLAs (BC votes on
October 24, 2026). They are wired once the results are in, from the City's and the Legislature's own pages.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F

OUT = os.path.join(HERE, 'raw', 'representatives'); os.makedirs(OUT, exist_ok=True)
try:
    data = F.get('https://www.ourcommons.ca/Members/en/search/XML')
    open(os.path.join(OUT, 'ourcommons.xml'), 'wb').write(data)
except RuntimeError as e:   # blocked or down: keep the committed copy (MPs change only at by-elections)
    if not os.path.exists(os.path.join(OUT, 'ourcommons.xml')): raise
    print('  ! ourcommons.xml not refreshed; keeping the last copy:', e)
print('ourcommons.xml', os.path.getsize(os.path.join(OUT, 'ourcommons.xml')) // 1000, 'KB')
