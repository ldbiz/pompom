"""Task queue model and JSON persistence."""

import json
import random
from dataclasses import dataclass


@dataclass
class Task:
    """A single task entry in the task queue."""
    title: str
    done: bool = False

    def to_dict(self) -> dict:
        return {"title": self.title, "done": self.done}

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            title=str(d.get("title", "")),
            done=bool(d.get("done", False)),
        )


class TaskQueue:
    """Ordered list of tasks with optional shuffle mode and sequential advance."""

    def __init__(self) -> None:
        self.tasks: list[Task] = []
        self.current_index: int = -1   # -1 = no current task
        self.shuffle_mode: bool = False

    @property
    def current(self) -> Task | None:
        if 0 <= self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None

    def sync_current(self) -> None:
        """Point current_index at an undone task, or -1 when all are done."""
        if not self.tasks:
            self.current_index = -1
            return
        cur = self.current
        if cur is not None and not cur.done:
            return
        if not self.advance():
            self.current_index = -1

    def add(self, task: Task) -> None:
        self.tasks.append(task)
        if self.current_index < 0:
            self.current_index = 0

    def remove(self, index: int) -> None:
        if not (0 <= index < len(self.tasks)):
            return
        self.tasks.pop(index)
        if not self.tasks:
            self.current_index = -1
        elif self.current_index >= len(self.tasks):
            self.current_index = len(self.tasks) - 1

    def remove_completed(self) -> int:
        """Remove all completed tasks. Returns the number removed."""
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if not t.done]
        removed = before - len(self.tasks)
        if not self.tasks:
            self.current_index = -1
        elif self.current_index >= len(self.tasks):
            self.current_index = len(self.tasks) - 1
        self.sync_current()
        return removed

    def advance(self) -> bool:
        """Move to the next undone task.  Returns True if a new task was selected."""
        if not self.tasks:
            return False
        if self.shuffle_mode:
            undone = [i for i, t in enumerate(self.tasks) if not t.done]
            if not undone:
                return False
            # Avoid re-selecting the same task when alternatives exist
            if len(undone) > 1 and self.current_index in undone:
                undone = [i for i in undone if i != self.current_index]
            self.current_index = random.choice(undone)
            return True
        # Sequential: find next undone task after current
        start = self.current_index + 1 if self.current_index >= 0 else 0
        for i in list(range(start, len(self.tasks))) + list(range(0, start)):
            if not self.tasks[i].done:
                self.current_index = i
                return True
        return False

    def to_json(self) -> str:
        return json.dumps({
            "tasks": [t.to_dict() for t in self.tasks],
            "current_index": self.current_index,
            "shuffle_mode": self.shuffle_mode,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "TaskQueue":
        tq = cls()
        try:
            d = json.loads(s)
            tq.tasks = [Task.from_dict(t) for t in d.get("tasks", [])]
            tq.current_index = int(d.get("current_index", -1))
            tq.shuffle_mode = bool(d.get("shuffle_mode", False))
            # Guard against out-of-range index
            if tq.tasks and not (0 <= tq.current_index < len(tq.tasks)):
                tq.current_index = 0
        except Exception:
            pass
        return tq

