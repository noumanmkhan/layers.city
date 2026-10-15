#!/usr/bin/env bash
# Rebuild docs/dallas/data/* and docs/dallas/index.html from the inputs in cities/dallas/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper + leaflet).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/dallas/data
python3 build.py
python3 landmarks.py
python3 profiles.py
[ -f raw/canopy/canopy.json ] && python3 ../../engine/canopy.py dallas   # after profiles: tree canopy per ZIP (fetch-dallas.yml)
python3 ../../engine/skyscrapers.py dallas   # towers 150 m+ from raw/skyscrapers/wiki.json
python3 institutions.py       # universities, Dallas College, ERs: points, written straight to docs
OUT=../../docs/dallas/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=60 keep-shapes -filter-slivers min-area=40000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify sides 10; simplify zips 10; simplify council 10; simplify tx_house 20; simplify tx_senate 20; simplify us_house 20
[ -f tmp/us_house_2021.geojson ] && simplify us_house_2021 20
simplify school 10; simplify heritage 3; simplify pids 5
npx mapshaper -i tmp/counties.geojson -simplify interval=40 keep-shapes -o $OUT/counties.geojson precision=0.00005 format=geojson -quiet
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=6 -o $OUT/$f.geojson precision=0.00001 -quiet; done
python3 collectors.py          # after streets and base are simplified: the tier below the main streets
npx mapshaper -i tmp/collectors.geojson -simplify interval=6 -o $OUT/collectors.geojson precision=0.00001 -quiet
npx mapshaper -i tmp/region_highways.geojson -simplify interval=20 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in rail_lines rail_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=20 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/dart_lines.geojson -simplify interval=6 -o $OUT/dart_lines.geojson precision=0.00001 -quiet
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=60 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
python3 ../../engine/regions.py dallas
python3 nearby.py             # after sides are simplified and institutions written: the card's Nearby points
[ -d raw/representatives ] && python3 representatives.py   # after the boundaries above: it matches them
[ -f raw/city/days_of_service.geojson ] && python3 collection.py   # garbage, recycling and brush days for the card
[ -f raw/drive_times.json ] && python3 ../../engine/drive.py build dallas   # after base is simplified: adds drive times to it
[ -f raw/surface/routes.json ] && python3 ../../engine/surface.py dallas    # DART buses from its GTFS
[ -f raw/bikes.geojson ] && python3 ../../engine/bikes.py dallas   # bike lanes (fetch-bikes.yml)
[ -f raw/voting/centers.json ] && python3 voting.py   # where to vote, until the polls close
python3 ../../engine/facts.py dallas   # after profiles and the simplified units: what makes each stand out
python3 ../../engine/assemble.py dallas
echo "Done. Preview: cd docs && python3 -m http.server 8000"
