"""San Francisco's hand-kept lists: the parts of the city, known-as names, landmarks, main streets and highways.

Units (decided with the user, October 30, 2026): the City's 41 Analysis Neighborhoods (DataSF p5b7-5n3h), which are
2020 census tracts grouped by the Planning Department, so the neighbourhood lens adds up exactly. The 117 SF Find
neighbourhoods (pty2-tcw4, the names people say: Cole Valley, Dogpatch, NoPa...) are a second, finer layer.

Parts of the city: San Francisco never had boroughs or former cities, so the "major" fill is the five parts locals
use when giving the rough idea, grouping the 41 Analysis Neighborhoods. Hand-drawn, not an official division.

Known-as names: places people call neighbourhoods that the 41 don't name. Positions (lat, lon) are approximate
centres, moved to OpenStreetMap's place point when one with the same name sits within 1 km (raw/osm_places.json).

Landmarks: a short list of places San Franciscans give directions by. tier 1 = city-scale anchors (from zoom 11);
tier 2 = from zoom 13. 'osm' is the OpenStreetMap name to snap to when it differs.
"""
import re

SIDES = {
    'Downtown': ['Financial District/South Beach', 'South of Market', 'Tenderloin', 'Chinatown', 'Nob Hill', 'North Beach',
                 'Russian Hill', 'Mission Bay', 'Treasure Island'],
    'Northside': ['Marina', 'Pacific Heights', 'Presidio', 'Presidio Heights', 'Seacliff', 'Japantown', 'Western Addition',
                  'Lone Mountain/USF'],
    'West Side': ['Inner Richmond', 'Outer Richmond', 'Lincoln Park', 'Golden Gate Park', 'Inner Sunset', 'Sunset/Parkside',
                  'Lakeshore', 'West of Twin Peaks'],
    'Central': ['Haight Ashbury', 'Hayes Valley', 'Castro/Upper Market', 'Noe Valley', 'Twin Peaks', 'Glen Park', 'Mission'],
    'Southeast': ['Potrero Hill', 'Bayview Hunters Point', 'Bernal Heights', 'Excelsior', 'Outer Mission', 'Portola',
                  'Visitacion Valley', 'McLaren Park', 'Oceanview/Merced/Ingleside'],
}
SIDE_INFO = {
    'Downtown': 'The Financial District, SoMa and the hills above them: Nob Hill, Russian Hill, North Beach and Chinatown, out to Mission Bay and Treasure Island.',
    'Northside': 'Along the Bay from the Marina to the Presidio, and the Western Addition, Japantown and Pacific Heights behind it.',
    'West Side': 'The Richmond and the Sunset, either side of Golden Gate Park, out to Ocean Beach and Lake Merced.',
    'Central': 'The middle of the city: the Mission, the Castro, Noe Valley, the Haight and Twin Peaks.',
    'Southeast': 'Potrero Hill and Bernal Heights down to Bayview, the Excelsior and Visitacion Valley.',
}

KNOWN_AS = [{'name': n, 'osm': o or n, 'kind': k, 'at': at} for n, o, k, at in [
    ('SoMa', 'South of Market', 'area', [37.7785, -122.4056]), ('Union Square', None, 'area', [37.7880, -122.4075]),
    ('Embarcadero', 'The Embarcadero', 'area', [37.7955, -122.3937]), ('Rincon Hill', None, 'area', [37.7855, -122.3925]),
    ("Fisherman's Wharf", None, 'area', [37.8080, -122.4177]), ('Telegraph Hill', None, 'area', [37.8015, -122.4058]),
    ('Jackson Square', None, 'area', [37.7967, -122.4030]), ('Polk Gulch', None, 'area', [37.7905, -122.4205]),
    ('Cow Hollow', None, 'area', [37.7975, -122.4365]), ('Laurel Heights', None, 'area', [37.7860, -122.4520]),
    ('NoPa', 'North Panhandle', 'area', [37.7765, -122.4410]), ('Lower Haight', None, 'area', [37.7720, -122.4310]),
    ('Cole Valley', None, 'area', [37.7655, -122.4500]), ('Duboce Triangle', None, 'area', [37.7670, -122.4320]),
    ('Dolores Heights', None, 'area', [37.7570, -122.4300]), ('Mission Dolores', None, 'area', [37.7615, -122.4265]),
    ('Dogpatch', None, 'area', [37.7590, -122.3890]), ('Bernal Heights', None, 'area', [37.7410, -122.4155]),
    ('Inner Mission', None, 'area', [37.7590, -122.4180]), ('Diamond Heights', None, 'area', [37.7425, -122.4425]),
    ('Forest Hill', None, 'area', [37.7480, -122.4635]), ('St. Francis Wood', 'Saint Francis Wood', 'area', [37.7355, -122.4675]),
    ('Parkside', None, 'area', [37.7390, -122.4890]), ('Outer Sunset', None, 'area', [37.7555, -122.4940]),
    ('Sea Cliff', None, 'area', [37.7865, -122.4890]), ('Ingleside', None, 'area', [37.7230, -122.4545]),
    ('Crocker-Amazon', 'Crocker Amazon', 'area', [37.7105, -122.4380]), ('Silver Terrace', None, 'area', [37.7360, -122.4005]),
    ('Hunters Point', None, 'area', [37.7290, -122.3755]), ('Little Saigon', None, 'enclave', [37.7835, -122.4170]),
]]

L_ = lambda name, cat, tier, at, aliases=(), osm=None: {'name': name, 'osm': osm or name, 'cat': cat, 'tier': tier, 'at': at, 'aliases': list(aliases)}
LANDMARKS = [
    # Sports
    L_('Oracle Park', 'sports', 1, (37.7786, -122.3893), ['Giants', 'AT&T Park', 'Pac Bell Park']),
    L_('Chase Center', 'sports', 1, (37.7680, -122.3877), ['Warriors', 'Valkyries']),
    L_('Kezar Stadium', 'sports', 2, (37.7669, -122.4559), ['Kezar']),
    # Parks and views
    L_('Golden Gate Park', 'park', 1, (37.7694, -122.4862), []),
    L_('Presidio', 'park', 1, (37.7989, -122.4662), ['The Presidio', 'Presidio of San Francisco'], osm='Presidio of San Francisco'),
    L_('Twin Peaks', 'park', 1, (37.7544, -122.4477), []),
    L_('Ocean Beach', 'park', 1, (37.7594, -122.5107), []),
    L_('Crissy Field', 'park', 2, (37.8039, -122.4645), []),
    L_('Dolores Park', 'park', 2, (37.7596, -122.4269), ['Mission Dolores Park'], osm='Mission Dolores Park'),
    L_('Alamo Square', 'park', 2, (37.7764, -122.4346), ['Painted Ladies']),
    L_('Lands End', 'park', 2, (37.7799, -122.5110), ['Sutro Baths']),
    L_('Lake Merced', 'park', 2, (37.7246, -122.4920), []),
    L_('McLaren Park', 'park', 2, (37.7184, -122.4194), ['John McLaren Park'], osm='John McLaren Park'),
    L_('Bernal Heights Park', 'park', 2, (37.7430, -122.4141), ['Bernal Hill']),
    L_('Salesforce Park', 'park', 2, (37.7895, -122.3965), ['Transbay rooftop park']),
    # Museums and sights
    L_('Golden Gate Bridge', 'culture', 1, (37.8199, -122.4783), []),
    L_('Alcatraz Island', 'culture', 1, (37.8267, -122.4230), ['Alcatraz', 'The Rock']),
    L_('Coit Tower', 'culture', 1, (37.8024, -122.4058), ['Telegraph Hill']),
    L_('Ferry Building', 'culture', 1, (37.7955, -122.3937), ['Ferry Plaza']),
    L_('Pier 39', 'culture', 2, (37.8087, -122.4098), ['PIER 39', 'Sea lions']),
    L_('Lombard Street', 'culture', 2, (37.8021, -122.4187), ['Crooked street', 'Crookedest street']),
    L_('Palace of Fine Arts', 'culture', 2, (37.8029, -122.4484), []),
    L_('Exploratorium', 'culture', 2, (37.8017, -122.3973), ['Pier 15']),
    L_('San Francisco Museum of Modern Art', 'culture', 2, (37.7857, -122.4011), ['SFMOMA']),
    L_('California Academy of Sciences', 'culture', 2, (37.7699, -122.4661), ['Cal Academy']),
    L_('de Young Museum', 'culture', 2, (37.7715, -122.4687), ['de Young', 'DeYoung']),
    L_('Legion of Honor', 'culture', 2, (37.7845, -122.5008), ['California Palace of the Legion of Honor']),
    L_('Mission Dolores', 'culture', 2, (37.7642, -122.4270), ['Misión San Francisco de Asís']),
    L_('Grace Cathedral', 'culture', 2, (37.7919, -122.4134), []),
    L_('Transamerica Pyramid', 'culture', 2, (37.7952, -122.4028), ['Transamerica']),
    L_('Salesforce Tower', 'culture', 1, (37.7898, -122.3969), []),
    L_('San Francisco Zoo', 'culture', 2, (37.7330, -122.5030), ['SF Zoo']),
    # Music and theatre
    L_('War Memorial Opera House', 'music', 2, (37.7782, -122.4209), ['SF Opera', 'San Francisco Ballet']),
    L_('Davies Symphony Hall', 'music', 2, (37.7777, -122.4207), ['SF Symphony', 'Louise M. Davies Symphony Hall'], osm='Louise M. Davies Symphony Hall'),
    L_('Bill Graham Civic Auditorium', 'music', 2, (37.7786, -122.4177), ['Bill Graham', 'Civic Auditorium']),
    L_('The Fillmore', 'music', 2, (37.7840, -122.4330), ['Fillmore']),
    L_('Moscone Center', 'civic', 2, (37.7842, -122.4016), ['Moscone']),
    # Civic and transport
    L_('San Francisco City Hall', 'civic', 1, (37.7793, -122.4193), ['City Hall']),
    L_('Salesforce Transit Center', 'civic', 2, (37.7895, -122.3965), ['Transbay Transit Center', 'Transbay Terminal']),
    L_('San Francisco Caltrain Station', 'civic', 2, (37.7766, -122.3947), ['4th and King', 'Caltrain'], osm='San Francisco'),
    L_('San Francisco International Airport', 'airport', 1, (37.6213, -122.3790), ['SFO']),
    L_('Oakland International Airport', 'airport', 1, (37.7126, -122.2197), ['OAK', 'Oakland Airport'], osm='Oakland San Francisco Bay Airport'),
    L_('San José Mineta International Airport', 'airport', 2, (37.3639, -121.9289), ['SJC', 'San Jose Airport'], osm='San José Mineta International Airport'),
]

# Main streets drawn heavier (OpenStreetMap's other primary and secondary roads are drawn as minor). street_key() forms.
MAJOR_STREETS = {
    'Market St', 'Mission St', 'Van Ness Ave', 'Geary Blvd', 'Geary St', 'Lombard St', 'Columbus Ave', 'The Embarcadero',
    'California St', 'Divisadero St', 'Fillmore St', 'Masonic Ave', 'Park Presidio Blvd', '19th Ave', 'Sunset Blvd', 'Great Hwy',
    'Lincoln Way', 'Fulton St', 'Fell St', 'Oak St', 'Octavia Blvd', 'Franklin St', 'Gough St', 'Bush St', 'Pine St', 'Broadway',
    'Stockton St', 'Kearny St', '3rd St', '4th St', '16th St', '24th St', 'Cesar Chavez St', 'Potrero Ave', 'Folsom St', 'Howard St',
    'Harrison St', 'Bryant St', 'King St', 'Townsend St', 'Brannan St', 'Valencia St', 'Guerrero St', 'Dolores St', 'Castro St',
    'Church St', 'Portola Dr', "O'Shaughnessy Blvd", 'Monterey Blvd', 'Ocean Ave', 'Alemany Blvd', 'San Jose Ave', 'Geneva Ave',
    'Bayshore Blvd', 'Silver Ave', 'Evans Ave', 'Junipero Serra Blvd', 'Sloat Blvd', 'Taraval St', 'Judah St', 'Irving St', 'Noriega St',
    'Clement St', 'Balboa St', 'Clay St', 'Washington St', 'Turk St', 'Golden Gate Ave', 'McAllister St', 'Hayes St', 'Grove St',
    'Laguna Honda Blvd', 'Mission Bay Blvd', 'Marina Blvd', 'Bay St', 'North Point St', 'Jefferson St', 'Hyde St', 'Polk St', 'Larkin St',
}
ABBR = [(r'\bRoad\b', 'Rd'), (r'\bStreet\b', 'St'), (r'\bAvenue\b', 'Ave'), (r'\bBoulevard\b', 'Blvd'), (r'\bLane\b', 'Ln'),
        (r'\bDrive\b', 'Dr'), (r'\bParkway\b', 'Pkwy'), (r'\bHighway\b', 'Hwy'), (r'\bTerrace\b', 'Ter'), (r'\bExpressway\b', 'Expy'),
        (r'\bPlace\b', 'Pl'), (r'\bSaint\b', 'St'), (r'\.', ''), (r',', '')]


def street_name(n):
    for a, b in ABBR:
        n = re.sub(a, b, n)
    return re.sub(r'\s+', ' ', n).strip()


def street_key(n):
    return street_name(n)


# Highways: OpenStreetMap name or ref fragment -> the name people use, and the route on its shield.
HIGHWAYS = [
    ('Central Freeway', 'Central Freeway (US 101)', '101'), ('James Lick Freeway', 'Bayshore Freeway (US 101)', '101'),
    ('Bayshore Freeway', 'Bayshore Freeway (US 101)', '101'), ('Southern Embarcadero Freeway', 'I-280', '280'),
    ('John F. Foran Freeway', 'I-280', '280'), ('Junipero Serra Freeway', 'I-280', '280'), ('Embarcadero Freeway', 'I-80', '80'),
    ('San Francisco–Oakland Bay Bridge', 'Bay Bridge (I-80)', '80'), ('San Francisco-Oakland Bay Bridge', 'Bay Bridge (I-80)', '80'),
    ('Bay Bridge', 'Bay Bridge (I-80)', '80'), ('Golden Gate Bridge', 'Golden Gate Bridge (US 101)', '101'),
    ('Doyle Drive', 'Presidio Parkway (US 101)', '101'), ('Presidio Parkway', 'Presidio Parkway (US 101)', '101'),
    ('Mountain Lake Tunnel', 'Park Presidio (CA 1)', '1'), ('Robin Williams Tunnel', 'US 101', '101'),
]
