"""Pin classes for component input/output connections."""

from typing import Optional, TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from components import Component
    from wires import Wire


class Pin:
    """Base pin class."""
    def __init__(self, name: str, relative_pos: tuple, parent: 'Component'):
        self.name = name
        self.relative_pos = pygame.Vector2(relative_pos)
        self.parent_component = parent

    @property
    def world_pos(self) -> pygame.Vector2:
        """Absolute world position of this pin."""
        return self.parent_component.position + self.relative_pos

    @property
    def x(self) -> float:
        return self.world_pos.x

    @property
    def y(self) -> float:
        return self.world_pos.y


class InputPin(Pin):
    """An input pin accepts exactly one wire connection."""
    def __init__(self, name: str, relative_pos: tuple, parent: 'Component'):
        super().__init__(name, relative_pos, parent)
        self.wire: Optional['Wire'] = None
        self._cached_value: bool = False

    @property
    def value(self) -> bool:
        """Read the logic level from the connected wire, or False if none."""
        if self.wire is not None and self.wire.start_pin is not None:
            return self.wire.start_pin.value
        return False

    @property
    def connected(self) -> bool:
        return self.wire is not None


class OutputPin(Pin):
    """An output pin can drive multiple wires."""
    def __init__(self, name: str, relative_pos: tuple, parent: 'Component'):
        super().__init__(name, relative_pos, parent)
        self.wires: list['Wire'] = []
        self.value: bool = False  # set by component evaluation
