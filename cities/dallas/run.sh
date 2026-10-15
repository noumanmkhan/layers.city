#!/usr/bin/env bash
# Rebuild docs/dallas/data/* and docs/dallas/index.html from the inputs in cities/dallas/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper + leaflet).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/dallas/data
python3 build.py
python3 profiles.py
OUT=../../docs/dallas/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=60 keep-shapes -filter-slivers min-area=40000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify sides 10; simplify zips 10; simplify council 10; simplify tx_house 10; simplify tx_senate 10; simplify us_house 10
npx mapshaper -i tmp/counties.geojson -simplify interval=40 keep-shapes -o $OUT/counties.geojson precision=0.00005 format=geojson -quiet
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=6 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/region_highways.geojson -simplify interval=20 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in rail_lines rail_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=20 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/dart_lines.geojson -simplify interval=6 -o $OUT/dart_lines.geojson precision=0.00001 -quiet
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=60 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
python3 ../../engine/regions.py dallas
[ -f raw/voting/centers.json ] && python3 voting.py   # where to vote, until the polls close
python3 ../../engine/facts.py dallas   # after profiles and the simplified units: what makes each stand out
python3 ../../engine/assemble.py dallas
echo "Done. Preview: cd docs && python3 -m http.server 8000"
