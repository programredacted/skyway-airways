"""Destination posters and what to do when you land.

One entry per airport we serve. `palette` colours that city's poster; the
artwork itself lives in templates/posters/<code>.html, one landmark per city.
`things` is a plain list of sights worth the trip - not a day-by-day plan.
"""

DESTINATIONS = {
    "JFK": {
        "city": "New York",
        "region": "New York, U.S.A.",
        "tagline": "The island that never sits still",
        "palette": ("#1b3a5c", "#e0a52e", "#c1541f"),
        "things": [
            ("The Statue of Liberty", "Ferry out from Battery Park and climb the pedestal for the harbour view."),
            ("Empire State Building", "Eighty-six floors up, best an hour before sunset when the grid lights up."),
            ("Central Park", "Eight hundred acres in the middle of it all. Enter at 59th and keep walking."),
            ("Times Square after dark", "Absurd, loud, and worth seeing once with your head tilted back."),
            ("Brooklyn Bridge on foot", "Walk it towards Manhattan so the skyline builds in front of you."),
            ("A jazz basement in the Village", "Sets start late and finish later. Cash at the door."),
        ],
    },
    "LAX": {
        "city": "Los Angeles",
        "region": "California, U.S.A.",
        "tagline": "Sunshine, palm trees and open road",
        "palette": ("#2b7fa8", "#f0b429", "#d4622a"),
        "things": [
            ("The Hollywood Sign", "Best seen from Griffith Observatory, which is worth the drive anyway."),
            ("Walk of Fame", "Fifteen blocks of brass stars on Hollywood Boulevard."),
            ("Santa Monica Pier", "Ferris wheel over the Pacific, and the end of Route 66."),
            ("Venice Beach", "Boardwalk, skate bowl and muscle beach, best before nine."),
            ("A studio backlot tour", "See how plywood and paint become anywhere in the world."),
            ("Pacific Coast Highway", "Drive north to Malibu with the roof down and no particular hurry."),
        ],
    },
    "SFO": {
        "city": "San Francisco",
        "region": "California, U.S.A.",
        "tagline": "Fog, hills and the great red bridge",
        "palette": ("#2f5f7a", "#e05a34", "#f0c46a"),
        "things": [
            ("Golden Gate Bridge", "Walk out into the fog with the cables humming overhead."),
            ("Alcatraz", "Boat to the island, then the cell-block tour narrated by men who were there."),
            ("Cable cars", "Hang off the running board up Powell Street and hold on properly."),
            ("Fisherman's Wharf", "Sourdough, crab, and sea lions arguing on the pontoons."),
            ("Lombard Street", "Eight hairpin turns down one block of hillside."),
            ("Napa Valley", "An hour north for vineyards, oak barrels and a very long lunch."),
        ],
    },
    "ORD": {
        "city": "Chicago",
        "region": "Illinois, U.S.A.",
        "tagline": "Broad shoulders on a big lake",
        "palette": ("#20455f", "#d9a227", "#a8451a"),
        "things": [
            ("Willis Tower Skydeck", "Glass ledges cantilevered off the 103rd floor. Look down."),
            ("Architecture river cruise", "Ninety minutes with the whole skyline leaning over you."),
            ("Millennium Park", "The great mirrored bean, and free concerts under the steel shell."),
            ("The Art Institute", "Two lions at the door, Hopper and Seurat inside."),
            ("Ride the L", "The elevated Loop, screeching around corners between the towers."),
            ("Deep-dish pizza", "Order it, wait the forty minutes, understand why."),
        ],
    },
    "MIA": {
        "city": "Miami",
        "region": "Florida, U.S.A.",
        "tagline": "Pastel evenings on the water",
        "palette": ("#1f7d8c", "#f2c14e", "#e8734a"),
        "things": [
            ("Art Deco District", "Ocean Drive's pastel hotels, neon-lit and best walked after dark."),
            ("South Beach", "Wide white sand, striped lifeguard huts, warm water all year."),
            ("Little Havana", "Calle Ocho for cigars, domino players and very strong coffee."),
            ("The Everglades", "Airboat out into flat water, tall grass and unfamiliar birds."),
            ("Vizcaya", "An Italian villa on Biscayne Bay, with formal gardens to the water."),
            ("Key West run", "Three hours of causeways and bridges to the end of the road."),
        ],
    },
    "ANC": {
        "city": "Anchorage",
        "region": "Alaska, U.S.A.",
        "tagline": "Where the map runs out",
        "palette": ("#28506b", "#cfe3ee", "#e0a52e"),
        "things": [
            ("Denali National Park", "Six million acres, one road, and North America's highest peak."),
            ("Portage Glacier", "Ice that groans and cracks while you stand and watch it."),
            ("Float-plane to a lake", "Take off from Lake Hood and land somewhere with nobody on it."),
            ("Northern lights", "From late August, on any clear night away from the town lights."),
            ("Tony Knowles Coastal Trail", "Eleven miles along the inlet, with moose right of way."),
            ("The salmon run", "Stand in the shallows at Ship Creek and watch the river turn silver."),
        ],
    },
    "HNL": {
        "city": "Honolulu",
        "region": "Hawaii, U.S.A.",
        "tagline": "Mid-ocean, mid-afternoon, no hurry",
        "palette": ("#12787f", "#f2c14e", "#e2643c"),
        "things": [
            ("Waikiki Beach", "Long slow rollers and the kindest surf lesson you will ever get."),
            ("Diamond Head", "Up the crater early, before the trail warms up, for the whole coast."),
            ("Pearl Harbor", "The memorial sits directly over the hull. People go quiet."),
            ("The North Shore", "Winter waves the size of houses, and shrimp trucks by the road."),
            ("Hanauma Bay", "A drowned crater full of reef fish, in water you can stand up in."),
            ("A luau at sunset", "Roast pork, ukulele, and the sun going down behind the palms."),
        ],
    },
    "MEX": {
        "city": "Mexico City",
        "region": "Mexico",
        "tagline": "A capital built on a lake bed",
        "palette": ("#1f5f5e", "#e8a13a", "#c1441f"),
        "things": [
            ("Teotihuacan", "Climb the Pyramid of the Sun before the coaches arrive."),
            ("Zocalo and the Cathedral", "One of the largest squares on earth, sinking very slowly."),
            ("Frida Kahlo's Blue House", "Coyoacan, her studio left much as she had it."),
            ("Xochimilco", "Float the old canals on a painted barge with a band alongside."),
            ("Museum of Anthropology", "The Aztec sun stone, and the finest pre-Columbian collection anywhere."),
            ("Rivera's murals", "Whole walls of the country's history, painted three storeys high."),
        ],
    },
    "GIG": {
        "city": "Rio de Janeiro",
        "region": "Brazil",
        "tagline": "Mountains that fall into the sea",
        "palette": ("#146b6b", "#f2b544", "#d4562a"),
        "things": [
            ("Christ the Redeemer", "Cog railway up Corcovado, then the whole city laid out below."),
            ("Sugarloaf Mountain", "Two cable-car stages, and the bay opening underneath you."),
            ("Copacabana", "Beach football, cold coconut, and that wave-patterned pavement."),
            ("Ipanema at sunset", "The whole beach applauds when the sun drops behind Dois Irmaos."),
            ("Escadaria Selaron", "Two hundred steps tiled in scavenged ceramic, all reds and blues."),
            ("Samba in Lapa", "Friday night under the arches. Follow the drums; they know the way."),
        ],
    },
    "LHR": {
        "city": "London",
        "region": "England",
        "tagline": "Fog, river and a very long history",
        "palette": ("#2b4a63", "#d9c9a8", "#c1541f"),
        "things": [
            ("Big Ben and Parliament", "Stand on Westminster Bridge and wait for the hour to strike."),
            ("Tower of London", "Nine hundred years of fortress, and the Crown Jewels in the basement."),
            ("The British Museum", "Free, enormous, impossible to finish. Pick one wing and stay."),
            ("Buckingham Palace", "Changing of the Guard, if you can see over everyone else."),
            ("Tower Bridge", "Walk the high-level glass floor and watch the road open beneath you."),
            ("A West End show", "Curtain up at half seven, pub across the road afterwards."),
        ],
    },
    "CDG": {
        "city": "Paris",
        "region": "France",
        "tagline": "An afternoon that lasts all evening",
        "palette": ("#33556e", "#e6c98f", "#b8432a"),
        "things": [
            ("The Eiffel Tower", "Go at dusk. On the hour it sparkles for five minutes and nobody is cynical."),
            ("The Louvre", "Enter through the glass pyramid in the last two hours, when the crowds have gone."),
            ("Notre-Dame and the Ile de la Cite", "The island the whole city grew out of."),
            ("Montmartre", "Climb the steps to Sacre-Coeur at dusk and look back over the rooftops."),
            ("Dinner, slowly", "A small room, a carafe, and no plan for the rest of the evening."),
            ("A bistro kitchen", "The Ratatouille version is a cartoon; the real ones are just as fierce."),
        ],
    },
    "FCO": {
        "city": "Rome",
        "region": "Italy",
        "tagline": "Three thousand years, all still in use",
        "palette": ("#3d5a52", "#e8c07a", "#b5462a"),
        "things": [
            ("The Colosseum", "Fifty thousand seats, and the tunnels under the arena floor still visible."),
            ("The Roman Forum", "Go at opening, in low light, before the heat arrives."),
            ("The Pantheon", "Nearly two thousand years old, and the dome is still open to the sky."),
            ("Trevi Fountain", "A different place at midnight when the square is finally empty."),
            ("The Vatican Museums", "The long walk to the Sistine Chapel, then everyone looks up at once."),
            ("Trastevere for dinner", "Cobbles, ivy, and the long slow Roman evening."),
        ],
    },
    "FRA": {
        "city": "Frankfurt",
        "region": "Germany",
        "tagline": "Old square, new skyline",
        "palette": ("#294b63", "#dcc38e", "#c1541f"),
        "things": [
            ("Romerberg", "The timber-framed old square, rebuilt beam by beam after the war."),
            ("Main Tower", "The only skyscraper here with a public roof deck. Go up at dusk."),
            ("Museumsufer", "A dozen museums strung along one bank of the river."),
            ("Goethe House", "The rooms the poet grew up in, restored to the year he left."),
            ("An apple-wine tavern", "Sachsenhausen, long shared tables, ribbed grey jugs."),
            ("The Rhine Valley", "An hour out: castles on both banks and a slow boat between them."),
        ],
    },
    "IST": {
        "city": "Istanbul",
        "region": "Turkey",
        "tagline": "Two continents, one ferry ride",
        "palette": ("#1d5566", "#e3b556", "#c04a2a"),
        "things": [
            ("Hagia Sophia", "Cathedral, then mosque, then museum, then mosque again. Stand under the dome."),
            ("The Blue Mosque", "Six minarets and twenty thousand hand-painted tiles."),
            ("Topkapi Palace", "Four courtyards of Ottoman court life, above the water on three sides."),
            ("The Grand Bazaar", "Four thousand shops. Get lost on purpose, accept the tea, haggle politely."),
            ("Basilica Cistern", "An underground forest of columns, with two Medusa heads at the back."),
            ("Cross the Bosphorus", "Europe to Asia for the price of a tram ticket, gulls following the ferry."),
        ],
    },
    "HKG": {
        "city": "Hong Kong",
        "region": "Hong Kong",
        "tagline": "Harbour lights and mountain trails",
        "palette": ("#17475e", "#e8b93f", "#cc4b28"),
        "things": [
            ("Victoria Peak", "The tram goes up at an angle that feels wrong, to the view everyone photographs."),
            ("The Star Ferry", "Cross the harbour on the top deck. Ten minutes, and it costs pennies."),
            ("Tian Tan Buddha", "Two hundred and sixty-eight steps up Lantau to a very large bronze."),
            ("Temple Street Night Market", "Noodles, fortune tellers and neon, from dusk onwards."),
            ("Man Mo Temple", "Coils of incense hanging from the ceiling, burning for weeks."),
            ("Dragon's Back", "A ridge trail with the South China Sea on both sides."),
        ],
    },
    "HND": {
        "city": "Tokyo",
        "region": "Japan",
        "tagline": "Neon streets, quiet gardens",
        "palette": ("#2a4a6b", "#e8e2d4", "#c9432f"),
        "things": [
            ("Senso-ji", "The oldest temple in the city, through the great lantern gate at Asakusa."),
            ("Shibuya Crossing", "Stand at the edge and watch a thousand people move at once."),
            ("Mount Fuji", "Clear winter mornings from the train window heading west."),
            ("Meiji Shrine", "A forest of a hundred thousand trees, in the middle of the city."),
            ("Tsukiji outer market", "Be there before six and eat the freshest thing you ever will."),
            ("Shinjuku after dark", "Alleyways of six-seat bars under a canopy of signage."),
        ],
    },
    "SYD": {
        "city": "Sydney",
        "region": "Australia",
        "tagline": "A harbour city with its shoes off",
        "palette": ("#12667f", "#f2c14e", "#e0623c"),
        "things": [
            ("The Opera House", "Take the tour to see how those shells actually go together."),
            ("Harbour Bridge climb", "Up the arch on a harness, or walk the pedestrian span for free."),
            ("Bondi Beach", "Then the cliff walk to Bronte, swimming at either end."),
            ("Ferry to Manly", "The best cheap tour in the country, thirty minutes each way."),
            ("The Rocks", "The oldest streets in the city, sandstone pubs and a weekend market."),
            ("Blue Mountains", "Two hours west: eucalyptus haze and enormous sandstone cliffs."),
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
