#!/usr/bin/env bash
# Rebuild docs/sf/data/* and docs/sf/index.html from the inputs in cities/sf/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper + leaflet).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/sf/data
python3 build.py
python3 landmarks.py
[ -f raw/acs_tracts.json ] && python3 profiles.py   # after build.py: the neighbourhood lens (fetch_acs.py)
[ -f raw/canopy/canopy.json ] && python3 ../../engine/canopy.py sf   # after profiles: tree canopy per neighborhood
OUT=../../docs/sf/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=50 keep-shapes -filter-slivers min-area=20000m2 -filter "!this.isNull" -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify sides 6; simplify neighbourhoods 5; simplify sffind 4; simplify supervisors 6; simplify assembly 6; simplify senate 8; simplify congress 8
simplify heritage 3; simplify cultural 4
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=5 -o $OUT/$f.geojson precision=0.00001 -quiet; done
python3 collectors.py          # after streets and base are simplified: the tier below the main streets (fetch_streets.py)
npx mapshaper -i tmp/collectors.geojson -simplify interval=5 -o $OUT/collectors.geojson precision=0.00001 -quiet
npx mapshaper -i tmp/region_highways.geojson -simplify interval=20 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in rail_lines rail_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=15 -o $OUT/$f.geojson precision=0.00001 -quiet; done
for f in bart_lines muni_lines; do npx mapshaper -i tmp/$f.geojson -simplify interval=4 -o $OUT/$f.geojson precision=0.00001 -quiet; done
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=60 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
[ -f raw/places/osm_worship.json ] && python3 faith.py   # places of worship (fetch_places.py)
[ -f raw/places/parks.geojson ] && python3 places.py   # parks, sports, schools, libraries, hospitals, colleges, Nearby
[ -f raw/tech_geocoded.json ] && python3 tech.py   # tech headquarters (fetch_tech.py)
[ -f raw/extras/tsunami.geojson ] && python3 extras.py   # hazard zones, soft-story buildings, ferries (fetch_extras.py)
[ -f raw/parking/garages.json ] && python3 parking.py   # garages and lots, permit areas, EV chargers (fetch_parking.py)
[ -f raw/sweeping.json ] && python3 sweeping.py        # street sweeping squares for the card (fetch_sweeping.py)
[ -f raw/addresses.json ] && python3 addresses.py      # each street's numbering, for the card's Address row (fetch_addresses.py)
[ -f raw/representatives/ca.csv ] && python3 representatives.py   # current officeholders (fetch_representatives.py)
python3 ../../engine/badges.py sf   # a drawing for a few neighborhoods (cities/sf/badges/)
python3 ../../engine/regions.py sf
[ -f raw/drive_times.json ] && python3 ../../engine/drive.py build sf   # after base is simplified: drive times to Montgomery St
[ -f raw/skyscrapers/wiki.json ] && python3 ../../engine/skyscrapers.py sf   # towers 150 m+ (fetch-skyscrapers.yml)
[ -f raw/heritage_buildings.json ] && python3 ../../engine/heritage_buildings.py sf   # Article 10 landmarks (fetch-heritage-buildings.yml)
python3 ../../engine/assemble.py sf
echo "Done. Preview: cd docs && python3 -m http.server 8000"
