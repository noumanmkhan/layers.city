# Chicago community area badges

One-colour drawings (viewBox 0 0 240 120; classes m ink, k knockout, ms/ks strokes), one per community area, named
by its slug. engine/badges.py chicago places each inside its community area. Public buildings, transit and landscape
only: no logos, signage or anyone's artwork (so no Cloud Gate, murals or ballpark signs). Each drawing shows what is
inside its own community area (checked against the polygons November 7, 2026): the Museum of Science and Industry is
in Hyde Park, the Chinatown Gate in Armour Square, Union Station in the Near West Side, Montrose Harbor in Uptown,
St. Adalbert in the Lower West Side; Humboldt Park's boathouse falls in West Town's polygon, so it has none.
To add one: drop <slug>.svg here, run python3 engine/badges.py chicago, then assemble.
