"""Melbourne's hand-kept lists: the sides, known-as names, landmarks, and how street names are written.

Units (decided with the user, November 12, 2026: the San Francisco shape): the suburbs of the City of Melbourne
(ABS Suburbs and Localities 2021, cut to the City's boundary) in full detail, inside a Greater Melbourne view whose
other suburbs are grouped by council. The ABS locality "Melbourne" covers both the CBD (3000) and the St Kilda Road
precinct south of the Yarra (3004); build.py splits it at the river, because Melburnians treat them as two places.

Sides: the Yarra is the line Melburnians draw ("north of the river", "south of the river"). The City is split three
ways: the city centre (the CBD and the waterfront districts around it), the inner north and the inner south.

Known-as names: places people name that aren't suburbs. Positions are approximate (lat, lon), moved to
OpenStreetMap's place point when one with the same name sits within 1 km. kind: district | enclave | village

Landmarks: a short list of places Melburnians give directions by. tier 1 = city-scale anchors (from zoom 11);
tier 2 = from zoom 13.
"""

CBD, ST_KILDA_RD = 'Melbourne CBD', 'St Kilda Road'
SIDES = {
    'City centre': [CBD, 'Docklands', 'Southbank', 'South Wharf', 'East Melbourne'],
    'North of the river': ['Carlton', 'Carlton North', 'Parkville', 'North Melbourne', 'West Melbourne', 'Kensington', 'Flemington'],
    'South of the river': [ST_KILDA_RD, 'South Yarra', 'Port Melbourne'],
}
SIDE_INFO = {
    'City centre': 'The CBD’s Hoddle Grid, Docklands, Southbank and East Melbourne.',
    'North of the river': 'Carlton, Parkville and North Melbourne out to Kensington and Flemington.',
    'South of the river': 'St Kilda Road, the City’s part of South Yarra and the Fishermans Bend employment precinct.',
}
# Units shown with a note rather than as places people live.
UNIT_NOTES = {
    'Port Melbourne': 'only the City’s piece: the Fishermans Bend employment precinct, west of the West Gate Freeway',
    'South Yarra': 'only the City’s piece, west of Punt Road; the rest is in the City of Stonnington',
    'Carlton North': 'only the City’s piece; most of Carlton North is in the City of Yarra',
    'Flemington': 'the City’s piece: the racecourse and the streets around it',
}
UNIT_AKA = {
    CBD: ['CBD', 'Melbourne', 'Hoddle Grid', 'the city'],
    ST_KILDA_RD: ['Melbourne 3004', 'St Kilda Rd'],
    'Docklands': ['Melbourne Docklands'],
}

KNOWN_AS = [
    {'name': 'Chinatown', 'kind': 'enclave', 'at': (-37.8113, 144.9688)},
    {'name': 'Greek Precinct', 'kind': 'enclave', 'at': (-37.8104, 144.9657), 'osm': 'Greek Precinct'},
    {'name': 'Paris End', 'kind': 'district', 'at': (-37.8139, 144.9722)},
    {'name': 'Bourke Street Mall', 'kind': 'district', 'at': (-37.8137, 144.9642)},
    {'name': 'Degraves Street', 'kind': 'village', 'at': (-37.8170, 144.9656)},
    {'name': 'Lygon Street', 'kind': 'village', 'at': (-37.7985, 144.9672)},
    {'name': 'Errol Street', 'kind': 'village', 'at': (-37.8031, 144.9493)},
    {'name': 'Arts Precinct', 'kind': 'district', 'at': (-37.8226, 144.9686)},
    {'name': 'NewQuay', 'kind': 'district', 'at': (-37.8136, 144.9392)},
    {'name': 'Victoria Harbour', 'kind': 'district', 'at': (-37.8197, 144.9420)},
    {'name': "Yarra's Edge", 'kind': 'district', 'at': (-37.8247, 144.9450)},
    {'name': 'Arden', 'kind': 'district', 'at': (-37.7988, 144.9420)},
    {'name': 'Fishermans Bend', 'kind': 'district', 'at': (-37.8285, 144.9230)},
    {'name': 'Queens Road', 'kind': 'district', 'at': (-37.8390, 144.9770)},
]

# category, tier, (lat, lon), aliases; 'osm' when OpenStreetMap names it differently.
LANDMARKS = [
    # Sports
    {'name': 'MCG', 'cat': 'sports', 'tier': 1, 'at': (-37.8200, 144.9834), 'aliases': ['Melbourne Cricket Ground', 'The G', 'Boxing Day Test', 'AFL Grand Final'], 'osm': 'Melbourne Cricket Ground'},
    {'name': 'Marvel Stadium', 'cat': 'sports', 'tier': 2, 'at': (-37.8165, 144.9475), 'aliases': ['Docklands Stadium', 'Etihad Stadium']},
    {'name': 'Rod Laver Arena', 'cat': 'sports', 'tier': 2, 'at': (-37.8217, 144.9785), 'aliases': ['Melbourne Park', 'Australian Open']},
    {'name': 'AAMI Park', 'cat': 'sports', 'tier': 2, 'at': (-37.8251, 144.9837), 'aliases': ['Melbourne Rectangular Stadium', 'Storm', 'Victory']},
    {'name': 'Flemington Racecourse', 'cat': 'sports', 'tier': 2, 'at': (-37.7890, 144.9120), 'aliases': ['Melbourne Cup', 'Flemington']},
    {'name': 'Ikon Park', 'cat': 'sports', 'tier': 2, 'at': (-37.7840, 144.9617), 'aliases': ['Princes Park', 'Carlton Football Club']},
    {'name': 'Albert Park Circuit', 'cat': 'sports', 'tier': 2, 'at': (-37.8497, 144.9690), 'aliases': ['Grand Prix', 'Albert Park Lake', 'Formula 1'], 'osm': 'Albert Park Lake'},
    # Parks and gardens
    {'name': 'Royal Botanic Gardens', 'cat': 'park', 'tier': 1, 'at': (-37.8304, 144.9796), 'aliases': ['Botanic Gardens', 'Botanical Gardens', 'Tan Track', 'The Tan'], 'osm': 'Royal Botanic Gardens Victoria'},
    {'name': 'Fitzroy Gardens', 'cat': 'park', 'tier': 2, 'at': (-37.8131, 144.9800), 'aliases': ["Cooks' Cottage", 'Captain Cook’s Cottage']},
    {'name': 'Carlton Gardens', 'cat': 'park', 'tier': 2, 'at': (-37.8050, 144.9710), 'aliases': ['Royal Exhibition Building gardens']},
    {'name': 'Flagstaff Gardens', 'cat': 'park', 'tier': 2, 'at': (-37.8105, 144.9545), 'aliases': ['Flagstaff']},
    {'name': 'Birrarung Marr', 'cat': 'park', 'tier': 2, 'at': (-37.8183, 144.9735), 'aliases': ['Birrarung', 'Federation Bells']},
    {'name': 'Royal Park', 'cat': 'park', 'tier': 1, 'at': (-37.7880, 144.9530), 'aliases': ['Royal Park Wetlands']},
    {'name': 'Melbourne Zoo', 'cat': 'park', 'tier': 2, 'at': (-37.7841, 144.9515), 'aliases': ['Zoo', 'Royal Melbourne Zoological Gardens']},
    {'name': 'Sidney Myer Music Bowl', 'cat': 'music', 'tier': 2, 'at': (-37.8231, 144.9733), 'aliases': ['Music Bowl', 'The Bowl']},
    {'name': 'St Kilda Beach', 'cat': 'park', 'tier': 2, 'at': (-37.8670, 144.9740), 'aliases': ['St Kilda', 'St Kilda Pier', 'Luna Park']},
    # Music and theatre
    {'name': 'Arts Centre Melbourne', 'cat': 'music', 'tier': 2, 'at': (-37.8213, 144.9688), 'aliases': ['Arts Centre', 'The Spire', 'Hamer Hall', 'State Theatre']},
    {'name': 'Melbourne Recital Centre', 'cat': 'music', 'tier': 2, 'at': (-37.8241, 144.9675), 'aliases': ['Recital Centre']},
    {'name': 'Forum Melbourne', 'cat': 'music', 'tier': 2, 'at': (-37.8162, 144.9692), 'aliases': ['Forum Theatre', 'The Forum']},
    {'name': 'Regent Theatre', 'cat': 'music', 'tier': 2, 'at': (-37.8150, 144.9671), 'aliases': ['The Regent']},
    {'name': 'Princess Theatre', 'cat': 'music', 'tier': 2, 'at': (-37.8105, 144.9724), 'aliases': ['The Princess']},
    {'name': "Her Majesty's Theatre", 'cat': 'music', 'tier': 2, 'at': (-37.8113, 144.9696), 'aliases': ['Her Maj']},
    # Civic and transport
    {'name': 'Flinders Street Station', 'cat': 'civic', 'tier': 1, 'at': (-37.8183, 144.9671), 'aliases': ['Flinders Street', 'Under the clocks', 'Flinders St Station']},
    {'name': 'Southern Cross Station', 'cat': 'civic', 'tier': 1, 'at': (-37.8184, 144.9525), 'aliases': ['Spencer Street Station', 'SkyBus', 'V/Line', 'Southern Cross']},
    {'name': 'Federation Square', 'cat': 'civic', 'tier': 1, 'at': (-37.8180, 144.9691), 'aliases': ['Fed Square', 'ACMI']},
    {'name': 'Melbourne Town Hall', 'cat': 'civic', 'tier': 2, 'at': (-37.8150, 144.9665), 'aliases': ['Town Hall']},
    {'name': 'Parliament House', 'cat': 'civic', 'tier': 2, 'at': (-37.8110, 144.9735), 'aliases': ['Parliament of Victoria', 'Spring Street'], 'osm': 'Parliament House'},
    {'name': 'State Library Victoria', 'cat': 'civic', 'tier': 2, 'at': (-37.8098, 144.9652), 'aliases': ['State Library', 'La Trobe Reading Room']},
    {'name': 'Queen Victoria Market', 'cat': 'civic', 'tier': 1, 'at': (-37.8076, 144.9568), 'aliases': ['Vic Market', 'Queen Vic Market', 'QVM']},
    {'name': 'Melbourne Central', 'cat': 'civic', 'tier': 2, 'at': (-37.8102, 144.9628), 'aliases': ['Shot Tower', 'Melbourne Central Station']},
    {'name': 'Melbourne Convention and Exhibition Centre', 'cat': 'civic', 'tier': 2, 'at': (-37.8255, 144.9535), 'aliases': ['MCEC', 'Jeff’s Shed', 'Convention Centre']},
    {'name': 'Shrine of Remembrance', 'cat': 'civic', 'tier': 1, 'at': (-37.8305, 144.9735), 'aliases': ['The Shrine', 'Anzac Day']},
    {'name': 'Crown Melbourne', 'cat': 'civic', 'tier': 2, 'at': (-37.8235, 144.9580), 'aliases': ['Crown', 'Crown Casino']},
    # Museums and sights
    {'name': 'National Gallery of Victoria', 'cat': 'culture', 'tier': 2, 'at': (-37.8226, 144.9689), 'aliases': ['NGV', 'NGV International'], 'osm': 'NGV International'},
    {'name': 'Melbourne Museum', 'cat': 'culture', 'tier': 2, 'at': (-37.8033, 144.9717), 'aliases': ['IMAX Melbourne']},
    {'name': 'Royal Exhibition Building', 'cat': 'culture', 'tier': 2, 'at': (-37.8047, 144.9717), 'aliases': ['Exhibition Building', 'World Heritage']},
    {'name': 'Immigration Museum', 'cat': 'culture', 'tier': 2, 'at': (-37.8193, 144.9603), 'aliases': ['Old Customs House']},
    {'name': 'Old Melbourne Gaol', 'cat': 'culture', 'tier': 2, 'at': (-37.8078, 144.9653), 'aliases': ['Melbourne Gaol', 'Ned Kelly']},
    {'name': 'Eureka Skydeck', 'cat': 'culture', 'tier': 2, 'at': (-37.8214, 144.9645), 'aliases': ['Eureka Tower', 'Skydeck']},
    {'name': 'Hosier Lane', 'cat': 'culture', 'tier': 2, 'at': (-37.8166, 144.9692), 'aliases': ['Street art lane', 'Graffiti lane', 'AC/DC Lane']},
    {'name': 'SEA LIFE Melbourne Aquarium', 'cat': 'culture', 'tier': 2, 'at': (-37.8209, 144.9583), 'aliases': ['Melbourne Aquarium', 'Aquarium']},
    {'name': 'Scienceworks', 'cat': 'culture', 'tier': 2, 'at': (-37.8317, 144.8919), 'aliases': ['Melbourne Planetarium']},
    {'name': 'University of Melbourne', 'cat': 'culture', 'tier': 2, 'at': (-37.7983, 144.9610), 'aliases': ['Melbourne Uni', 'UniMelb', 'Parkville campus']},
    # Airports (outside the City)
    {'name': 'Melbourne Airport', 'cat': 'airport', 'tier': 1, 'at': (-37.6690, 144.8410), 'aliases': ['Tullamarine', 'MEL', 'Tulla']},
    {'name': 'Avalon Airport', 'cat': 'airport', 'tier': 2, 'at': (-38.0394, 144.4694), 'aliases': ['AVV', 'Avalon']},
]
for k in KNOWN_AS: k.setdefault('osm', k['name'])

# Street names as Melbourne writes them on signs: a short suffix ("Collins Street" -> "Collins St").
SUFFIX = {'Street': 'St', 'Road': 'Rd', 'Avenue': 'Ave', 'Parade': 'Pde', 'Esplanade': 'Esp', 'Boulevard': 'Blvd',
          'Highway': 'Hwy', 'Freeway': 'Fwy', 'Place': 'Pl', 'Crescent': 'Cres', 'Drive': 'Dr', 'Terrace': 'Tce',
          'Promenade': 'Prom', 'Grove': 'Gr', 'Square': 'Sq', 'Court': 'Ct'}


def street_name(s):
    w = s.split()
    if len(w) > 1 and w[-1] in SUFFIX:
        w[-1] = SUFFIX[w[-1]]
    return ' '.join(w)


street_key = street_name

# The streets people navigate by inside the City. Everything else OpenStreetMap tags trunk, primary or secondary
# there is drawn as a minor street; tertiary roads become collectors.
MAJOR_STREETS = {
    # the Hoddle Grid, south to north and west to east
    'Flinders St', 'Collins St', 'Bourke St', 'Lonsdale St', 'La Trobe St',
    'Spencer St', 'King St', 'William St', 'Queen St', 'Elizabeth St', 'Swanston St', 'Russell St', 'Exhibition St', 'Spring St',
    # around it
    'St Kilda Rd', 'Kings Way', 'City Rd', 'Clarendon St', 'Alexandra Ave', 'Batman Ave', 'Wellington Pde',
    'Victoria Pde', 'Victoria St', 'Peel St', 'Flemington Rd', 'Racecourse Rd', 'Mount Alexander Rd', 'Macaulay Rd',
    'Dynon Rd', 'Footscray Rd', 'Harbour Esp', 'Wurundjeri Way', 'Docklands Dr', 'Lorimer St', 'Grattan St',
    'Royal Pde', 'Lygon St', 'Rathdowne St', 'Nicholson St', 'Elgin St', 'Punt Rd', 'Hoddle St', 'Toorak Rd',
    'Domain Rd', 'Dudley St', 'Arden St', 'Smithfield Rd', 'Epsom Rd', 'Montague St', 'Normanby Rd', 'Whiteman St',
}
