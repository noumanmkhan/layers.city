"""Hyderabad's curated lists: the districts the map covers, known-as names and landmarks.
Deliberately short. Positions are approximate; build.py and landmarks.py move each to OpenStreetMap's point of the
same name when one is close by (raw/osm_places.json, raw/osm_landmarks.json)."""

# The four revenue districts the city spans. The regional view covers every mandal in them.
DISTRICTS = ['Hyderabad', 'Medchal–Malkajgiri', 'Ranga Reddy', 'Sangareddy']
DISTRICT_INFO = {
    'Hyderabad': 'The old city and the core: the only district that is all city, from Charminar to Secunderabad',
    'Medchal–Malkajgiri': 'The north and east: Kukatpally, Malkajgiri, Uppal and out past Medchal',
    'Ranga Reddy': 'The west and south: the IT corridor, the airport and a long rural belt beyond the Outer Ring Road',
    'Sangareddy': 'The north-west edge: Patancheru, Ameenpur and Tellapur, then farmland to the Karnataka border',
}

# Names people give directions by that aren't mandals: localities and areas. (name, OSM name or None, at)
# Places that share a mandal's name (Kukatpally, Ameerpet, Uppal, Secunderabad…) are left out: the mandal label already shows.
KNOWN_AS = [{'name': n, 'osm': o or n, 'kind': 'area', 'at': at} for n, o, at in [
    ('HITEC City', None, [17.4474, 78.3762]), ('Financial District', None, [17.4166, 78.3416]),
    ('Gachibowli', None, [17.4401, 78.3489]), ('Madhapur', None, [17.4483, 78.3915]), ('Kondapur', None, [17.4600, 78.3640]),
    ('Miyapur', None, [17.4968, 78.3614]), ('Manikonda', None, [17.4050, 78.3860]),
    ('Kokapet', None, [17.3970, 78.3370]), ('Nallagandla', None, [17.4700, 78.3100]), ('Tellapur', None, [17.4640, 78.2850]),
    ('Jubilee Hills', None, [17.4325, 78.4071]), ('Banjara Hills', None, [17.4156, 78.4347]), ('Film Nagar', None, [17.4140, 78.4070]),
    ('Yousufguda', None, [17.4350, 78.4270]), ('Sanath Nagar', None, [17.4560, 78.4430]),
    ('Begumpet', None, [17.4447, 78.4664]), ('Sindhi Colony', None, [17.4420, 78.4720]), ('Somajiguda', None, [17.4240, 78.4580]),
    ('Panjagutta', 'Punjagutta', [17.4260, 78.4500]), ('Lakdikapul', 'Lakdi-ka-pul', [17.4030, 78.4630]),
    ('Masab Tank', None, [17.4010, 78.4520]), ('Mehdipatnam', None, [17.3950, 78.4390]), ('Tolichowki', None, [17.3960, 78.4150]),
    ('Attapur', None, [17.3720, 78.4280]), ('Abids', None, [17.3930, 78.4770]),
    ('Koti', None, [17.3850, 78.4860]), ('Old City', None, [17.3570, 78.4760]),
    ('Falaknuma', None, [17.3320, 78.4680]), ('Malakpet', None, [17.3730, 78.5030]), ('Dilsukhnagar', 'Dilsukh Nagar', [17.3687, 78.5247]),
    ('LB Nagar', None, [17.3480, 78.5520]), ('Habsiguda', None, [17.4180, 78.5430]),
    ('Tarnaka', None, [17.4280, 78.5370]), ('Bowenpally', None, [17.4730, 78.4870]),
    ('Sainikpuri', None, [17.4930, 78.5530]), ('ECIL', None, [17.4700, 78.5720]),
    ('Kompally', None, [17.5360, 78.4870]),
]]

CAT_LABEL = {'culture': 'Heritage site or sight', 'park': 'Park', 'sports': 'Stadium', 'campus': 'University',
             'civic': 'Civic and transport', 'airport': 'Airport', 'music': 'Arts venue'}


def L_(name, cat, tier, at, aliases=(), osm=None):
    return {'name': name, 'cat': cat, 'tier': tier, 'at': at, 'aliases': list(aliases), 'osm': osm or name}


LANDMARKS = [
    # Heritage and sights
    L_('Charminar', 'culture', 1, (17.3616, 78.4747)),
    L_('Golconda Fort', 'culture', 1, (17.3833, 78.4011), ['Golkonda']),
    L_('Qutb Shahi Tombs', 'culture', 2, (17.3946, 78.3956), ['Seven Tombs']),
    L_('Mecca Masjid', 'culture', 2, (17.3604, 78.4736)),
    L_('Chowmahalla Palace', 'culture', 2, (17.3578, 78.4717)),
    L_('Falaknuma Palace', 'culture', 2, (17.3310, 78.4675)),
    L_('Salar Jung Museum', 'culture', 1, (17.3713, 78.4804)),
    L_('Paigah Tombs', 'culture', 2, (17.3390, 78.4970)),
    L_('Buddha Statue', 'culture', 2, (17.4156, 78.4746), ['Hussain Sagar Buddha']),
    L_('Birla Mandir', 'culture', 2, (17.4062, 78.4691)),
    L_('Shilparamam', 'culture', 2, (17.4526, 78.3810)),
    L_('Durgam Cheruvu Cable Bridge', 'culture', 2, (17.4300, 78.3880), ['Cable Bridge'], osm='Durgam Cheruvu Bridge'),
    L_('Ramoji Film City', 'culture', 2, (17.2543, 78.6808)),
    # Parks
    L_('Nehru Zoological Park', 'park', 2, (17.3509, 78.4515), ['Hyderabad Zoo']),
    L_('KBR National Park', 'park', 2, (17.4210, 78.4200), ['Kasu Brahmananda Reddy National Park']),
    L_('Lumbini Park', 'park', 2, (17.4100, 78.4730)),
    L_('Sanjeevaiah Park', 'park', 2, (17.4310, 78.4840)),
    # Arts
    L_('Ravindra Bharathi', 'music', 2, (17.4040, 78.4650)),
    # Stadiums
    L_('Rajiv Gandhi International Cricket Stadium', 'sports', 1, (17.4065, 78.5505), ['Uppal Stadium']),
    L_('Lal Bahadur Shastri Stadium', 'sports', 2, (17.3990, 78.4730), ['LB Stadium', 'Fateh Maidan']),
    L_('Gachibowli Stadium', 'sports', 2, (17.4470, 78.3430), ['G.M.C. Balayogi Athletic Stadium'], osm='G.M.C. Balayogi Athletic Stadium'),
    # Universities
    L_('Osmania University', 'campus', 1, (17.4130, 78.5280), ['OU']),
    L_('University of Hyderabad', 'campus', 2, (17.4580, 78.3250), ['HCU', 'Central University']),
    L_('IIT Hyderabad', 'campus', 2, (17.5940, 78.1230), ['Indian Institute of Technology Hyderabad'], osm='Indian Institute of Technology Hyderabad'),
    # Civic and transport
    L_('Telangana Secretariat', 'civic', 2, (17.4080, 78.4700), osm='Dr. B.R. Ambedkar Telangana State Secretariat'),
    L_('Telangana Legislative Assembly', 'civic', 2, (17.4005, 78.4672), ['Assembly']),
    L_('Secunderabad Junction', 'civic', 1, (17.4339, 78.5016), ['Secunderabad station']),
    L_('Hyderabad Deccan station', 'civic', 2, (17.3923, 78.4675), ['Nampally station'], osm='Hyderabad Deccan'),
    L_('Kacheguda station', 'civic', 2, (17.3890, 78.4990), osm='Kacheguda'),
    L_('MGBS bus station', 'civic', 2, (17.3780, 78.4840), ['Mahatma Gandhi Bus Station', 'Imlibun'], osm='Mahatma Gandhi Bus Station'),
    L_('JBS bus station', 'civic', 2, (17.4500, 78.4990), ['Jubilee Bus Station'], osm='Jubilee Bus Station'),
    L_('Rajiv Gandhi International Airport', 'airport', 1, (17.2403, 78.4294), ['Shamshabad airport', 'HYD']),
]

# Lakes labelled on the map: (name, at, near or far)
WATER_LABELS = [('Hussain Sagar', [17.4239, 78.4738], 'lake-near'), ('Osman Sagar', [17.3830, 78.3000], 'lake-far'),
                ('Himayat Sagar', [17.3150, 78.3750], 'lake-far'), ('Shamirpet Lake', [17.6000, 78.5650], 'lake-far')]

# Districts beyond the four, labelled on the land around the region: (name, [lon, lat]). A point inside the region is skipped.
BEYOND = [('Yadadri Bhuvanagiri district', [79.0, 17.5]), ('Siddipet district', [78.75, 18.15]), ('Nalgonda district', [79.05, 16.95]),
          ('Nagarkurnool district', [78.55, 16.66]), ('Mahabubnagar district', [77.85, 16.7]), ('Bidar district, Karnataka', [77.35, 17.95]),
          ('Kamareddy district', [78.15, 18.38])]
