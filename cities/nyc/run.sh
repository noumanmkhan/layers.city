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
python3 collectors.py          # after streets and base are simplified: the tier below the main streets (fetch_streets.py)
npx mapshaper -i tmp/collectors.geojson -simplify interval=5 -o $OUT/collectors.geojson precision=0.00001 -quiet
npx mapshaper -i tmp/region_highways.geojson -simplify interval=20 -o $OUT/region_highways.geojson precision=0.00001 -quiet
for f in rail_lines rail_lines_inner; do npx mapshaper -i tmp/$f.geojson -simplify interval=15 -o $OUT/$f.geojson precision=0.00001 -quiet; done
npx mapshaper -i tmp/subway_lines.geojson -simplify interval=4 -o $OUT/subway_lines.geojson precision=0.00001 -quiet
cp tmp/region_areas.geojson tmp/region_areas.raw.geojson
npx mapshaper -i tmp/region_areas.raw.geojson -simplify interval=60 keep-shapes -o tmp/region_areas.geojson precision=0.00005 format=geojson -quiet
python3 ../../engine/regions.py nyc
[ -f raw/canopy/canopy.json ] && python3 ../../engine/canopy.py nyc   # after profiles: tree canopy per district
[ -f raw/drive_times.json ] && python3 ../../engine/drive.py build nyc   # after base is simplified: drive times to Penn Station
[ -f raw/surface/routes.json ] && python3 ../../engine/surface.py nyc    # MTA buses
[ -f raw/bikes.geojson ] && python3 ../../engine/bikes.py nyc   # NYC DOT bike routes
[ -f raw/bikeshare.json ] && python3 ../../engine/bikeshare.py nyc   # Citi Bike stations
[ -f raw/heritage_buildings.json ] && python3 ../../engine/heritage_buildings.py nyc   # LPC individual landmarks
[ -f raw/construction/osm.json ] && python3 ../../engine/construction.py nyc   # after streets: lines being built
python3 ../../engine/addresses.py nyc   # after streets: Fifth Avenue, East and West (Manhattan)
[ -f raw/ferries/nycferry.zip ] && python3 ferries.py   # NYC Ferry and the Staten Island Ferry
python3 crz.py   # after build.py's streets_ew: the Congestion Relief Zone, Manhattan from 60th Street south
[ -f raw/places/worship_osm.json ] && python3 faith.py   # places of worship (OpenStreetMap)
[ -f raw/places/facdb.json ] && python3 places.py   # after faith: hospitals, colleges, libraries, schools, parks, sports, the card's Nearby
[ -f raw/places/evacuation_zones.geojson ] && python3 evacuation.py && npx mapshaper -i tmp/evacuation.geojson -simplify interval=20 keep-shapes -o $OUT/evacuation.geojson precision=0.0001 -quiet   # after places.py: hurricane evacuation zones and centers
[ -f raw/places/school_zones_es.geojson ] && python3 zones.py   # the card's Schools section: DOE school zones
[ -f raw/places/dsny_frequencies.geojson ] && python3 collection.py   # trash, recycling and compost days for the card
[ -d raw/representatives ] && python3 representatives.py   # after the districts above: it matches them
[ -f raw/voting/election_districts.geojson ] && python3 voting.py   # where to vote, until the polls close
[ -f ../../docs/nyc/data/cd_profiles.json ] && python3 ../../engine/facts.py nyc   # after profiles and the simplified units
python3 ../../engine/assemble.py nyc
python3 ../../engine/places.py nyc   # a static page per place for search and link previews, plus the site's sitemap.xml
echo "Done. Preview: cd docs && python3 -m http.server 8000"
