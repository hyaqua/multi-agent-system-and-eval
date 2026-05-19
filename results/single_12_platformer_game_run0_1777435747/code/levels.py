"""
Level data definitions. Each level is a dictionary with:
  - platforms: list of (x, y, width) tuples
  - coins: list of (x, y) tuples  (coin center position)
  - enemies: list of (x, y) tuples  (enemy spawn, y = platform top)
  - goal: (x, y) tuple  (y = platform top the goal sits on)
  - player_start: (x, y) tuple
"""

LEVELS = [
    # Level 1 – "The Meadow" – gentle introduction, mostly flat ground
    {
        "name": "The Meadow",
        "player_start": (80, 400),
        "platforms": [
            # Continuous ground with small gaps
            (0, 500, 300),
            (310, 500, 300),
            (620, 500, 300),
            (930, 500, 300),
            # Elevated platforms
            (150, 380, 120),
            (400, 300, 100),
            (650, 360, 100),
            (850, 400, 120),
            (1100, 320, 120),
            # Final section ground
            (1240, 500, 400),
        ],
        "coins": [
            (180, 350),   # on elevated platform at y=380
            (430, 270),   # on elevated platform at y=300
            (680, 330),   # on elevated platform at y=360
            (880, 370),   # on elevated platform at y=400
            (1130, 290),  # on elevated platform at y=320
            (1300, 470),  # on ground near goal
        ],
        "enemies": [
            (200, 500),   # patrols on first ground segment
            (750, 500),   # patrols on third ground segment
        ],
        "goal": (1500, 500),
    },
    # Level 2 – "The Caverns" – more vertical, tighter jumps
    {
        "name": "The Caverns",
        "player_start": (80, 420),
        "platforms": [
            # Ground sections with gaps
            (0, 520, 200),
            (220, 520, 180),
            (420, 520, 180),
            (620, 520, 250),
            # Staircase / vertical platforms
            (200, 420, 100),
            (350, 350, 100),
            (500, 280, 100),
            (700, 380, 100),
            (850, 320, 100),
            (1000, 400, 100),
            (1150, 340, 100),
            (1300, 260, 100),
            # Final ground
            (1450, 520, 300),
        ],
        "coins": [
            (230, 390),
            (380, 320),
            (530, 250),
            (730, 350),
            (880, 290),
            (1030, 370),
            (1180, 310),
            (1330, 230),
        ],
        "enemies": [
            (300, 520),
            (700, 520),
            (1040, 400),
        ],
        "goal": (1600, 520),
    },
    # Level 3 – "Sky Peaks" – challenging, sparse platforms
    {
        "name": "Sky Peaks",
        "player_start": (60, 300),
        "platforms": [
            # Starting ground
            (0, 500, 200),
            (220, 500, 100),
            # Ascending platforms
            (360, 440, 90),
            (500, 380, 80),
            (620, 310, 80),
            (740, 370, 80),
            (860, 280, 70),
            (960, 350, 80),
            (1080, 260, 70),
            (1180, 200, 80),
            (1300, 300, 90),
            # Final ground
            (1420, 500, 250),
        ],
        "coins": [
            (390, 410),
            (530, 350),
            (650, 280),
            (770, 340),
            (890, 250),
            (990, 320),
            (1110, 230),
            (1210, 170),
        ],
        "enemies": [
            (260, 500),
            (540, 380),
            (1000, 350),
            (1200, 200),
        ],
        "goal": (1560, 500),
    },
]
