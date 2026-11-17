"""Dubai's curated lists: the city's outline, its sides, the highways, known-as names and landmarks.
Deliberately short. Positions are approximate; build.py and landmarks.py move each to OpenStreetMap's point of the
same name when one is close by (raw/places.json, raw/pois.geojson). (lat, lon) throughout, like the other cities."""

# "The city" (scouting/dubai/FINDINGS.md): Dubai's urban area from Jebel Ali to the Sharjah border, inland to just past
# Emirates Road (E611) with Dubai South, Expo City and Dubailand; not the inland desert or the Hatta exclave. This hand
# outline is cut to the emirate's OSM boundary and the coast, so only its inland edge matters. (lon, lat)
CITY_OUTLINE = [(54.80, 24.90), (54.93, 24.82), (55.08, 24.78), (55.22, 24.80), (55.30, 24.93), (55.40, 25.03),
                (55.50, 25.12), (55.57, 25.22), (55.58, 25.30), (55.45, 25.40), (55.30, 25.42), (54.80, 25.20)]

# Sides: Deira (the old town north and east of the Creek, and everything east of it up to the Sharjah border and down the
# Al Ain Road), Bur Dubai (the old town on the Creek's other bank, out along the coast to Umm Suqeim and inland to the
# Al Ain Road) and New Dubai (Al Barsha to Jebel Ali and the newer inland districts). Lines people draw, roughly:
# the Creek, the Al Ain Road (E66), and Umm Suqeim/Al Barsha. (lon, lat)
SIDE_LINES = {
    'Deira': [(55.255, 25.31), (55.288, 25.268), (55.312, 25.247), (55.333, 25.218), (55.348, 25.193), (55.37, 25.175),
              (55.40, 25.14), (55.46, 25.07), (55.62, 24.86), (55.80, 25.0), (55.80, 25.50), (55.30, 25.50)],
    'Bur Dubai': [(55.255, 25.31), (55.288, 25.268), (55.312, 25.247), (55.333, 25.218), (55.348, 25.193), (55.37, 25.175),
                  (55.40, 25.14), (55.46, 25.07), (55.35, 25.03), (55.27, 25.105), (55.215, 25.135), (55.19, 25.16), (55.10, 25.30)],
}
SIDES = ['Deira', 'Bur Dubai', 'New Dubai']
SIDE_INFO = {
    'Deira': 'The old town north of the Creek, and the districts out to the Sharjah border and the airport: Deira, Al Qusais, Mirdif, Rashidiya',
    'Bur Dubai': 'The old town south of the Creek and the coast to Umm Suqeim: Bur Dubai, Karama, Jumeirah, Downtown, Business Bay',
    'New Dubai': 'Al Barsha and Al Quoz to Jebel Ali, and the newer districts inland: the Marina, JLT, JVC, Dubailand, Dubai South',
}

# Highways: the federal E roads, plus Dubai's grade-separated D roads people call by name. ref -> (shield, name)
HIGHWAYS = {
    'E11': 'Sheikh Zayed Road', 'E311': 'Sheikh Mohammed bin Zayed Road', 'E611': 'Emirates Road', 'E44': 'Hatta Road',
    'E66': 'Al Ain Road', 'E77': 'Expo Road', 'E55': 'Umm Suqeim–Al Qudra Road', 'E88': 'Al Dhaid Road',
    'E102': 'Kalba Road', 'E75': 'Al Fayah Road', 'D68': 'Al Khail Road',
}

# Names people give directions by that aren't the communities on the map. (name, OSM name or None, (lat, lon))
KNOWN_AS = [{'name': n, 'osm': o or n, 'kind': k, 'at': at} for n, o, k, at in [
    ('Dubai Marina', None, 'area', (25.0800, 55.1400)), ('JLT', 'Jumeirah Lake Towers', 'area', (25.0700, 55.1450)),
    ('JBR', 'Jumeirah Beach Residence', 'area', (25.0790, 55.1330)), ('Palm Jumeirah', 'Nakhlat Jumeira', 'area', (25.1170, 55.1350)),
    ('Bluewaters', 'Bluewaters Island', 'area', (25.0800, 55.1210)), ('Media City', 'Dubai Media City', 'area', (25.0940, 55.1520)),
    ('Internet City', 'Dubai Internet City', 'area', (25.0950, 55.1600)), ('Knowledge Park', 'Dubai Knowledge Park', 'area', (25.1030, 55.1640)),
    ('Barsha Heights', None, 'area', (25.0980, 55.1760)), ('Al Barsha', None, 'area', (25.1000, 55.2000)),
    ('Emirates Hills', None, 'area', (25.0650, 55.1650)), ('The Greens', None, 'area', (25.0930, 55.1700)),
    ('JVC', 'Jumeirah Village Circle', 'area', (25.0570, 55.2080)), ('Al Furjan', None, 'area', (25.0270, 55.1470)),
    ('Discovery Gardens', None, 'area', (25.0390, 55.1410)), ('Motor City', None, 'area', (25.0420, 55.2420)),
    ('Sports City', 'Dubai Sports City', 'area', (25.0390, 55.2210)), ('Arabian Ranches', None, 'area', (25.0560, 55.2700)),
    ('Dubai Hills', 'Dubai Hills Estate', 'area', (25.1070, 55.2470)), ('Al Quoz', None, 'area', (25.1500, 55.2400)),
    ('Al Sufouh', None, 'area', (25.1150, 55.1800)), ('Umm Suqeim', None, 'area', (25.1450, 55.2000)),
    ('City Walk', None, 'area', (25.2060, 55.2620)), ('La Mer', None, 'area', (25.2300, 55.2530)),
    ('Al Fahidi', 'Al Fahidi Historical Neighbourhood', 'area', (25.2640, 55.3000)), ('Meena Bazaar', None, 'area', (25.2600, 55.2950)),
    ('Gold Souk', 'Deira Gold Souk', 'area', (25.2700, 55.2970)), ('Satwa', 'Al Satwa', 'area', (25.2240, 55.2770)),
    ('Dubai Creek Harbour', None, 'area', (25.2050, 55.3450)), ('Festival City', 'Dubai Festival City', 'area', (25.2230, 55.3550)),
    ('Silicon Oasis', 'Dubai Silicon Oasis', 'area', (25.1200, 55.3800)), ('International City', None, 'area', (25.1650, 55.4100)),
    ('Academic City', 'Dubai Academic City', 'area', (25.1300, 55.4200)), ('Ras Al Khor', None, 'area', (25.1800, 55.3500)),
    ('Jebel Ali Free Zone', None, 'area', (25.0100, 55.0800)), ('Dubai Investments Park', None, 'area', (24.9800, 55.1900)),
    ('Dubai South', None, 'area', (24.9100, 55.1600)), ('Expo City', 'Expo City Dubai', 'area', (24.9620, 55.1500)),
    ('Al Mamzar', None, 'area', (25.3000, 55.3500)), ('Al Khawaneej', None, 'area', (25.2400, 55.5100)),
]]

CAT_LABEL = {'culture': 'Heritage site or sight', 'park': 'Park or beach', 'sports': 'Sports venue', 'campus': 'University',
             'civic': 'Civic and transport', 'airport': 'Airport', 'music': 'Arts and events venue'}


def L_(name, cat, tier, at, aliases=(), osm=None):
    return {'name': name, 'cat': cat, 'tier': tier, 'at': at, 'aliases': list(aliases), 'osm': osm or name}


LANDMARKS = [
    L_('Burj Khalifa', 'culture', 1, (25.1972, 55.2744), ['Tallest building']),
    L_('Dubai Mall', 'civic', 1, (25.1985, 55.2796), ['The Dubai Mall', 'Dubai Aquarium'], 'The Dubai Mall'),
    L_('Burj Al Arab', 'culture', 1, (25.1412, 55.1853), [], 'Jumeirah Burj Al Arab'),
    L_('Dubai Frame', 'culture', 1, (25.2354, 55.3003)),
    L_('Museum of the Future', 'culture', 1, (25.2192, 55.2820)),
    L_('Al Fahidi Fort', 'culture', 2, (25.2633, 55.2972), ['Dubai Museum']),
    L_('Al Shindagha', 'culture', 2, (25.2690, 55.2880), ['Shindagha Museum', 'Al Shindagha Historical District'], 'Al Shindagha Museum'),
    L_('Jumeirah Mosque', 'culture', 2, (25.2339, 55.2654)),
    L_('Atlantis The Palm', 'culture', 2, (25.1304, 55.1171), ['Atlantis', 'Aquaventure'], 'Atlantis Hotel'),
    L_('Dubai Opera', 'music', 1, (25.1955, 55.2722)),
    L_('Coca-Cola Arena', 'music', 2, (25.2052, 55.2694)),
    L_('Dubai World Trade Centre', 'civic', 2, (25.2250, 55.2870), ['DWTC', 'Trade Centre', 'GITEX']),
    L_('Expo City Dubai', 'civic', 1, (24.9632, 55.1500), ['Expo 2020', 'Al Wasl Plaza']),
    L_('Global Village', 'culture', 2, (25.0697, 55.3047)),
    L_('Mall of the Emirates', 'civic', 2, (25.1181, 55.2003), ['Ski Dubai', 'MOE']),
    L_('Dubai Marina Mall', 'civic', 3, (25.0762, 55.1406)),
    L_('Dubai International Airport', 'airport', 1, (25.2532, 55.3657), ['DXB', 'Dubai Airport']),
    L_('Al Maktoum International Airport', 'airport', 1, (24.9090, 55.1720), ['DWC', 'Dubai World Central']),
    L_('Sharjah International Airport', 'airport', 2, (25.3286, 55.5172), ['SHJ']),
    L_('Zabeel Park', 'park', 2, (25.2310, 55.2970)),
    L_('Creek Park', 'park', 2, (25.2387, 55.3299), ['Dubai Creek Park']),
    L_('Al Safa Park', 'park', 2, (25.1870, 55.2420), ['Safa Park'], 'Safa Park'),
    L_('Mushrif Park', 'park', 2, (25.2200, 55.4560), ['Mushrif National Park'], 'Mushrif National Park'),
    L_('Dubai Miracle Garden', 'park', 2, (25.0605, 55.2443)),
    L_('Kite Beach', 'park', 2, (25.1580, 55.1950)),
    L_('JBR Beach', 'park', 3, (25.0790, 55.1330), ['The Beach at JBR']),
    L_('Al Mamzar Beach Park', 'park', 2, (25.3219, 55.3499), [], 'Al Mamzar Park'),
    L_('Dubai Autodrome', 'sports', 3, (25.0490, 55.2390)),
    L_('Meydan Racecourse', 'sports', 2, (25.1600, 55.3000), ['Dubai World Cup', 'Meydan']),
    L_('Dubai Tennis Stadium', 'sports', 3, (25.2410, 55.3410), ['Dubai Duty Free Tennis'], 'Dubai Duty Free Tennis Stadium'),
    L_('Dubai International Stadium', 'sports', 3, (25.0460, 55.2190), ['Dubai International Cricket Stadium', 'Sports City'], 'Dubai International Cricket Stadium'),
    L_('Ain Dubai', 'culture', 3, (25.0805, 55.1225), ['Bluewaters wheel']),
    L_('Dubai Creek', 'culture', 2, (25.2560, 55.3060), ['The Creek', 'Abra crossing'], 'Dubai Creek'),
    L_('Etihad Rail Dubai station', 'civic', 2, (25.0171, 55.1678), ['Al Yalayis station', 'Etihad Rail'], 'Dubai Al Yalayis Station'),
    # Sharjah and Ajman: a few, for the regional view
    L_('Al Noor Mosque', 'culture', 3, (25.3348, 55.3872)),
    L_('Sharjah Museum of Islamic Civilization', 'culture', 3, (25.3606, 55.3871)),
    L_('Al Qasba', 'culture', 3, (25.3222, 55.3790)),
    L_('Al Majaz Waterfront', 'park', 3, (25.3266, 55.3880), [], 'Al Majaz Park'),
    L_('University City Sharjah', 'campus', 2, (25.2900, 55.4900), ['American University of Sharjah', 'University of Sharjah'], 'University City'),
    L_('Ajman Museum', 'culture', 3, (25.4153, 55.4466)),
    L_('Ajman Corniche', 'park', 3, (25.4170, 55.4440)),
]

# Places beyond the city for the regional view's labels ("Sharjah", "Ajman"...). (name, (lon, lat))
BEYOND = [('Sharjah', (55.40, 25.34)), ('Ajman', (55.47, 25.40)), ('Umm Al Quwain', (55.56, 25.53)),
          ('Abu Dhabi emirate', (54.92, 24.80)), ('Hatta (Dubai)', (55.75, 24.95))]
