# Colors
BACKGROUND = (30, 30, 30)
GRID_DOT = (60, 60, 60)
TOOLBAR_BG = (50, 50, 50)
TOOLBAR_BUTTON = (70, 70, 80)
TOOLBAR_BUTTON_HOVER = (90, 90, 100)
TOOLBAR_BUTTON_ACTIVE = (100, 120, 140)
COMPONENT_BODY = (80, 80, 100)
COMPONENT_BORDER = (150, 150, 170)
COMPONENT_SELECTED = (255, 255, 0)
PIN_HIGH = (0, 255, 0)
PIN_LOW = (128, 128, 128)
PIN_HOLE = (20, 20, 20)
PIN_BORDER = (180, 180, 200)
WIRE_COLOR = (200, 200, 200)
WIRE_HIGH = (0, 255, 0)
WIRE_LOW = (128, 128, 128)
WIRE_CYCLE = (255, 0, 0)
SELECTION_BOX = (100, 140, 255)
RUBBER_BAND_FILL = (100, 140, 255, 40)
CYCLE_HIGHLIGHT = (255, 0, 0)
WARNING_COLOR = (255, 60, 60)
OUTPUT_TEXT = (255, 255, 255)
OVERLAY_TEXT = (200, 200, 200)

# Sizes
GRID_SIZE = 20
COMPONENT_WIDTH = 70
COMPONENT_HEIGHT = 50
PIN_RADIUS = 6
TOOLBAR_WIDTH = 170
FONT_SIZE = 12
SMALL_FONT_SIZE = 10
MIN_ZOOM = 0.1
MAX_ZOOM = 10.0
ZOOM_STEP = 0.1

# Component types
GATE_TYPES = ['AND', 'OR', 'NOT', 'NAND', 'NOR', 'XOR', 'XNOR']
EXTRA_TYPES = ['INPUT', 'OUTPUT', 'CLOCK', 'SEVEN_SEGMENT']
ALL_TYPES = GATE_TYPES + EXTRA_TYPES

# Pin definitions per component type
PIN_DEFS = {
    'AND':       {'inputs': [('in0', 0.0, 0.33), ('in1', 0.0, 0.67)], 'outputs': [('out', 1.0, 0.5)]},
    'OR':        {'inputs': [('in0', 0.0, 0.33), ('in1', 0.0, 0.67)], 'outputs': [('out', 1.0, 0.5)]},
    'NOT':       {'inputs': [('in0', 0.0, 0.5)], 'outputs': [('out', 1.0, 0.5)]},
    'NAND':      {'inputs': [('in0', 0.0, 0.33), ('in1', 0.0, 0.67)], 'outputs': [('out', 1.0, 0.5)]},
    'NOR':       {'inputs': [('in0', 0.0, 0.33), ('in1', 0.0, 0.67)], 'outputs': [('out', 1.0, 0.5)]},
    'XOR':       {'inputs': [('in0', 0.0, 0.33), ('in1', 0.0, 0.67)], 'outputs': [('out', 1.0, 0.5)]},
    'XNOR':      {'inputs': [('in0', 0.0, 0.33), ('in1', 0.0, 0.67)], 'outputs': [('out', 1.0, 0.5)]},
    'INPUT':     {'inputs': [], 'outputs': [('out', 1.0, 0.5)]},
    'OUTPUT':    {'inputs': [('in0', 0.0, 0.5)], 'outputs': [('out', 1.0, 0.5)]},
    'CLOCK':     {'inputs': [], 'outputs': [('out', 1.0, 0.5)]},
    'SEVEN_SEGMENT': {
        'inputs': [
            ('a', 0.0, 0.1), ('b', 0.0, 0.22), ('c', 0.0, 0.34),
            ('d', 0.0, 0.46), ('e', 0.0, 0.58), ('f', 0.0, 0.70), ('g', 0.0, 0.82)
        ],
        'outputs': []
    },
}

# Component display sizes (width, height) in world units
COMPONENT_SIZES = {
    'AND': (70, 50), 'OR': (70, 50), 'NOT': (50, 50),
    'NAND': (70, 50), 'NOR': (70, 50), 'XOR': (70, 50), 'XNOR': (70, 50),
    'INPUT': (50, 40), 'OUTPUT': (50, 40), 'CLOCK': (60, 40),
    'SEVEN_SEGMENT': (80, 140),
}
