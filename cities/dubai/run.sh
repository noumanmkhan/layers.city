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
for f in sides communities route_areas; do npx mapshaper -i tmp/$f.geojson -simplify interval=12 keep-shapes -o $OUT/$f.geojson precision=0.00001 format=geojson -quiet; done
for f in highways streets collectors; do npx mapshaper -i tmp/$f.geojson -simplify interval=6 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/region_highways.geojson -simplify interval=25 -o $OUT/region_highways.geojson precision=0.00001 -quiet
$PY ../../engine/surface.py dubai      # buses and the tram (raw/surface/: engine/fetch_surface.py dubai, from the GTFS zip)
$PY transit.py                         # Metro, tram, abras and ferries, Etihad Rail, the Palm Monorail
for f in metro_lines tram_lines ferry_lines ferry_lines_inner monorail_lines; do npx mapshaper -i tmp/$f.geojson -simplify interval=4 -o $OUT/$f.geojson precision=0.00001 -quiet; done
for f in rail_lines rail_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=15 -o $OUT/$f.geojson precision=0.00001 -quiet; done
$PY ../../engine/construction.py dubai  # the Blue Line, from raw/construction/osm.json (transit.py)
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=80 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
$PY ../../engine/regions.py dubai
$PY places_more.py                    # parks and beaches, hospitals, campuses, schools, libraries, worship, sports, heritage
npx mapshaper -i tmp/parks.geojson -simplify interval=6 keep-shapes -o $OUT/parks.geojson precision=0.00001 format=geojson -quiet
$PY nearby.py                         # the card's Nearby section, from the layers above
$PY ../../engine/skyscrapers.py dubai   # 200 m and taller (raw/skyscrapers/: engine/fetch_skyscrapers.py dubai)
$PY ../../engine/assemble.py dubai
$PY ../../engine/routes/build.py dubai     # Routes from here (raw/surface/rapid_*.json, sched.json)
echo "Done. Preview: cd docs && python3 -m http.server 8000"
