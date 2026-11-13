#!/usr/bin/env bash
# Rebuild docs/melbourne/data/* and docs/melbourne/index.html from the inputs in cities/melbourne/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/melbourne/data
python3 build.py
python3 landmarks.py
python3 profiles.py             # after build.py: the suburb lens and Living here (2021 Census, SA1s)
OUT=../../docs/melbourne/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=40 keep-shapes -filter-slivers min-area=20000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify sides 4; simplify suburbs 4
[ -f raw/representatives/districts.geojson ] && python3 representatives.py   # state districts, federal divisions, who holds them
simplify state 4; simplify federal 4
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=5 -o $OUT/$f.geojson precision=0.00001 -quiet; done
python3 collectors.py          # after streets and base are simplified: the tier below the main streets
npx mapshaper -i tmp/collectors.geojson -simplify interval=5 -o $OUT/collectors.geojson precision=0.00001 -quiet
npx mapshaper -i tmp/region_highways.geojson -simplify interval=20 -o $OUT/region_highways.geojson precision=0.00001 -quiet
python3 transit.py             # after base is simplified: trains, trams, V/Line
for f in train_lines tram_lines; do npx mapshaper -i tmp/$f.geojson -simplify interval=4 -o $OUT/$f.geojson precision=0.00001 -quiet; done
for f in vline_lines vline_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=20 -o $OUT/$f.geojson precision=0.00001 -quiet; done
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=60 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
python3 ../../engine/regions.py melbourne
if [ -f raw/parks/osm_parks.json ]; then python3 parks.py; fi   # Parks, Sports & rec
if [ -f raw/more/osm_city.json ]; then python3 places_more.py; fi   # ERs, campuses, schools, community, worship, bikes, development
python3 ../../engine/skyscrapers.py melbourne
if [ -f raw/addresses.json ]; then python3 addresses.py; fi   # the card's Address row
if [ -f raw/more/heritage_places.json ]; then python3 heritage.py; fi   # Heritage buildings
python3 parking.py   # public car parks
if [ -f raw/more/osm_construction.json ]; then python3 construction.py; fi   # Suburban Rail Loop East, from OSM
python3 nearby.py   # the card's Nearby section, from the layers above
if [ -f raw/voting/sites.json ]; then python3 voting.py; fi   # where to vote, until November 28
python3 ../../engine/assemble.py melbourne
python3 ../../engine/profiles/build.py melbourne   # fact sheets, from the published layers
python3 ../../engine/routes/build.py melbourne     # Routes from here (needs raw/surface/rapid_*.json and sched.json)
python3 ../../engine/venues.py melbourne           # Venues pages (events and drive times come from the nightly job)
echo "Done. Preview: cd docs && python3 -m http.server 8000"
