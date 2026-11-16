#!/usr/bin/env bash
# Building outlines for a city's map as one PMTiles file, uploaded to the R2 bucket the Worker serves /tiles/ from.
#   engine/tiles/buildings.sh <city> <west> <south> <east> <north>
# Source: Overture Maps Foundation's buildings theme (ODbL; mostly OpenStreetMap and Microsoft/Esri footprints), read
# straight from its public S3 bucket with DuckDB, newest release. Kept: the outline, and height (m) and floors where
# known (h, f), for a flat fill now and 3D later. Tiles: MapLibre zoom 13 to 15 (the map shows buildings from its
# zoom 15, which is MapLibre's 14), overzoomed beyond. Run in GitHub Actions (build-tiles.yml): needs duckdb (pip),
# tippecanoe (built from source by the workflow), the AWS CLI (listing releases) and Wrangler with
# CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID (the token needs Workers R2 Storage: Write).
set -euo pipefail
CITY=$1; W=$2; S=$3; E=$4; N=$5
WORK=${WORK:-/tmp/tiles-$CITY}; mkdir -p "$WORK"
REL=$(aws s3 ls --no-sign-request s3://overturemaps-us-west-2/release/ | awk '{print $2}' | tr -d / | sort | tail -1)
echo "Overture release: $REL"
python3 - "$REL" "$W" "$S" "$E" "$N" "$WORK/buildings.geojsonl" <<'PY'
import sys, duckdb, time
rel, w, s, e, n, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6]
t = time.time()
con = duckdb.connect()
for q in ("INSTALL spatial", "LOAD spatial", "INSTALL httpfs", "LOAD httpfs", "SET s3_region='us-west-2'", "SET threads=4", "SET geometry_always_xy = true"):
    con.execute(q)
con.execute(f"""
COPY (
  SELECT round(height, 1) AS h, num_floors AS f, geometry
  FROM read_parquet('s3://overturemaps-us-west-2/release/{rel}/theme=buildings/type=building/*', hive_partitioning=1)
  WHERE bbox.xmin < {e} AND bbox.xmax > {w} AND bbox.ymin < {n} AND bbox.ymax > {s}
) TO '{out}' WITH (FORMAT GDAL, DRIVER 'GeoJSONSeq')""")
print('buildings written in', round(time.time() - t), 's', flush=True)
PY
wc -l "$WORK/buildings.geojsonl"; du -h "$WORK/buildings.geojsonl"
tippecanoe -o "$WORK/buildings.pmtiles" --force -l buildings -Z13 -z15 \
  --drop-smallest-as-needed --maximum-tile-bytes=1500000 --simplification=2 --hilbert --read-parallel \
  --attribution='© OpenStreetMap contributors, Overture Maps Foundation' "$WORK/buildings.geojsonl"
du -h "$WORK/buildings.pmtiles"
# Wrangler uploads at most 300 MiB. A big region (New York's tri-state) goes over: drop zoom 13, which the map
# doesn't draw (it shows buildings from MapLibre zoom 14), and build again.
if [ "$(stat -c %s "$WORK/buildings.pmtiles")" -gt 304087040 ]; then
  echo "over 290 MiB: rebuilding from zoom 14"
  tippecanoe -o "$WORK/buildings.pmtiles" --force -l buildings -Z14 -z15 \
    --drop-smallest-as-needed --maximum-tile-bytes=1500000 --simplification=2 --hilbert --read-parallel \
    --attribution='© OpenStreetMap contributors, Overture Maps Foundation' "$WORK/buildings.geojsonl"
  du -h "$WORK/buildings.pmtiles"
fi
npx --yes wrangler@4 r2 object put "layers-city-tiles/$CITY/buildings.pmtiles" --file "$WORK/buildings.pmtiles" \
  --content-type application/octet-stream --remote
echo "uploaded $CITY/buildings.pmtiles ($(date -u +%F), Overture $REL)"
