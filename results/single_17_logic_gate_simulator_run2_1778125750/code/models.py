"""Data model classes for the logic gate simulator."""
from constants import PIN_DEFS, COMPONENT_SIZES, PIN_RADIUS


class Component:
    """A logic component placed on the canvas."""
    _next_id = 0

    def __init__(self, comp_type, x, y, label=None, comp_id=None):
        if comp_id is not None:
            self.id = comp_id
            try:
                num = int(comp_id.split('_')[1])
                Component._next_id = max(Component._next_id, num + 1)
            except (ValueError, IndexError):
                pass
        else:
            self.id = f"comp_{Component._next_id}"
            Component._next_id += 1

        self.comp_type = comp_type
        self.x = x
        self.y = y
        self.label = label or comp_type
        self.properties = {}
        if comp_type == 'CLOCK':
            self.properties['frequency'] = 1.0

        self.input_values = {}
        self.output_values = {}
        self.clock_timer = 0.0
        self.clock_state = 0

        pin_def = PIN_DEFS.get(comp_type, {'inputs': [], 'outputs': []})
        self.input_pins = list(pin_def['inputs'])
        self.output_pins = list(pin_def['outputs'])

        for name, _, _ in self.input_pins:
            self.input_values[name] = 0
        for name, _, _ in self.output_pins:
            self.output_values[name] = 0

    @property
    def width(self):
        return COMPONENT_SIZES.get(self.comp_type, (70, 50))[0]

    @property
    def height(self):
        return COMPONENT_SIZES.get(self.comp_type, (70, 50))[1]

    def get_pin_world_pos(self, pin_name, is_input):
        if is_input:
            pins = self.input_pins
        else:
            pins = self.output_pins
        for name, rx, ry in pins:
            if name == pin_name:
                return (self.x + rx * self.width, self.y + ry * self.height)
        return (self.x, self.y)

    def contains_point(self, wx, wy):
        return (self.x <= wx <= self.x + self.width and
                self.y <= wy <= self.y + self.height)

    def find_pin_at(self, wx, wy):
        for name, rx, ry in self.input_pins:
            px = self.x + rx * self.width
            py = self.y + ry * self.height
            if (wx - px) ** 2 + (wy - py) ** 2 <= PIN_RADIUS ** 2:
                return (name, True)
        for name, rx, ry in self.output_pins:
            px = self.x + rx * self.width
            py = self.y + ry * self.height
            if (wx - px) ** 2 + (wy - py) ** 2 <= PIN_RADIUS ** 2:
                return (name, False)
        return None

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.comp_type,
            'x': self.x,
            'y': self.y,
            'label': self.label,
            'properties': self.properties,
        }

    @classmethod
    def from_dict(cls, d):
        comp = cls(d['type'], d['x'], d['y'], d.get('label'), comp_id=d['id'])
        comp.properties = d.get('properties', {})
        return comp


class Wire:
    """A wire connecting an output pin to an input pin."""
    _next_id = 0

    def __init__(self, from_comp_id, from_pin, to_comp_id, to_pin, wire_id=None):
        if wire_id is not None:
            self.id = wire_id
            try:
                num = int(wire_id.split('_')[1])
                Wire._next_id = max(Wire._next_id, num + 1)
            except (ValueError, IndexError):
                pass
        else:
            self.id = f"wire_{Wire._next_id}"
            Wire._next_id += 1

        self.from_comp = from_comp_id
        self.from_pin = from_pin
        self.to_comp = to_comp_id
        self.to_pin = to_pin
        self.path = []

    def to_dict(self):
        return {
            'id': self.id,
            'from_component': self.from_comp,
            'from_pin': self.from_pin,
            'to_component': self.to_comp,
            'to_pin': self.to_pin,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(d['from_component'], d['from_pin'],
                   d['to_component'], d['to_pin'],
                   wire_id=d.get('id'))
