"""Task dataclass and priority ordering."""

from dataclasses import dataclass, field
from datetime import datetime

PRIORITY_ORDER: dict[str, int] = {
    "high": 1,
    "medium": 2,
    "low": 3,
}

VALID_PRIORITIES = frozenset(PRIORITY_ORDER.keys())


@dataclass(frozen=True)
class Task:
    """Immutable task with id, title, priority, completed status, and creation date."""

    id: int
    title: str
    priority: str
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        status = "✅" if self.completed else "❌"
        created_str = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.id:>4d}  {status}  {self.priority:<6s}  {created_str}  {self.title}"
