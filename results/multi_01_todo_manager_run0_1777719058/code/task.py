"""Task data model for the CLI Todo Manager."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Task:
    """Represents a single task with an ID, title, priority, completion status, and creation timestamp."""

    id: int
    title: str
    priority: str = "medium"  # low, medium, high
    completed: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the task to a JSON-ready dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "priority": self.priority,
            "completed": self.completed,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """Deserialize a Task from a dictionary (e.g. loaded from JSON)."""
        return cls(
            id=data["id"],
            title=data["title"],
            priority=data.get("priority", "medium"),
            completed=data.get("completed", False),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
