"""Fetch who currently holds each office the San Francisco map shows, into cities/sf/raw/representatives/.
Runs in GitHub Actions (fetch-sf.yml).

- ca.csv: Open States' current California legislators (data.openstates.org): Assembly and Senate, district and party
- house.xml: Clerk of the U.S. House member list (current members of Congress, with state and district)
- us_house_2021.geojson: the congressional districts the sitting members were elected in (Census 2024 cartographic
  boundaries, 119th Congress = the 2021 Citizens Redistricting Commission map), clipped to the city's box. The map's
  congress layer has the Proposition 50 lines used from the November 3, 2026 election; the card looks the sitting
  member up in these until the new members take office on January 3, 2027 (Dallas does the same).
- bos_*.html: the Board of Supervisors' pages, for the current members (DataSF's district file names a supervisor
  who was recalled in 2025, so its names aren't used). representatives.py reads them.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_lib import *

OUT = os.path.join(RAW, 'representatives')
os.makedirs(OUT, exist_ok=True)
failed = []
for name, url in [('ca.csv', 'https://data.openstates.org/people/current/ca.csv'), ('house.xml', 'https://clerk.house.gov/xml/lists/MemberData.xml'),
                  ('bos_supervisors.html', 'https://sfbos.org/supervisors'), ('bos_home.html', 'https://sfbos.org/'),
                  ('bos_sfgov.html', 'https://www.sf.gov/departments--board-supervisors')]:
    try:
        b = get(url, tries=3); open(os.path.join(OUT, name), 'wb').write(b); print('wrote', name, len(b))
    except Exception as e:
        print('failed', name, e); failed.append(name)


def house_2021():
    z = download('https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_cd119_500k.zip', os.path.join(TMP, 'cd119.zip'))
    shp_to_geojson(z, '1=1', os.path.join('representatives', 'us_house_2021.geojson'), spat=CITY)


step('us_house_2021', house_2021)
print('failed:', failed + FAILED or 'none')
