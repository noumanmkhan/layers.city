#!/usr/bin/env bash
# Rebuild docs/hyderabad/data/* and docs/hyderabad/index.html from the inputs in cities/hyderabad/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper + leaflet).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/hyderabad/data
python3 build.py
python3 landmarks.py
OUT=../../docs/hyderabad/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=60 keep-shapes -filter-slivers min-area=20000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify districts 15; simplify mandals 12; simplify pincodes 15
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=6 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/region_highways.geojson -simplify interval=25 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in rail_lines rail_lines_inner metro_lines; do npx mapshaper -i tmp/$f.geojson -simplify interval=8 -o $OUT/$f.geojson precision=0.00001 -quiet; done
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=80 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
python3 ../../engine/regions.py hyderabad
python3 ../../engine/assemble.py hyderabad
echo "Done. Preview: cd docs && python3 -m http.server 8000"
