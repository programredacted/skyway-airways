"""Destination posters and what to do when you land.

One entry per airport we serve. `motif` picks which stylised scene the poster
draws (see templates/_poster.html); `palette` recolours it. Kept deliberately
short — a poster and four things worth doing, not a guidebook.
"""

DESTINATIONS = {
    "JFK": {
        "city": "New York",
        "region": "New York, U.S.A.",
        "tagline": "The island that never sits still",
        "motif": "skyline",
        "palette": ("#1b3a5c", "#e0a52e", "#c1541f"),
        "things": [
            ("Ride to the top", "The observation deck at dusk, when the grid lights up all at once."),
            ("Walk the park", "Enter at 59th and keep walking until the traffic noise disappears."),
            ("Catch a set", "Basement jazz clubs in the Village start late and finish later."),
            ("Eat standing up", "A slice, folded, on the sidewalk. This is the correct way."),
        ],
    },
    "LAX": {
        "city": "Los Angeles",
        "region": "California, U.S.A.",
        "tagline": "Sunshine and open road",
        "motif": "surf",
        "palette": ("#2b7fa8", "#f0b429", "#d4622a"),
        "things": [
            ("Drive the coast", "The highway north out of Santa Monica, roof down, no particular hurry."),
            ("Beach morning", "Venice before nine, while the sand still belongs to the swimmers."),
            ("Studio tour", "See how the backlot turns plywood into anywhere in the world."),
            ("Hills at sunset", "Park up above the basin and watch the lights come on for miles."),
        ],
    },
    "SFO": {
        "city": "San Francisco",
        "region": "California, U.S.A.",
        "tagline": "Fog, hills and the great red bridge",
        "motif": "bridge",
        "palette": ("#2f5f7a", "#e05a34", "#f0c46a"),
        "things": [
            ("Cross the bridge", "On foot, into the fog, with the cables humming overhead."),
            ("Ride the cable car", "Hang off the running board up Powell and hold on properly."),
            ("Wharf breakfast", "Sourdough and crab, eaten outdoors in a sea breeze."),
            ("Wine country", "An hour north: vineyards, oak barrels and a long lunch."),
        ],
    },
    "ORD": {
        "city": "Chicago",
        "region": "Illinois, U.S.A.",
        "tagline": "Broad shoulders on a big lake",
        "motif": "skyline",
        "palette": ("#20455f", "#d9a227", "#a8451a"),
        "things": [
            ("Architecture cruise", "The river route, where the whole skyline leans over you."),
            ("Lakefront mile", "Walk north along the water until the towers turn into beach."),
            ("Blues on the South Side", "Small rooms, loud amplifiers, no set finishing time."),
            ("Deep dish", "Order it, wait the forty minutes, understand why."),
        ],
    },
    "MIA": {
        "city": "Miami",
        "region": "Florida, U.S.A.",
        "tagline": "Pastel evenings on the water",
        "motif": "surf",
        "palette": ("#1f7d8c", "#f2c14e", "#e8734a"),
        "things": [
            ("Ocean Drive", "Neon, pastel facades and a lot of people watching each other."),
            ("Everglades run", "Flat water, tall grass and birds you have never seen before."),
            ("Cuban coffee", "Small, strong and taken standing at a window counter."),
            ("Sail the bay", "Out past the causeway, where the city becomes a low white line."),
        ],
    },
    "ANC": {
        "city": "Anchorage",
        "region": "Alaska, U.S.A.",
        "tagline": "Where the map runs out",
        "motif": "peaks",
        "palette": ("#28506b", "#cfe3ee", "#e0a52e"),
        "things": [
            ("Glacier day trip", "Ice that groans and cracks while you stand and watch it."),
            ("Midnight light", "In summer the sun barely sets. Walk at eleven and see."),
            ("Bush plane", "Float-plane out to a lake with nobody else on it."),
            ("Salmon run", "Stand in the shallows and watch the river turn silver."),
        ],
    },
    "HNL": {
        "city": "Honolulu",
        "region": "Hawaii, U.S.A.",
        "tagline": "Mid-ocean, mid-afternoon, no hurry",
        "motif": "surf",
        "palette": ("#12787f", "#f2c14e", "#e2643c"),
        "things": [
            ("Learn to surf", "Waikiki's long slow rollers are the kindest classroom there is."),
            ("Climb the crater", "Up Diamond Head early, before the trail warms up."),
            ("Windward drive", "Around the island the long way, stopping at every lookout."),
            ("Luau evening", "Roast pork, ukulele and the sun going down behind the palms."),
        ],
    },
    "MEX": {
        "city": "Mexico City",
        "region": "Mexico",
        "tagline": "A capital built on a lake bed",
        "motif": "dome",
        "palette": ("#1f5f5e", "#e8a13a", "#c1441f"),
        "things": [
            ("Pyramids at dawn", "Teotihuacan before the coaches arrive, all to yourself."),
            ("Float the canals", "Xochimilco, on a painted barge, with a band alongside."),
            ("Murals downtown", "Whole walls of history painted three storeys high."),
            ("Market lunch", "Point at whatever smells best. It will be correct."),
        ],
    },
    "GIG": {
        "city": "Rio de Janeiro",
        "region": "Brazil",
        "tagline": "Mountains that fall into the sea",
        "motif": "peaks",
        "palette": ("#146b6b", "#f2b544", "#d4562a"),
        "things": [
            ("Sugarloaf cable car", "Two stages up, and the whole bay opens underneath you."),
            ("Copacabana morning", "Beach football, cold coconut, the mountains behind."),
            ("Samba night", "Lapa on a Friday. Follow the drums; they know the way."),
            ("Tijuca forest", "Rainforest inside the city limits, twenty minutes from the sand."),
        ],
    },
    "LHR": {
        "city": "London",
        "region": "England",
        "tagline": "Fog, river and a very long history",
        "motif": "spire",
        "palette": ("#2b4a63", "#d9c9a8", "#c1541f"),
        "things": [
            ("River walk", "South bank from the bridges east, past every century at once."),
            ("Museum afternoon", "Free to enter, impossible to finish. Pick one wing."),
            ("West End show", "Curtain up at half seven, pub across the road after."),
            ("Sunday market", "Portobello early, for things you did not know you wanted."),
        ],
    },
    "CDG": {
        "city": "Paris",
        "region": "France",
        "tagline": "An afternoon that lasts all evening",
        "motif": "spire",
        "palette": ("#33556e", "#e6c98f", "#b8432a"),
        "things": [
            ("Left bank hours", "Coffee, a paper, and no plan whatsoever until lunch."),
            ("The great museum", "Go in the last two hours; the crowds have gone home."),
            ("Montmartre steps", "Climb them at dusk and look back over the rooftops."),
            ("Market street", "Bread, cheese, fruit, and a bench by the river."),
        ],
    },
    "FCO": {
        "city": "Rome",
        "region": "Italy",
        "tagline": "Three thousand years, all still in use",
        "motif": "dome",
        "palette": ("#3d5a52", "#e8c07a", "#b5462a"),
        "things": [
            ("The Forum at opening", "Ruins in low morning light, before the heat arrives."),
            ("Fountain at midnight", "Trevi is a different place when the square is empty."),
            ("Trastevere dinner", "Cobbles, ivy, and the long slow Roman evening."),
            ("Espresso standing", "At the bar, one gulp, thirty seconds, out again."),
        ],
    },
    "FRA": {
        "city": "Frankfurt",
        "region": "Germany",
        "tagline": "Old square, new skyline",
        "motif": "skyline",
        "palette": ("#294b63", "#dcc38e", "#c1541f"),
        "things": [
            ("Römerberg square", "Timber-framed houses around a plaza that rebuilt itself."),
            ("Museum embankment", "A dozen museums along one stretch of the river."),
            ("Apple wine tavern", "Sachsenhausen, long shared tables, ribbed grey jugs."),
            ("Rhine day trip", "An hour out: castles, vineyards and a slow boat."),
        ],
    },
    "IST": {
        "city": "Istanbul",
        "region": "Turkey",
        "tagline": "Two continents, one ferry ride",
        "motif": "dome",
        "palette": ("#1d5566", "#e3b556", "#c04a2a"),
        "things": [
            ("Cross the Bosphorus", "Ferry from Europe to Asia for the price of a tram ticket."),
            ("Grand Bazaar", "Get lost on purpose. Accept the tea. Haggle politely."),
            ("Dome at prayer", "Stand under the great dome and listen to it echo."),
            ("Fish under the bridge", "Grilled, in bread, eaten watching the boats."),
        ],
    },
    "HKG": {
        "city": "Hong Kong",
        "region": "Hong Kong",
        "tagline": "Harbour lights and mountain trails",
        "motif": "skyline",
        "palette": ("#17475e", "#e8b93f", "#cc4b28"),
        "things": [
            ("Peak tram", "Straight up the hillside to the view everyone photographs."),
            ("Star Ferry", "Cross the harbour on the top deck, ten minutes, pennies."),
            ("Night market", "Temple Street after dark: noodles, fortune tellers, neon."),
            ("Island hop", "A ferry to Lantau and a beach with nobody on it."),
        ],
    },
    "HND": {
        "city": "Tokyo",
        "region": "Japan",
        "tagline": "Neon streets, quiet gardens",
        "motif": "peaks",
        "palette": ("#2a4a6b", "#e8e2d4", "#c9432f"),
        "things": [
            ("Fish market breakfast", "Be there before six. Eat the freshest thing you ever will."),
            ("Temple morning", "Asakusa at opening, incense smoke and almost no one about."),
            ("Crossing at night", "Stand at Shibuya and watch a thousand people move at once."),
            ("Mount Fuji view", "Clear winter mornings, from the train window heading west."),
        ],
    },
    "SYD": {
        "city": "Sydney",
        "region": "Australia",
        "tagline": "A harbour city with its shoes off",
        "motif": "surf",
        "palette": ("#12667f", "#f2c14e", "#e0623c"),
        "things": [
            ("Harbour ferry", "To Manly and back; the best cheap tour in the country."),
            ("Bondi to Bronte", "Cliff walk between beaches, swim at either end."),
            ("Climb the bridge", "Or just walk the pedestrian span and look down."),
            ("Blue Mountains", "Two hours west: eucalyptus haze and enormous sandstone."),
        ],
    },
}


def get(code):
    """The destination guide for an airport code, or None."""
    return DESTINATIONS.get(code.upper())


def all_destinations():
    """Every guide, alphabetical by city, for the index page."""
    return sorted(
        ({"code": code, **entry} for code, entry in DESTINATIONS.items()),
        key=lambda entry: entry["city"],
    )
