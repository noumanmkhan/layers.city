"""What the fact-sheet scripts share: the city's settings (cities/<city>/factsheet.json) and a few helpers.

Everything a fact sheet says that is particular to one city lives in that file: which published file holds the
places, the transit hubs, the drive destinations, the names of the agencies and programmes (a bike-share
scheme, a parking authority), the distance unit and the page's wording. The engine itself names no city.
"""
import json, math, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MI_KM = 1.609344


def settings(city):
    p = os.path.join(ROOT, 'cities', city, 'factsheet.json')
    if not os.path.exists(p):
        raise SystemExit(f'{city}: no cities/{city}/factsheet.json (the fact sheets\' settings for this city)')
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def units_file(cfg):
    """The published file of places that get a fact sheet each, such as neighbourhoods.geojson."""
    return cfg.get('units', 'neighbourhoods') + '.geojson'


def station_keys(feats):
    """A name for each station that is unique in the city: the station's own name, or, where two stations share
    it (New York has several 86 St), the name with its lines, "86 St (4 5 6)". Fact sheets look stations up by
    this name, so walk_grid.py and build.py must agree on it."""
    names = [f['properties']['name'] for f in feats]
    count = {}
    for n in names:
        count[n] = count.get(n, 0) + 1
    out = [n if count[n] == 1 else f"{n} ({' '.join(f['properties'].get('lines', []))})" for n, f in zip(names, feats)]
    seen = {}
    for i, n in enumerate(out):   # still the same (one name, same lines, far apart): number them
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            out[i] = f'{n} {seen[n]}'
    return out


class Units:
    """Distances, lengths and areas in the city's unit ("km" or "mi"), worded as the map words them."""

    def __init__(self, unit):
        self.mi = unit == 'mi'

    def dist(self, d_km):
        """Toronto's fact sheets: "600 m", "1.8 km". Miles: "300 ft" under a tenth of a mile, then "0.4 mi"."""
        if not self.mi:
            return f'{d_km * 1000:.0f} m' if d_km < 1 else f'{d_km:.1f} km'
        mi = d_km / MI_KM
        return f'{(round(mi * 5280 / 50) * 50) or 50} ft' if mi < 0.095 else f'{mi:.1f} mi'

    def length(self, l_km):
        return f'{l_km:.1f} km' if not self.mi else f'{l_km / MI_KM:.1f} mi'

    def area(self, a_km2):
        return f'{a_km2:.1f} km²' if not self.mi else f'{a_km2 / MI_KM ** 2:.1f} sq mi'

    def radius_km(self, r):
        """A radius given in the city's unit, in km."""
        return r * MI_KM if self.mi else r

    def radius(self, r):
        return f'{r:g} {"mi" if self.mi else "km"}'
