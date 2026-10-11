"""Fetch the City of Vancouver's street blocks (public-streets: every block of every public street, with its
hundred-block address, e.g. "2300 W 47TH AV") into raw/public_streets.geojson. Runs in GitHub Actions
(fetch-vancouver.yml). Used for How addresses work: the Ontario and Carrall Street divide, which streets
take W and E, and how block numbers run. Open Government Licence – Vancouver."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch_lib as F

URL = 'https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/public-streets/exports/geojson?select=hblock,streetuse,geom'
F.step('public streets', lambda: F.save('public_streets.geojson', json.loads(F.get(URL))))
print('done; failed:', F.FAILED or 'none')
