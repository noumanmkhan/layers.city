"""Hand-kept names for the Dallas map: the areas built from ZIP codes, known-as names and main streets.

Dallas has no official neighbourhoods (its Neighborhood Organizations Map is self-drawn and overlapping), so the
map's units are the ZIP codes people already use, clipped to the city limits, and the areas group them the way
Dallasites usually place a ZIP. The grouping is a first draft for local review."""
import re

# Area -> ZIP codes. A ZIP that is mostly another city (Coppell's 75019, Grand Prairie's 75051) still joins the
# area its Dallas part sits in.
SIDES = {
    'Downtown & Uptown': ['75201', '75202', '75204', '75219', '75226', '75207'],
    'East Dallas': ['75214', '75206', '75218', '75223', '75228', '75246'],
    'Lake Highlands': ['75238', '75243', '75231'],
    'North Dallas': ['75205', '75225', '75230', '75251', '75240', '75254'],
    'Far North Dallas': ['75248', '75252', '75287'],
    'Northwest Dallas': ['75209', '75235', '75220', '75229', '75247', '75234', '75244', '75019', '75007'],
    'West Dallas': ['75212'],
    'Oak Cliff': ['75208', '75203', '75211', '75224', '75233', '75236', '75249', '75051', '75052', '75104'],
    'South Dallas': ['75210', '75215'],
    'Southern Dallas': ['75216', '75241', '75232', '75237', '75134', '75141'],
    'Pleasant Grove': ['75217', '75227', '75253', '75159'],
}
SIDE_INFO = {
    'Downtown & Uptown': 'The central business district, the Arts District and Deep Ellum, with Uptown, Oak Lawn and the Design District north and west of it.',
    'East Dallas': 'Old East Dallas, Lakewood, Lower Greenville and the neighbourhoods around White Rock Lake.',
    'Lake Highlands': 'North of White Rock Lake, between Northwest Highway and LBJ (I-635), with Vickery Meadow to its west.',
    'North Dallas': 'Preston Hollow and the neighbourhoods along the Dallas North Tollway and Central Expressway, up to LBJ (I-635).',
    'Far North Dallas': 'North of LBJ (I-635), up to the Collin and Denton county lines: Prestonwood and the neighbourhoods around Bent Tree.',
    'Northwest Dallas': 'Love Field, Bachman Lake, the Medical District and Harry Hines, out to Cypress Waters by DFW Airport.',
    'West Dallas': 'Across the Trinity from downtown, by the Margaret Hunt Hill Bridge: Trinity Groves and the West Dallas neighbourhoods.',
    'Oak Cliff': 'South and west of the Trinity: Bishop Arts, Kessler Park, Winnetka Heights and the neighbourhoods out to Mountain Creek Lake.',
    'South Dallas': 'Fair Park and the historic neighbourhoods south-east of downtown, along MLK Jr. Boulevard.',
    'Southern Dallas': 'South of Oak Cliff along I-35E and US 67, out to Red Bird and the city’s southern edge.',
    'Pleasant Grove': 'South-east Dallas, east of the Trinity and south of I-30, out to the city’s eastern edge.',
}
SIDE_OF = {z: s for s, zs in SIDES.items() for z in zs}

# Known-as names: [name, OpenStreetMap place name to snap to, kind, [lat, lon] by hand].
KNOWN_AS = [{'name': n, 'osm': o or n, 'kind': k, 'at': at} for n, o, k, at in [
    ('Deep Ellum', None, 'area', [32.7840, -96.7830]),
    ('Bishop Arts', 'Bishop Arts District', 'area', [32.7487, -96.8287]),
    ('Uptown', None, 'area', [32.7985, -96.8005]),
    ('Oak Lawn', None, 'area', [32.8120, -96.8130]),
    ('Design District', None, 'area', [32.7960, -96.8250]),
    ('Knox-Henderson', 'Knox', 'area', [32.8195, -96.7900]),
    ('Lower Greenville', None, 'area', [32.8150, -96.7700]),
    ('Lakewood', None, 'area', [32.8170, -96.7480]),
    ('Old East Dallas', None, 'area', [32.7980, -96.7700]),
    ('Arts District', None, 'area', [32.7895, -96.7985]),
    ('Victory Park', None, 'area', [32.7880, -96.8100]),
    ('The Cedars', 'South Side', 'area', [32.7700, -96.7950]),
    ('Fair Park', None, 'area', [32.7790, -96.7600]),
    ('Trinity Groves', None, 'area', [32.7760, -96.8370]),
    ('Kessler Park', None, 'area', [32.7600, -96.8550]),
    ('Winnetka Heights', 'Winnetka Heights Historic District', 'area', [32.7490, -96.8410]),
    ('Preston Hollow', None, 'area', [32.8800, -96.8050]),
    ('Vickery Meadow', 'Vickery Meadows', 'area', [32.8690, -96.7600]),
    ('Lake Highlands', None, 'area', [32.8900, -96.7250]),
    ('Casa Linda', None, 'area', [32.8370, -96.6930]),
    ('Medical District', None, 'area', [32.8110, -96.8370]),
    ('Bachman Lake', None, 'area', [32.8560, -96.8660]),
    ('Asian Trade District', None, 'area', [32.8810, -96.8960]),
    ('Prestonwood', None, 'area', [32.9700, -96.8130]),
    ('Pleasant Grove', None, 'area', [32.7200, -96.6900]),
    ('Red Bird', None, 'area', [32.6800, -96.8700]),
    ('Cypress Waters', None, 'area', [32.9400, -96.9780]),
]]

# Main streets drawn heavier (the rest of OpenStreetMap's primary and secondary roads are drawn as minor).
MAJOR_STREETS = {
    'Preston Rd', 'Greenville Ave', 'Lemmon Ave', 'Inwood Rd', 'Mockingbird Ln', 'Northwest Hwy', 'Royal Ln', 'Forest Ln',
    'Belt Line Rd', 'Hillcrest Rd', 'Abrams Rd', 'Skillman St', 'Gaston Ave', 'Ross Ave', 'McKinney Ave', 'Live Oak St',
    'Columbia Ave', 'Buckner Blvd', 'Ferguson Rd', 'Garland Rd', 'Jefferson Blvd', 'Davis St', 'Zang Blvd', 'Beckley Ave',
    'Hampton Rd', 'Westmoreland Rd', 'Illinois Ave', 'Kiest Blvd', 'Ledbetter Dr', 'Lancaster Rd', 'Malcolm X Blvd',
    'Martin Luther King Jr Blvd', 'Harry Hines Blvd', 'Marsh Ln', 'Webb Chapel Rd', 'Coit Rd', 'Frankford Rd', 'Campbell Rd',
    'Arapaho Rd', 'Spring Valley Rd', 'Walnut Hill Ln', 'Lovers Ln', 'Commerce St', 'Main St', 'Elm St', 'Singleton Blvd',
    'Fort Worth Ave', 'Riverfront Blvd', 'Cedar Springs Rd', 'Maple Ave', 'Oak Lawn Ave', 'Haskell Ave', 'Lake June Rd',
    'Scyene Rd', 'Military Pkwy', 'Camp Wisdom Rd', 'Wheatland Rd', 'Polk St', 'Marsalis Ave', 'Second Ave', 'Park Ln',
    'Midway Rd', 'Josey Ln', 'Audelia Rd', 'Plano Rd', 'Jupiter Rd', 'Lake Highlands Dr', 'Bruton Rd', 'Elam Rd',
    'Pleasant Grove Rd', 'Cockrell Hill Rd', 'Westmoreland Rd', 'Red Bird Ln', 'Wheatland Rd', 'Simpson Stuart Rd',
}
ABBR = [(r'\bRoad\b', 'Rd'), (r'\bStreet\b', 'St'), (r'\bAvenue\b', 'Ave'), (r'\bBoulevard\b', 'Blvd'), (r'\bLane\b', 'Ln'),
        (r'\bDrive\b', 'Dr'), (r'\bParkway\b', 'Pkwy'), (r'\bHighway\b', 'Hwy'), (r'\bNorth\b', 'N'), (r'\bSouth\b', 'S'),
        (r'\bEast\b', 'E'), (r'\bWest\b', 'W'), (r'\bExpressway\b', 'Expy'), (r'\bFreeway\b', 'Fwy'), (r'\bJunior\b', 'Jr'),
        (r'\bMartin Luther King,? Jr\.?\b', 'Martin Luther King Jr'), (r'\.', '')]


def street_name(n):
    for a, b in ABBR:
        n = re.sub(a, b, n)
    return re.sub(r'\s+', ' ', n).strip()


def street_key(n):
    """The street without its direction prefix, so "N Hampton Rd" and "S Hampton Rd" join into one main street."""
    return re.sub(r'^(N|S|E|W) ', '', street_name(n))
