"""Hand-kept names for the New York City map: community district names, known-as names, landmarks and main streets.

The units are the City's 59 community districts (DCP "Community Districts", boro_cd 101-503). They have numbers,
not names, so each gets the name of the neighbourhoods people usually say for it (community boards use the same
pairs). The 12 joint interest areas in the file (boro_cd 164, 226-228, 355-356, 480-484, 595: Central Park, the
big Bronx parks, Prospect Park, the airports, Flushing Meadows, Gateway) aren't districts: they become park units
with no profile, named after the 2020 NTA they cover (build.py)."""
import re

BORO = {'1': 'Manhattan', '2': 'Bronx', '3': 'Brooklyn', '4': 'Queens', '5': 'Staten Island'}

CD_NAMES = {
    101: 'Financial District & Tribeca', 102: 'Greenwich Village & SoHo', 103: 'Lower East Side & Chinatown',
    104: "Chelsea & Hell's Kitchen", 105: 'Midtown', 106: 'Murray Hill & Turtle Bay', 107: 'Upper West Side',
    108: 'Upper East Side', 109: 'Morningside & Hamilton Heights', 110: 'Central Harlem', 111: 'East Harlem',
    112: 'Washington Heights & Inwood',
    201: 'Mott Haven & Melrose', 202: 'Hunts Point & Longwood', 203: 'Morrisania & Crotona', 204: 'Highbridge & Concourse',
    205: 'Fordham & University Heights', 206: 'Belmont & East Tremont', 207: 'Kingsbridge Heights & Bedford Park',
    208: 'Riverdale & Kingsbridge', 209: 'Parkchester & Soundview', 210: 'Throgs Neck & Co-op City',
    211: 'Morris Park & Pelham Parkway', 212: 'Williamsbridge & Wakefield',
    301: 'Greenpoint & Williamsburg', 302: 'Downtown Brooklyn & Fort Greene', 303: 'Bedford-Stuyvesant', 304: 'Bushwick',
    305: 'East New York & Starrett City', 306: 'Park Slope & Carroll Gardens', 307: 'Sunset Park & Windsor Terrace',
    308: 'Crown Heights & Prospect Heights', 309: 'Crown Heights South & Lefferts Gardens', 310: 'Bay Ridge & Dyker Heights',
    311: 'Bensonhurst & Bath Beach', 312: 'Borough Park & Kensington', 313: 'Coney Island & Brighton Beach',
    314: 'Flatbush & Midwood', 315: 'Sheepshead Bay & Gravesend', 316: 'Brownsville & Ocean Hill',
    317: 'East Flatbush', 318: 'Canarsie & Flatlands',
    401: 'Astoria & Long Island City', 402: 'Sunnyside & Woodside', 403: 'Jackson Heights & East Elmhurst',
    404: 'Elmhurst & Corona', 405: 'Ridgewood & Maspeth', 406: 'Forest Hills & Rego Park', 407: 'Flushing & Whitestone',
    408: 'Fresh Meadows & Briarwood', 409: 'Kew Gardens & Woodhaven', 410: 'Ozone Park & Howard Beach',
    411: 'Bayside & Little Neck', 412: 'Jamaica & Hollis', 413: 'Queens Village & Rosedale', 414: 'The Rockaways',
    501: 'North Shore', 502: 'Mid-Island', 503: 'South Shore',
}
CD_INFO = {
    501: 'St. George, Stapleton, Port Richmond and the neighbourhoods along the Kill Van Kull and the Narrows.',
    502: 'New Springville, Todt Hill, South Beach and the middle of the island around the Staten Island Mall.',
    503: 'Great Kills, Eltingville, Tottenville and the South Shore down to the Outerbridge Crossing.',
}
BORO_INFO = {
    'Manhattan': 'The island between the Hudson and East rivers: downtown, Midtown, the Upper East and West Sides, Harlem and Upper Manhattan.',
    'Bronx': "The only borough on the mainland, north of Manhattan across the Harlem River: Yankee Stadium, the Bronx Zoo and Pelham Bay Park.",
    'Brooklyn': 'The most populous borough, at the western end of Long Island, across the East River from Lower Manhattan.',
    'Queens': 'The largest borough by area, east of Brooklyn on Long Island, home to both of the city’s airports.',
    'Staten Island': 'The least populous borough, across New York Harbor, joined to Manhattan by the free ferry and to Brooklyn by the Verrazzano.',
}

# Known-as names: [name, OpenStreetMap place name to snap to, kind, [lat, lon] by hand].
KNOWN_AS = [{'name': n, 'osm': o or n, 'kind': k, 'at': at} for n, o, k, at in [
    ('Tribeca', 'TriBeCa', 'area', [40.7163, -74.0086]), ('Battery Park City', None, 'area', [40.7115, -74.0160]),
    ('SoHo', None, 'area', [40.7233, -74.0030]), ('West Village', None, 'area', [40.7358, -74.0036]),
    ('East Village', None, 'area', [40.7265, -73.9815]), ('Little Italy', None, 'area', [40.7191, -73.9973]),
    ('Chinatown', None, 'area', [40.7158, -73.9970]), ('NoHo', None, 'area', [40.7270, -73.9930]),
    ('Flatiron', 'Flatiron District', 'area', [40.7410, -73.9897]), ('Gramercy', 'Gramercy Park', 'area', [40.7368, -73.9845]),
    ('Kips Bay', None, 'area', [40.7420, -73.9780]), ('Hudson Yards', None, 'area', [40.7540, -74.0020]),
    ('Times Square', None, 'area', [40.7580, -73.9855]), ('Lincoln Square', None, 'area', [40.7740, -73.9840]),
    ('Yorkville', None, 'area', [40.7760, -73.9490]), ('Sugar Hill', None, 'area', [40.8280, -73.9450]),
    ('Roosevelt Island', None, 'area', [40.7620, -73.9500]),
    ('DUMBO', None, 'area', [40.7033, -73.9881]), ('Brooklyn Heights', None, 'area', [40.6960, -73.9950]),
    ('Cobble Hill', None, 'area', [40.6860, -73.9960]), ('Boerum Hill', None, 'area', [40.6850, -73.9840]),
    ('Red Hook', None, 'area', [40.6750, -74.0100]), ('Gowanus', None, 'area', [40.6730, -73.9900]),
    ('Clinton Hill', None, 'area', [40.6890, -73.9660]), ('Prospect Heights', None, 'area', [40.6770, -73.9680]),
    ('Ditmas Park', None, 'area', [40.6400, -73.9620]), ('Brighton Beach', None, 'area', [40.5780, -73.9600]),
    ('Long Island City', None, 'area', [40.7447, -73.9485]), ('Astoria', None, 'area', [40.7644, -73.9235]),
    ('Jackson Heights', None, 'area', [40.7557, -73.8831]), ('Flushing', None, 'area', [40.7580, -73.8300]),
    ('Forest Hills', None, 'area', [40.7180, -73.8450]), ('Sunnyside', None, 'area', [40.7430, -73.9200]),
    ('Arthur Avenue', 'Belmont', 'area', [40.8550, -73.8880]), ('Riverdale', None, 'area', [40.8900, -73.9120]),
    ('City Island', None, 'area', [40.8470, -73.7860]), ('Mott Haven', None, 'area', [40.8090, -73.9230]),
    ('St. George', 'Saint George', 'area', [40.6430, -74.0770]),
]]

# Curated landmarks: the places New Yorkers give directions by. 'osm' is the OpenStreetMap name to snap to.
L_ = lambda name, cat, tier, at, aliases=(), osm=None: {'name': name, 'osm': osm or name, 'cat': cat, 'tier': tier, 'at': at, 'aliases': list(aliases)}
LANDMARKS = [
    # Sports
    L_('Madison Square Garden', 'sports', 1, (40.7505, -73.9934), ['MSG', 'The Garden', 'Knicks', 'Rangers']),
    L_('Yankee Stadium', 'sports', 1, (40.8296, -73.9262), ['Yankees']),
    L_('Citi Field', 'sports', 1, (40.7571, -73.8458), ['Mets']),
    L_('Barclays Center', 'sports', 1, (40.6826, -73.9754), ['Nets', 'Liberty']),
    L_('USTA Billie Jean King National Tennis Center', 'sports', 2, (40.7499, -73.8462), ['US Open', 'Arthur Ashe Stadium']),
    L_('MetLife Stadium', 'sports', 2, (40.8135, -74.0745), ['Giants', 'Jets', 'Meadowlands']),
    # Parks
    L_('Central Park', 'park', 1, (40.7829, -73.9654), ['The Park']),
    L_('Prospect Park', 'park', 1, (40.6602, -73.9690), []),
    L_('The High Line', 'park', 1, (40.7480, -74.0048), ['High Line'], osm='High Line'),
    L_('Bryant Park', 'park', 2, (40.7536, -73.9832), []),
    L_('Washington Square Park', 'park', 2, (40.7308, -73.9973), ['Washington Square']),
    L_('Flushing Meadows–Corona Park', 'park', 1, (40.7400, -73.8407), ['Flushing Meadows', 'Unisphere'], osm='Flushing Meadows Corona Park'),
    L_('Brooklyn Bridge Park', 'park', 2, (40.7003, -73.9967), []),
    L_('The Bronx Zoo', 'park', 1, (40.8506, -73.8769), ['Bronx Zoo'], osm='Bronx Zoo'),
    L_('New York Botanical Garden', 'park', 2, (40.8623, -73.8803), ['NYBG', 'Botanical Garden']),
    L_('Coney Island', 'park', 1, (40.5749, -73.9859), ['Luna Park', 'Cyclone', 'Boardwalk']),
    L_('Governors Island', 'park', 2, (40.6895, -74.0168), []),
    # Culture and sights
    L_('Statue of Liberty', 'culture', 1, (40.6892, -74.0445), ['Liberty Island', 'Lady Liberty']),
    L_('Empire State Building', 'culture', 1, (40.7484, -73.9857), ['ESB']),
    L_('One World Trade Center', 'culture', 1, (40.7127, -74.0134), ['Freedom Tower', 'World Trade Center', '9/11 Memorial']),
    L_('Rockefeller Center', 'culture', 1, (40.7587, -73.9787), ['30 Rock', 'Top of the Rock']),
    L_('Times Square', 'culture', 1, (40.7580, -73.9855), ['Broadway', 'Theater District']),
    L_('Brooklyn Bridge', 'culture', 1, (40.7061, -73.9969), []),
    L_('The Metropolitan Museum of Art', 'culture', 1, (40.7794, -73.9632), ['The Met', 'Met Museum'], osm='Metropolitan Museum of Art'),
    L_('Museum of Modern Art', 'culture', 2, (40.7614, -73.9776), ['MoMA']),
    L_('American Museum of Natural History', 'culture', 2, (40.7813, -73.9740), ['AMNH', 'Natural History Museum']),
    L_('Guggenheim Museum', 'culture', 2, (40.7830, -73.9590), ['The Guggenheim'], osm='Solomon R. Guggenheim Museum'),
    L_('Brooklyn Museum', 'culture', 2, (40.6712, -73.9636), []),
    L_('Chrysler Building', 'culture', 2, (40.7516, -73.9755), []),
    L_('Flatiron Building', 'culture', 2, (40.7411, -73.9897), []),
    L_('Apollo Theater', 'music', 2, (40.8100, -73.9500), ['The Apollo']),
    L_('Lincoln Center', 'music', 1, (40.7725, -73.9835), ['Lincoln Center for the Performing Arts', 'Met Opera'], osm='Lincoln Center for the Performing Arts'),
    L_('Radio City Music Hall', 'music', 2, (40.7600, -73.9800), ['Radio City', 'Rockettes']),
    L_('Carnegie Hall', 'music', 2, (40.7651, -73.9799), []),
    # Civic and transport
    L_('Grand Central Terminal', 'civic', 1, (40.7527, -73.9772), ['Grand Central', 'Metro-North']),
    L_('Penn Station', 'civic', 1, (40.7506, -73.9935), ['Pennsylvania Station', 'Moynihan Train Hall', 'LIRR', 'Amtrak'], osm='Pennsylvania Station'),
    L_('Port Authority Bus Terminal', 'civic', 2, (40.7570, -73.9910), ['Port Authority', 'PABT']),
    L_('City Hall', 'civic', 2, (40.7128, -74.0060), ['New York City Hall'], osm='New York City Hall'),
    L_('Staten Island Ferry Whitehall Terminal', 'civic', 2, (40.7013, -74.0130), ['Staten Island Ferry', 'Whitehall'], osm='Whitehall Terminal'),
    L_('Javits Center', 'civic', 2, (40.7578, -74.0022), ['Jacob K. Javits Convention Center'], osm='Jacob K. Javits Convention Center'),
    L_('Hudson Yards', 'civic', 2, (40.7536, -74.0007), ['The Vessel', 'The Edge']),
    # Airports
    L_('John F. Kennedy International Airport', 'airport', 1, (40.6413, -73.7781), ['JFK', 'Kennedy']),
    L_('LaGuardia Airport', 'airport', 1, (40.7769, -73.8740), ['LGA', 'LaGuardia']),
    L_('Newark Liberty International Airport', 'airport', 1, (40.6895, -74.1745), ['EWR', 'Newark Airport']),
]

# Main streets drawn heavier (OpenStreetMap's other primary and secondary roads are drawn as minor). Keys are
# street_key() forms: no East/West prefix, so "E 42nd St" and "W 42nd St" are one street.
MAJOR_STREETS = {
    # Manhattan
    'Broadway', '1st Ave', '2nd Ave', '3rd Ave', 'Lexington Ave', 'Park Ave', 'Madison Ave', '5th Ave', '6th Ave', 'Avenue of the Americas',
    '7th Ave', '8th Ave', '9th Ave', '10th Ave', '11th Ave', '12th Ave', 'Amsterdam Ave', 'Columbus Ave', 'Central Park W', 'West End Ave',
    'York Ave', 'Houston St', 'Canal St', 'Delancey St', '14th St', '23rd St', '34th St', '42nd St', '57th St', '72nd St', '79th St', '86th St',
    '96th St', '116th St', '125th St', '145th St', '155th St', '181st St', 'Bowery', 'Chambers St', 'St Nicholas Ave', 'Frederick Douglass Blvd',
    'Adam Clayton Powell Jr Blvd', 'Malcolm X Blvd', 'Lenox Ave', 'Fort Washington Ave', 'Dyckman St', 'Riverside Dr', 'Church St',
    # Bronx
    'Grand Concourse', 'Fordham Rd', 'Jerome Ave', 'Webster Ave', 'Boston Rd', 'White Plains Rd', 'Tremont Ave', 'Southern Blvd',
    'Westchester Ave', 'Pelham Pkwy', 'Gun Hill Rd', 'Third Ave', 'Castle Hill Ave', 'Westchester Ave', 'Broadway', 'Bainbridge Ave',
    'Kingsbridge Rd', 'University Ave', 'Allerton Ave', 'Bruckner Blvd', 'E Tremont Ave', '149th St', '161st St',
    # Brooklyn
    'Atlantic Ave', 'Flatbush Ave', 'Eastern Pkwy', 'Ocean Pkwy', 'Kings Hwy', 'Bedford Ave', 'Fulton St', 'Nostrand Ave', 'Utica Ave',
    'Linden Blvd', '4th Ave', 'Church Ave', 'Myrtle Ave', 'Flushing Ave', 'Metropolitan Ave', 'Coney Island Ave', 'McDonald Ave',
    'Bay Pkwy', '86th St', 'Avenue U', 'Rockaway Pkwy', 'Pennsylvania Ave', 'Ralph Ave', 'Court St', 'Smith St', 'Nassau Ave',
    'Manhattan Ave', 'Fort Hamilton Pkwy', 'New Utrecht Ave', 'Emmons Ave', 'Surf Ave', 'Ocean Ave', 'Cropsey Ave',
    # Queens
    'Northern Blvd', 'Queens Blvd', 'Woodhaven Blvd', 'Cross Bay Blvd', 'Roosevelt Ave', 'Jamaica Ave', 'Hillside Ave', 'Union Tpke',
    'Main St', 'Francis Lewis Blvd', 'Steinway St', '21st St', 'Astoria Blvd', 'Ditmars Blvd', 'Junction Blvd', 'Kissena Blvd',
    'Merrick Blvd', 'Sutphin Blvd', 'Guy R Brewer Blvd', 'Rockaway Blvd', 'Liberty Ave', 'Springfield Blvd', 'Bell Blvd', '164th St',
    'Parsons Blvd', 'Utopia Pkwy', 'Horace Harding Expy', 'Grand Ave', 'Greenpoint Ave', 'Vernon Blvd', 'Beach Channel Dr',
    # Staten Island
    'Hylan Blvd', 'Richmond Ave', 'Victory Blvd', 'Forest Ave', 'Richmond Rd', 'Amboy Rd', 'Arthur Kill Rd', 'Bay St', 'Richmond Ter',
    'Castleton Ave', 'Targee St', 'Clove Rd', 'Arden Ave', 'Huguenot Ave',
}
ABBR = [(r'\bRoad\b', 'Rd'), (r'\bStreet\b', 'St'), (r'\bAvenue\b', 'Ave'), (r'\bBoulevard\b', 'Blvd'), (r'\bLane\b', 'Ln'),
        (r'\bDrive\b', 'Dr'), (r'\bParkway\b', 'Pkwy'), (r'\bHighway\b', 'Hwy'), (r'\bTurnpike\b', 'Tpke'), (r'\bTerrace\b', 'Ter'),
        (r'\bExpressway\b', 'Expy'), (r'\bPlace\b', 'Pl'), (r'\bNorth\b', 'N'), (r'\bSouth\b', 'S'), (r'\bEast\b', 'E'), (r'\bWest\b', 'W'),
        (r'\bFirst\b', '1st'), (r'\bSecond\b', '2nd'), (r'\bThird Avenue\b', '3rd Ave'), (r'\bFifth\b', '5th'), (r'\bSaint\b', 'St'),
        (r'\bJunior\b', 'Jr'), (r'\.', ''), (r',', '')]


def street_name(n):
    for a, b in ABBR:
        n = re.sub(a, b, n)
    return re.sub(r'\s+', ' ', n).strip()


def street_key(n):
    """The street without its East/West prefix, so "E 42nd St" and "W 42nd St" join into one main street."""
    n = street_name(n)
    return re.sub(r'^(N|S|E|W) (?=\d|[A-Z])', '', n) if not n.startswith(('E Tremont', 'W End')) else n


# Highways: OpenStreetMap name fragment -> the name New Yorkers use, and the route shown on its shield ('' for none).
HIGHWAYS = [
    ('FDR Drive', 'FDR Drive', ''), ('Franklin D. Roosevelt East River Drive', 'FDR Drive', ''), ('Harlem River Drive', 'Harlem River Drive', ''),
    ('Henry Hudson Parkway', 'Henry Hudson Parkway', '9A'), ('Joe DiMaggio Highway', 'West Side Highway', '9A'), ('West Side Highway', 'West Side Highway', '9A'),
    ('Brooklyn-Queens Expressway', 'Brooklyn–Queens Expressway (BQE)', '278'), ('Gowanus Expressway', 'Gowanus Expressway', '278'),
    ('Staten Island Expressway', 'Staten Island Expressway', '278'), ('Bruckner Expressway', 'Bruckner Expressway', '278'),
    ('Long Island Expressway', 'Long Island Expressway (LIE)', '495'), ('Queens-Midtown Expressway', 'Long Island Expressway (LIE)', '495'),
    ('Van Wyck Expressway', 'Van Wyck Expressway', '678'), ('Whitestone Expressway', 'Whitestone Expressway', '678'),
    ('Cross Bronx Expressway', 'Cross Bronx Expressway', '95'), ('Trans-Manhattan Expressway', 'Trans-Manhattan Expressway', '95'),
    ('New England Thruway', 'New England Thruway', '95'), ('Major Deegan Expressway', 'Major Deegan Expressway', '87'),
    ('Clearview Expressway', 'Clearview Expressway', '295'), ('Throgs Neck Expressway', 'Throgs Neck Expressway', '295'),
    ('Sheridan Expressway', 'Sheridan Boulevard', ''), ('Prospect Expressway', 'Prospect Expressway', '27'),
    ('Grand Central Parkway', 'Grand Central Parkway', ''), ('Belt Parkway', 'Belt Parkway', ''), ('Shore Parkway', 'Belt Parkway', ''),
    ('Southern Parkway', 'Belt Parkway', ''), ('Laurelton Parkway', 'Belt Parkway', ''), ('Cross Island Parkway', 'Cross Island Parkway', ''),
    ('Jackie Robinson Parkway', 'Jackie Robinson Parkway', ''), ('Hutchinson River Parkway', 'Hutchinson River Parkway', ''),
    ('Bronx River Parkway', 'Bronx River Parkway', ''), ('Mosholu Parkway', 'Mosholu Parkway', ''), ('Nassau Expressway', 'Nassau Expressway', '878'),
    ('West Shore Expressway', 'West Shore Expressway', '440'), ('Korean War Veterans Parkway', 'Korean War Veterans Parkway', ''),
    ('Brooklyn-Battery Tunnel', 'Hugh L. Carey Tunnel', '478'), ('Hugh L. Carey Tunnel', 'Hugh L. Carey Tunnel', '478'),
    ('Queens-Midtown Tunnel', 'Queens–Midtown Tunnel', '495'), ('Lincoln Tunnel', 'Lincoln Tunnel', '495'), ('Holland Tunnel', 'Holland Tunnel', '78'),
    ('Verrazzano', 'Verrazzano-Narrows Bridge', '278'), ('Robert F. Kennedy Bridge', 'RFK (Triborough) Bridge', '278'),
    ('Triborough', 'RFK (Triborough) Bridge', '278'), ('George Washington Bridge', 'George Washington Bridge', '95'),
    ('Bronx-Whitestone Bridge', 'Bronx–Whitestone Bridge', '678'), ('Throgs Neck Bridge', 'Throgs Neck Bridge', '295'),
    ('Arthur Kill', 'Goethals Bridge', '278'), ('Goethals Bridge', 'Goethals Bridge', '278'), ('Outerbridge Crossing', 'Outerbridge Crossing', '440'),
    ('Bayonne Bridge', 'Bayonne Bridge', '440'),
]
