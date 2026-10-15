#!/usr/bin/env bash
# Rebuild docs/vancouver/data/* and docs/vancouver/index.html from the inputs in cities/vancouver/raw/.
# Needs: python3 with shapely; node (npm install at the repo root brings mapshaper + leaflet).
set -euo pipefail
cd "$(dirname "$0")"
[ -d ../../node_modules ] || (cd ../.. && npm install --silent)
mkdir -p tmp ../../docs/vancouver/data
python3 build.py
python3 landmarks.py
python3 profiles.py
OUT=../../docs/vancouver/data
simplify () { npx mapshaper -i "tmp/$1.geojson" -simplify interval="$2" keep-shapes -o "$OUT/$1.geojson" precision=0.00001 format=geojson -quiet; }
npx mapshaper -i tmp/base.geojson -simplify interval=40 keep-shapes -filter-slivers min-area=20000m2 -o $OUT/base.geojson precision=0.00005 format=geojson -quiet
simplify sides 8; simplify local_areas 8
python3 layers.py              # heritage districts, BIAs, provincial and federal ridings (tmp/), voting places (docs)
simplify heritage 3; simplify bia 4; simplify provincial 8; simplify federal 8
[ -f raw/canopy/canopy.json ] && python3 ../../engine/canopy.py vancouver   # after profiles: tree canopy per local area
python3 ../../engine/skyscrapers.py vancouver   # towers 100 m+ from raw/skyscrapers/wiki.json
python3 institutions.py        # universities, colleges, hospitals: points, written straight to docs
python3 french_schools.py      # CSF and VSB immersion schools
python3 faith.py               # places of worship (raw/faith/worship_osm.json)
[ -f raw/heritage_buildings.json ] && python3 ../../engine/heritage_buildings.py vancouver
for f in highways streets; do npx mapshaper -i tmp/$f.geojson -simplify interval=6 -o $OUT/$f.geojson precision=0.00001 -quiet; done
python3 collectors.py          # after streets and base are simplified: the tier below the main streets
npx mapshaper -i tmp/collectors.geojson -simplify interval=6 -o $OUT/collectors.geojson precision=0.00001 -quiet
npx mapshaper -i tmp/region_highways.geojson -simplify interval=15 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in wce_lines wce_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=30 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/skytrain_lines.geojson -simplify interval=5 -o $OUT/skytrain_lines.geojson precision=0.00001 -quiet
[ -f raw/public_streets.geojson ] && python3 address_prep.py && python3 ../../engine/addresses.py vancouver   # after streets: how addresses work
python3 nearby.py              # after institutions and faith: the card's Nearby points
[ -f raw/representatives/ourcommons.xml ] && python3 representatives.py   # after the federal ridings
[ -f raw/drive_times.json ] && python3 ../../engine/drive.py build vancouver   # after base is simplified: adds drive times to it
[ -f raw/bikes.geojson ] && python3 ../../engine/bikes.py vancouver           # Bikeways (fetch-bikes.yml)
[ -f raw/bikeshare.json ] && python3 ../../engine/bikeshare.py vancouver      # Mobi stations (fetch-bikes.yml)
[ -d raw/changes ] && python3 ../../engine/changes.py vancouver               # issued permits (fetch-changes.yml)
[ -f raw/construction/osm.json ] && python3 ../../engine/construction.py vancouver   # after streets: Broadway Subway, Surrey Langley SkyTrain
python3 ../../engine/facts.py vancouver   # after profiles and the simplified local areas: what makes each stand out
python3 ../../engine/assemble.py vancouver
echo "Done. Preview: cd docs && python3 -m http.server 8000"
