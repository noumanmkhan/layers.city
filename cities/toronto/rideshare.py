#!/usr/bin/env python3
"""Toronto rideshare, hour by hour: build the small JSON files for the explainer page.

Source: City of Toronto Open Data, "Private Transportation Companies - Summary and Trip Data" and
"Private Transportation Companies - Vehicle Operating Data" (Transportation Services). Contains
information licensed under the Open Government Licence - Toronto.

Raw files (gitignored, as downloaded and unzipped) in cities/toronto/raw/ptc/:
  trips_2025/, trips_2026/            monthly CSVs, completed trips by pickup hour x pickup/drop-off ward
  operating_hours_2025/, _2026/       monthly CSVs, one row per vehicle x hour (no location)
  summary_stats.csv                   daily, city-wide

Outputs in cities/toronto/rideshare/ (small, committed):
  hourly.json   pickups per hour (city, Toronto, Pearson, rest of GTA) by day type
  wards.json    pickups, wait and fare per ward x hour x day type
  flows.json    top ward-to-ward flows at three moments
  supply.json   drivers logged in and how their time splits, by hour x day type (4 sample months)
  years.json    average daily trips by month since 2018
  meta.json     window, day counts, rollup share, checks, licence line

Notes
- A "service day" runs 4 a.m. to 4 a.m. (as on the downtown-weekday page), so 1 a.m. Saturday is Friday night.
- Day types: weekday (Mon-Thu), fri, sat, sun. Holidays (list below) are left out of every day type.
- pickup_hr is read as local wall-clock time (the text before the UTC offset).
- Wards: "Not included elsewhere" rows (privacy rollups of cells under 10 trips) are counted in Toronto totals
  but not given to any ward; meta.json reports their share by hour.
- Needs: pip install duckdb. Run: python3 cities/toronto/rideshare.py
"""
import json
import os

import duckdb

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw', 'ptc')
OUT = os.path.join(HERE, 'rideshare')

START, END = '2025-08-01', '2026-07-30'     # service days, inclusive (Jul 31 2026 has no 4 a.m. close yet)
SUPPLY_MONTHS = ['202510', '202601', '202604', '202607']
HOLIDAYS = ['2025-08-04', '2025-09-01', '2025-10-13', '2025-12-24', '2025-12-25', '2025-12-26', '2025-12-31',
            '2026-01-01', '2026-02-16', '2026-04-03', '2026-05-18', '2026-07-01']
MIN_TRIPS_FOR_AVG = 100     # wait/fare blanked when a ward-hour averages fewer pickups than this
LICENCE = 'Contains information licensed under the Open Government Licence – Toronto.'

con = duckdb.connect()
con.execute("SET threads=4; SET memory_limit='2GB'")

svc = """
  date_trunc('day', lt - INTERVAL 4 HOUR)::DATE AS sday,
  hour(lt) AS hr
"""
daytype = """
  CASE dayofweek(sday) WHEN 5 THEN 'fri' WHEN 6 THEN 'sat' WHEN 0 THEN 'sun' ELSE 'weekday' END AS dtype
"""
hol = ', '.join(f"DATE '{d}'" for d in HOLIDAYS)

trip_files = [os.path.join(RAW, f'trips_{y}', f'trips_{y}*.csv') for y in (2025, 2026)]
con.execute(f"""
CREATE TABLE t AS
WITH raw AS (
  SELECT *, CAST(substr(pickup_hr, 1, 19) AS TIMESTAMP) AS lt
  FROM read_csv({trip_files}, header=true, union_by_name=true,
                types={{'pickup_hr':'VARCHAR','trips_total':'BIGINT'}})
), s AS (SELECT *, {svc} FROM raw)
SELECT *, {daytype} FROM s
WHERE sday BETWEEN DATE '{START}' AND DATE '{END}' AND sday NOT IN ({hol})
""")

days = dict(con.sql("SELECT dtype, count(DISTINCT sday) FROM t GROUP BY 1").fetchall())
DT = ['weekday', 'fri', 'sat', 'sun']
ORDER = list(range(4, 24)) + list(range(0, 4))   # clock order of a service day


def by_hour(rows):
    """rows: (dtype, hr, value) -> {dtype: [24 values in 4 a.m.-first order]}"""
    out = {d: [0] * 24 for d in DT}
    for d, h, v in rows:
        out[d][ORDER.index(h)] = v
    return out


def area(where):
    rows = con.sql(f"""
      SELECT dtype, hr, sum(trips_total) FROM t WHERE {where} GROUP BY 1, 2
    """).fetchall()
    return by_hour([(d, h, round(v / days[d])) for d, h, v in rows])


hourly = {
    'hours': ORDER,
    'days': days,
    'all': area('true'),
    'toronto': area("pickup_municipality = 'Toronto'"),
    'pearson': area("pickup_municipality = 'Pearson Airport'"),
    'rest_gta': area("pickup_municipality NOT IN ('Toronto', 'Pearson Airport', 'Other Municipality')"),
}

# Wards: pickups, trip-weighted wait and fare
ward_rows = con.sql("""
  SELECT pickup_ward, dtype, hr, sum(trips_total) AS n,
         sum(waittime_avg * trips_total) / nullif(sum(CASE WHEN waittime_avg IS NOT NULL THEN trips_total END), 0) AS wait,
         sum(fare_avg * trips_total) / nullif(sum(CASE WHEN fare_avg IS NOT NULL THEN trips_total END), 0) AS fare
  FROM t WHERE pickup_municipality = 'Toronto' AND pickup_ward <> 'Not included elsewhere'
  GROUP BY 1, 2, 3
""").fetchall()
wards = {}
for w, d, h, n, wait, fare in ward_rows:
    num, name = w.split(' - ', 1)
    rec = wards.setdefault(num, {'name': name, **{k: {x: [None] * 24 for x in DT} for k in ('pickups', 'wait', 'fare')}})
    i = ORDER.index(h)
    avg = n / days[d]
    rec['pickups'][d][i] = round(avg)
    if avg >= MIN_TRIPS_FOR_AVG:
        rec['wait'][d][i] = round(wait, 1) if wait is not None else None
        rec['fare'][d][i] = round(fare, 2) if fare is not None else None

rollup = con.sql("""
  SELECT dtype, hr, sum(CASE WHEN pickup_ward = 'Not included elsewhere' THEN trips_total ELSE 0 END) / sum(trips_total)
  FROM t WHERE pickup_municipality = 'Toronto' GROUP BY 1, 2
""").fetchall()
rollup_share = by_hour([(d, h, round(v, 3)) for d, h, v in rollup])
rollup_total = con.sql("""SELECT sum(CASE WHEN pickup_ward = 'Not included elsewhere' THEN trips_total ELSE 0 END) / sum(trips_total)
                          FROM t WHERE pickup_municipality = 'Toronto'""").fetchone()[0]


# Flows at three moments: top 12 pairs (ward or outside place) per moment
def place(muni, ward):
    return ward.split(' - ', 1)[0] if muni == 'Toronto' and ward != 'Not included elsewhere' else muni


flows = {}
for key, d, h in [('weekday_8', 'weekday', 8), ('weekday_18', 'weekday', 18), ('sat_1', 'sat', 1)]:
    rows = con.sql(f"""
      SELECT pickup_municipality, pickup_ward, dropoff_municipality, dropoff_ward, sum(trips_total) n
      FROM t WHERE dtype = '{d}' AND hr = {h}
        AND pickup_ward IS DISTINCT FROM 'Not included elsewhere' AND dropoff_ward IS DISTINCT FROM 'Not included elsewhere'
        AND pickup_municipality <> 'Other Municipality' AND dropoff_municipality <> 'Other Municipality'
      GROUP BY 1, 2, 3, 4 ORDER BY n DESC LIMIT 40
    """).fetchall()
    pairs = [{'from': place(a, b), 'to': place(c, e), 'per_hour': round(n / days[d])} for a, b, c, e, n in rows]
    flows[key] = [p for p in pairs if p['from'] != p['to']][:12]
    flows[key + '_same_ward'] = [p for p in pairs if p['from'] == p['to']][:5]

# Supply: four sample months of vehicle-hours (city-wide; no location in the source)
veh_files = [os.path.join(RAW, f'operating_hours_{m[:4]}', f'operating_hours_{m}.csv') for m in SUPPLY_MONTHS]
sup = con.sql(f"""
WITH raw AS (
  SELECT CAST(substr(hr, 1, 19) AS TIMESTAMP) AS lt, vehid, reported_trip_fractions,
         time_available, time_enroute, time_waiting, time_ontrip
  FROM read_csv({veh_files}, header=true, union_by_name=true, types={{'hr':'VARCHAR'}})
), s AS (SELECT *, {svc} FROM raw), d AS (SELECT *, {daytype} FROM s WHERE sday NOT IN ({hol}))
SELECT dtype, hr, count(DISTINCT sday) AS ndays,
       count(*) FILTER (WHERE time_available + time_enroute + time_waiting + time_ontrip > 0) AS veh_hours,
       sum(reported_trip_fractions) AS trips,
       sum(time_available) AS avail, sum(time_enroute) AS enroute, sum(time_waiting) AS waiting, sum(time_ontrip) AS ontrip
FROM d GROUP BY 1, 2
""").fetchall()
supply = {'months': SUPPLY_MONTHS, 'hours': ORDER,
          **{k: {x: [None] * 24 for x in DT} for k in ('drivers', 'trips', 'idle_share', 'ontrip_share', 'trips_per_driver')}}
for d, h, nd, vh, tr, a, e, w, o in sup:
    i = ORDER.index(h)
    tot = a + e + w + o
    supply['drivers'][d][i] = round(vh / nd)
    supply['trips'][d][i] = round(tr / nd)
    supply['idle_share'][d][i] = round(a / tot, 3)
    supply['ontrip_share'][d][i] = round(o / tot, 3)
    supply['trips_per_driver'][d][i] = round(tr / vh, 2)

# Years: average daily completed trips by month, from the City's summary file
yrs = con.sql(f"""
  SELECT strftime(dt, '%Y-%m') m, round(avg(reported_trips_started)) trips, round(avg(active_vehicles)) vehicles
  FROM read_csv('{os.path.join(RAW, 'summary_stats.csv')}', header=true) GROUP BY 1 ORDER BY 1
""").fetchall()
years = [{'month': m, 'avg_daily_trips': int(t), 'avg_active_vehicles': (int(v) if v is not None else None)} for m, t, v in yrs]
annual = con.sql(f"""
  SELECT year(dt) y, sum(reported_trips_started) FROM read_csv('{os.path.join(RAW, 'summary_stats.csv')}', header=true)
  GROUP BY 1 ORDER BY 1
""").fetchall()

# Check: trip files vs the City's daily summary, per calendar day (all rows, no holiday filter)
chk = con.sql(f"""
  WITH a AS (SELECT CAST(substr(pickup_hr, 1, 10) AS DATE) d, sum(trips_total) n
             FROM read_csv({trip_files}, header=true, union_by_name=true,
                           types={{'pickup_hr':'VARCHAR','trips_total':'BIGINT'}}) GROUP BY 1),
       b AS (SELECT dt d, reported_trips_started n FROM read_csv('{os.path.join(RAW, 'summary_stats.csv')}', header=true))
  SELECT count(*), avg(a.n / b.n), min(a.n / b.n), max(a.n / b.n)
  FROM a JOIN b USING (d) WHERE d BETWEEN DATE '{START}' AND DATE '{END}'
""").fetchone()

meta = {
    'window': {'start': START, 'end': END, 'note': 'service days run 4 a.m. to 4 a.m.; holidays excluded'},
    'holidays_excluded': HOLIDAYS,
    'days_by_type': days,
    'trips_in_window': con.sql('SELECT sum(trips_total) FROM t').fetchone()[0],
    'toronto_pickups_without_ward_share': round(rollup_total, 4),
    'rollup_share_by_hour': rollup_share,
    'min_trips_for_wait_fare': MIN_TRIPS_FOR_AVG,
    'annual_trips': {int(y): int(n) for y, n in annual},
    'check_trip_file_vs_summary': {'days': chk[0], 'mean_ratio': round(chk[1], 4), 'min': round(chk[2], 4), 'max': round(chk[3], 4)},
    'source': 'City of Toronto, Private Transportation Companies open data (Transportation Services)',
    'licence': LICENCE,
}

os.makedirs(OUT, exist_ok=True)
for name, obj in [('hourly', hourly), ('wards', wards), ('flows', flows), ('supply', supply), ('years', years), ('meta', meta)]:
    with open(os.path.join(OUT, f'{name}.json'), 'w') as f:
        json.dump(obj, f, separators=(',', ':'), ensure_ascii=False)
print(json.dumps({k: meta[k] for k in ('days_by_type', 'trips_in_window', 'toronto_pickups_without_ward_share',
                                       'check_trip_file_vs_summary')}, indent=1))
