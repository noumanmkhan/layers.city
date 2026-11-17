#!/usr/bin/env bash
# Rebuild docs/dubai/data/* and docs/dubai/index.html from the inputs in cities/dubai/raw/ (see SOURCES.md).
# Needs: python3 with shapely (PY=... to pick one); node (npm install at the repo root brings mapshaper).
# raw/ is refreshed by hand: extract_osm.py (OpenStreetMap) and the Data Dubai downloads, which answer only UAE addresses.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/dubai/data
$PY build.py
$PY landmarks.py
OUT=../../docs/dubai/data
npx mapshaper -i tmp/base.geojson -simplify interval=40 keep-shapes -filter-slivers min-area=20000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
for f in sides communities; do npx mapshaper -i tmp/$f.geojson -simplify interval=12 keep-shapes -o $OUT/$f.geojson precision=0.00001 format=geojson -quiet; done
for f in highways streets collectors; do npx mapshaper -i tmp/$f.geojson -simplify interval=6 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/region_highways.geojson -simplify interval=25 -o $OUT/region_highways.geojson precision=0.00001 -quiet
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=80 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
$PY ../../engine/regions.py dubai
$PY ../../engine/assemble.py dubai
echo "Done. Preview: cd docs && python3 -m http.server 8000"
