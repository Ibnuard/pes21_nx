"""Measured scoreboard geometry, in physical atlas pixels.

The native main plate begins at timeline x=6. The home accent sits outside
that plate at x=-2..6. Its mirrored away counterpart needs anchor x=244:
the child's (-2, -2) offset and 8x24 tiles give x=238..246, height 48.
"""

PLATE_X = 6
PLATE_WIDTH = 384
PLATE_HEIGHT = 48
BOXES = {
    'home_team': (0, 78),
    'home_score': (78, 116),
    'away_score': (116, 154),
    'away_team': (154, 232),
    'away_accent': (232, 240),
    'timer': (240, 336),
    'pes_logo': (336, 384),
}
LOGO_ICON = (348, 12, 372, 36)
SCORE_DIVIDER = (115, 117)  # One pixel from each score cell, not only away.
# Device v7 shows native uirText glyphs ~2 px right of the context center.
# This is an optical correction to placement, not a font/box width change.
TEXT_CENTER_CORRECTION_X = -2


def validate_geometry():
    end = 0
    for start, stop in BOXES.values():
        if start != end or stop <= start:
            raise ValueError('scoreboard boxes overlap or contain a gap')
        end = stop
    if end != PLATE_WIDTH:
        raise ValueError('scoreboard boxes do not fill the main plate')
    width = lambda name: BOXES[name][1] - BOXES[name][0]
    if width('home_team') != width('away_team'):
        raise ValueError('unequal team boxes')
    if width('home_score') != width('away_score'):
        raise ValueError('unequal score boxes')
    d0, d1 = SCORE_DIVIDER
    if d0 + d1 != 2 * BOXES['away_score'][0]:
        raise ValueError('score divider must straddle both cells equally')
    if width('pes_logo') != PLATE_HEIGHT:
        raise ValueError('logo context must be square')
    x0, y0, x1, y1 = LOGO_ICON
    if x1 - x0 != y1 - y0 or x0 + x1 != sum(BOXES['pes_logo']) or y0 + y1 != PLATE_HEIGHT:
        raise ValueError('logo icon must be square and centered')
    return {name: [start, 0, stop, PLATE_HEIGHT]
            for name, (start, stop) in BOXES.items()}


def timeline_targets():
    validate_geometry()
    # Time-content glyph spans keep their stock one/two/three-minute-digit
    # layouts. Their visual center is ~57.3 px from the time_set origin.
    timer_center = PLATE_X + sum(BOXES['timer']) / 2
    clock_x = round(timer_center - 57.35, 2)
    return {
        1: (8, 48),                       # cardNum_home
        7: (236, 48),                     # mirrored cardNum_away
        13: (clock_x - 4.65, 6),          # stock time plate, behind main
        14: (clock_x, 8),                 # time_set
        33: (clock_x, 8),                 # losstime_progress_set
        52: (100, 50),                    # aggregate
        56: (PLATE_X + BOXES['timer'][0], 50),
        60: (PLATE_X, 0),
        61: (PLATE_X + BOXES['away_team'][0] + 2 + TEXT_CENTER_CORRECTION_X, 10.65),
        63: (PLATE_X + BOXES['home_team'][0] + 2 + TEXT_CENTER_CORRECTION_X, 10.65),
        65: (PLATE_X + BOXES['away_score'][0] + 2 + TEXT_CENTER_CORRECTION_X, 8),
        67: (PLATE_X + BOXES['home_score'][0] + 2 + TEXT_CENTER_CORRECTION_X, 8),
        69: (PLATE_X + BOXES['away_accent'][1] - 2, 2),
        75: (0, 2),
    }
