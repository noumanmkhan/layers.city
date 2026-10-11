"""Vancouver's hand-kept lists: the sides, known-as names, landmarks, and how street names are written.

Sides (decided with the user, October 11, 2026): Downtown (the peninsula: Downtown, the West End and Stanley
Park), the West Side and the East Side. Ontario Street divides East from West addresses; the local areas
are grouped the way Vancouverites usually say it. Mount Pleasant and Riley Park straddle Main and Ontario
and are usually counted on the East Side.

Known-as names: places people call neighbourhoods that aren't among the City's 22 local areas. Positions
are approximate centres (lat, lon), moved to OpenStreetMap's place point when one with the same name sits
within 1 km (raw/osm_places.json, raw/osm_landmarks.json). kind: district | enclave | village

Landmarks: a short list of places Vancouverites give directions by. Universities, hospitals and skyscrapers
get their own toggles later. tier 1 = city-scale anchors (icons from zoom 11); tier 2 = from zoom 13.
"""

SIDES = {
    'Downtown': ['Downtown', 'West End'],
    'West Side': ['Arbutus Ridge', 'Dunbar-Southlands', 'Fairview', 'Kerrisdale', 'Kitsilano', 'Marpole', 'Oakridge',
                  'Shaughnessy', 'South Cambie', 'West Point Grey'],
    'East Side': ['Grandview-Woodland', 'Hastings-Sunrise', 'Kensington-Cedar Cottage', 'Killarney', 'Mount Pleasant',
                  'Renfrew-Collingwood', 'Riley Park', 'Strathcona', 'Sunset', 'Victoria-Fraserview'],
}
SIDE_INFO = {
    'Downtown': 'The peninsula: Downtown, the West End and Stanley Park.',
    'West Side': 'West of Ontario Street, from Kitsilano and Point Grey down to Marpole.',
    'East Side': 'East of Ontario Street, from Strathcona and Grandview out to Renfrew-Collingwood and Killarney.',
}

# (name, kind, lat, lon)
KNOWN_AS = [
    {'name': 'Gastown', 'kind': 'district', 'at': (49.2830, -123.1065)},
    {'name': 'Chinatown', 'kind': 'enclave', 'at': (49.2796, -123.1003)},
    {'name': 'Yaletown', 'kind': 'district', 'at': (49.2752, -123.1210)},
    {'name': 'Coal Harbour', 'kind': 'district', 'at': (49.2895, -123.1235)},
    {'name': 'Downtown Eastside', 'kind': 'district', 'at': (49.2815, -123.0950)},
    {'name': 'Davie Village', 'kind': 'village', 'at': (49.2808, -123.1330)},
    {'name': 'Railtown', 'kind': 'district', 'at': (49.2852, -123.0935)},
    {'name': 'Olympic Village', 'kind': 'district', 'at': (49.2700, -123.1110)},
    {'name': 'Fairview Slopes', 'kind': 'district', 'at': (49.2665, -123.1300)},
    {'name': 'South Granville', 'kind': 'village', 'at': (49.2600, -123.1385)},
    {'name': 'Kits Point', 'kind': 'district', 'at': (49.2740, -123.1470)},
    {'name': 'False Creek Flats', 'kind': 'district', 'at': (49.2690, -123.0920)},
    {'name': 'Commercial Drive', 'kind': 'village', 'at': (49.2700, -123.0695)},
    {'name': 'Main Street', 'kind': 'village', 'at': (49.2530, -123.1010)},
    {'name': 'Cambie Village', 'kind': 'village', 'at': (49.2530, -123.1150)},
    {'name': 'Punjabi Market', 'kind': 'enclave', 'at': (49.2190, -123.0905)},
    {'name': 'Cedar Cottage', 'kind': 'district', 'at': (49.2490, -123.0740)},
    {'name': 'Collingwood', 'kind': 'district', 'at': (49.2390, -123.0400)},
    {'name': 'Champlain Heights', 'kind': 'district', 'at': (49.2165, -123.0310)},
    {'name': 'Fraserview', 'kind': 'district', 'at': (49.2160, -123.0650)},
    {'name': 'Southlands', 'kind': 'district', 'at': (49.2240, -123.1900)},
]

# category, tier, (lat, lon), aliases; 'osm' when OpenStreetMap names it differently.
LANDMARKS = [
    # Sports
    {'name': 'BC Place', 'cat': 'sports', 'tier': 2, 'at': (49.2768, -123.1120), 'aliases': ['BC Lions', 'Whitecaps']},
    {'name': 'Rogers Arena', 'cat': 'sports', 'tier': 2, 'at': (49.2778, -123.1089), 'aliases': ['GM Place', 'General Motors Place', 'Canucks']},
    {'name': 'Nat Bailey Stadium', 'cat': 'sports', 'tier': 2, 'at': (49.2433, -123.1053), 'aliases': ['Canadians', 'The Nat']},
    {'name': 'Pacific Coliseum', 'cat': 'sports', 'tier': 2, 'at': (49.2856, -123.0430), 'aliases': ['PNE Coliseum']},
    # Parks and beaches
    {'name': 'Stanley Park', 'cat': 'park', 'tier': 1, 'at': (49.3017, -123.1417), 'aliases': ['Seawall']},
    {'name': 'Queen Elizabeth Park', 'cat': 'park', 'tier': 1, 'at': (49.2418, -123.1126), 'aliases': ['QE Park', 'Bloedel Conservatory', 'Little Mountain']},
    {'name': 'VanDusen Botanical Garden', 'cat': 'park', 'tier': 2, 'at': (49.2389, -123.1309), 'aliases': ['VanDusen']},
    {'name': 'Kitsilano Beach', 'cat': 'park', 'tier': 2, 'at': (49.2737, -123.1544), 'aliases': ['Kits Beach', 'Kits Pool']},
    {'name': 'English Bay Beach', 'cat': 'park', 'tier': 2, 'at': (49.2863, -123.1430), 'aliases': ['English Bay', 'First Beach']},
    {'name': 'Jericho Beach', 'cat': 'park', 'tier': 2, 'at': (49.2727, -123.1980), 'aliases': ['Jericho Beach Park']},
    {'name': 'Trout Lake', 'cat': 'park', 'tier': 2, 'at': (49.2559, -123.0626), 'aliases': ['John Hendry Park']},
    {'name': 'Dr. Sun Yat-Sen Classical Chinese Garden', 'cat': 'park', 'tier': 2, 'at': (49.2797, -123.1040), 'aliases': ['Sun Yat-Sen Garden', 'Chinese Garden']},
    # Music and theatre
    {'name': 'Orpheum', 'cat': 'music', 'tier': 2, 'at': (49.2799, -123.1205), 'aliases': ['Orpheum Theatre', 'Vancouver Symphony', 'VSO']},
    {'name': 'Queen Elizabeth Theatre', 'cat': 'music', 'tier': 2, 'at': (49.2806, -123.1135), 'aliases': ['QET', 'Vancouver Opera']},
    {'name': 'Commodore Ballroom', 'cat': 'music', 'tier': 2, 'at': (49.2806, -123.1229), 'aliases': ['The Commodore']},
    # Civic and transport
    {'name': 'Vancouver City Hall', 'cat': 'civic', 'tier': 2, 'at': (49.2610, -123.1139), 'aliases': ['City Hall']},
    {'name': 'Canada Place', 'cat': 'civic', 'tier': 2, 'at': (49.2888, -123.1111), 'aliases': ['Vancouver Convention Centre', 'Cruise ship terminal', 'FlyOver Canada']},
    {'name': 'Waterfront Station', 'cat': 'civic', 'tier': 2, 'at': (49.2856, -123.1116), 'aliases': ['Waterfront', 'SeaBus terminal', 'CPR Station']},
    {'name': 'Pacific Central Station', 'cat': 'civic', 'tier': 2, 'at': (49.2733, -123.0980), 'aliases': ['Amtrak', 'VIA Rail', 'Main Street station']},
    {'name': 'Central Library', 'cat': 'civic', 'tier': 2, 'at': (49.2797, -123.1157), 'aliases': ['Vancouver Public Library', 'VPL Central', 'Library Square'], 'osm': 'Vancouver Public Library Central Branch'},
    # Museums and sights
    {'name': 'Vancouver Art Gallery', 'cat': 'culture', 'tier': 2, 'at': (49.2829, -123.1205), 'aliases': ['VAG', 'Robson Square']},
    {'name': 'Science World', 'cat': 'culture', 'tier': 2, 'at': (49.2734, -123.1038), 'aliases': ['Telus World of Science', 'The golf ball']},
    {'name': 'Museum of Vancouver', 'cat': 'culture', 'tier': 2, 'at': (49.2763, -123.1446), 'aliases': ['MOV', 'H.R. MacMillan Space Centre', 'Space Centre', 'Vanier Park']},
    {'name': 'Vancouver Aquarium', 'cat': 'culture', 'tier': 2, 'at': (49.3007, -123.1309), 'aliases': ['Aquarium']},
    {'name': 'Granville Island', 'cat': 'culture', 'tier': 1, 'at': (49.2712, -123.1340), 'aliases': ['Granville Island Public Market', 'Public Market']},
    {'name': 'Gastown Steam Clock', 'cat': 'culture', 'tier': 2, 'at': (49.2844, -123.1089), 'aliases': ['Steam Clock']},
    {'name': 'Harbour Centre', 'cat': 'culture', 'tier': 2, 'at': (49.2847, -123.1117), 'aliases': ['Vancouver Lookout', 'The Lookout']},
    {'name': 'PNE and Playland', 'cat': 'culture', 'tier': 2, 'at': (49.2820, -123.0412), 'aliases': ['PNE', 'Playland', 'Pacific National Exhibition', 'Hastings Park'], 'osm': 'Playland'},
    # Airport (in Richmond, outside the city)
    {'name': 'Vancouver Airport', 'cat': 'airport', 'tier': 1, 'at': (49.1939, -123.1844), 'aliases': ['YVR', 'Vancouver International Airport'], 'osm': 'Vancouver International Airport'},
]
for k in KNOWN_AS: k.setdefault('osm', k['name'])

# Street names as Vancouver writes them on signs: a short direction before, a short suffix after
# ("West Broadway" -> "W Broadway", "East 41st Avenue" -> "E 41st Ave").
DIRS = {'West': 'W', 'East': 'E', 'North': 'N', 'South': 'S', 'Southwest': 'SW', 'Southeast': 'SE', 'Northwest': 'NW', 'Northeast': 'NE'}
SUFFIX = {'Avenue': 'Ave', 'Street': 'St', 'Road': 'Rd', 'Boulevard': 'Blvd', 'Drive': 'Dr', 'Parkway': 'Pkwy',
          'Highway': 'Hwy', 'Place': 'Pl', 'Crescent': 'Cres', 'Diversion': 'Diversion', 'Way': 'Way'}


def street_name(s):
    w = s.split()
    if len(w) > 1 and w[0] in DIRS:
        w[0] = DIRS[w[0]]
    if w and w[-1] in SUFFIX:
        w[-1] = SUFFIX[w[-1]]
    return ' '.join(w)


def street_key(s):
    """The street without its E/W prefix: West and East Broadway are one main street."""
    w = street_name(s).split()
    return ' '.join(w[1:]) if len(w) > 1 and w[0] in ('W', 'E') else ' '.join(w)


# The streets people navigate by. Everything else OpenStreetMap tags trunk, primary or secondary inside the
# city is drawn as a minor street; tertiary roads become collectors.
MAJOR_STREETS = {
    # east-west, north to south
    'Hastings St', 'Georgia St', 'Robson St', 'Davie St', 'Pacific St', 'Pender St', 'Powell St', 'Venables St', 'Prior St',
    '1st Ave', '4th Ave', 'Broadway', '12th Ave', '16th Ave', 'King Edward Ave', '33rd Ave', '41st Ave',
    '49th Ave', '57th Ave', 'SW Marine Dr', 'SE Marine Dr', 'Kingsway', 'Grandview Hwy', 'Terminal Ave',
    # north-south, west to east
    'Blanca St', 'Dunbar St', 'Mackenzie St', 'Arbutus St', 'Macdonald St', 'Granville St', 'Oak St', 'Cambie St',
    'Main St', 'Fraser St', 'Knight St', 'Victoria Dr', 'Commercial Dr', 'Nanaimo St', 'Renfrew St', 'Rupert St',
    'Boundary Rd', 'Burrard St', 'Denman St', 'Clark Dr', 'Quebec St',
}
