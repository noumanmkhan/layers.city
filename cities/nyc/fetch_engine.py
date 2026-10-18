"""Run the shared engine fetchers for New York City in one Actions job (fetch-nyc.yml), while NYC is built on dev:
the shared workflows (fetch-surface.yml, fetch-bikes.yml, fetch-canopy.yml, fetch-heritage-buildings.yml,
fetch-construction.yml) list their cities and commit to main, so NYC joins them when it's released.
Each fetcher reads its cities/nyc/<name>.json and writes under cities/nyc/raw/; one failing doesn't stop the rest."""
import os, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
failed = []
for script in ['fetch_surface.py', 'fetch_bikes.py', 'fetch_bikeshare.py', 'fetch_canopy.py', 'fetch_heritage_buildings.py', 'fetch_construction.py']:
    print('==', script, flush=True)
    if subprocess.run([sys.executable, '-u', os.path.join(ROOT, 'engine', script), 'nyc'], cwd=ROOT).returncode: failed.append(script)
print('FAILED:', failed or 'none')
