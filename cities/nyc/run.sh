#!/usr/bin/env bash
# Rebuild docs/nyc/data/* and docs/nyc/index.html from the inputs in cities/nyc/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper + leaflet).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/nyc/data
python3 build.py
python3 landmarks.py
[ -f raw/acs_tracts.json ] && python3 profiles.py
[ -f raw/skyscrapers/wiki.json ] && python3 ../../engine/skyscrapers.py nyc   # towers 650 ft+ (fetch-skyscrapers.yml)
OUT=../../docs/nyc/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=60 keep-shapes -filter-slivers min-area=20000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify boroughs 8; simplify districts 8; simplify ntas 6; simplify council 8; simplify assembly 8; simplify senate 10; simplify congress 10
simplify school 8; simplify heritage 3; simplify bids 3
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=5 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/region_highways.geojson -simplify interval=20 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in rail_lines rail_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=15 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/subway_lines.geojson -simplify interval=4 -o $OUT/subway_lines.geojson precision=0.00001 -quiet
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=60 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
python3 ../../engine/regions.py nyc
[ -d raw/representatives ] && python3 representatives.py   # after the districts above: it matches them
[ -f raw/voting/election_districts.geojson ] && python3 voting.py   # where to vote, until the polls close
[ -f ../../docs/nyc/data/cd_profiles.json ] && python3 ../../engine/facts.py nyc   # after profiles and the simplified units
python3 ../../engine/assemble.py nyc
echo "Done. Preview: cd docs && python3 -m http.server 8000"
