"""PawPal+ logic layer: backend classes for owners, pets, tasks, and scheduling."""

import logging
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

VALID_PRIORITIES = ("low", "medium", "high")
VALID_FREQUENCIES = ("daily", "weekly", "once")
# How far to move a task's due date when a recurring task is completed
RECURRENCE_DELTAS = {"daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
PRIORITY_ORDER = {"low": 1, "medium": 2, "high": 3}


def _format_time(minute: int) -> str:
    """Turn minutes from midnight into an HH:MM string."""
    return f"{minute // 60:02d}:{minute % 60:02d}"


@dataclass
class Task:
    """A single pet care activity (walk, feeding, meds, etc.)."""

    title: str
    duration_minutes: int
    priority: str  # one of VALID_PRIORITIES
    frequency: str = "daily"
    time: str | None = None  # optional preferred time, "HH:MM"
    completed: bool = False
    due_date: date | None = None  # when this occurrence is due; None means today
    assigned_to: str | None = None  # family member responsible for this task
    added_by: str | None = None  # family member who created it
    completed_on: date | None = None  # the day it was marked done

    def __post_init__(self) -> None:
        """Reject bad priorities, frequencies, and times so later code can trust them."""
        if self.priority not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {VALID_PRIORITIES}, got {self.priority!r}"
            )
        if self.frequency not in VALID_FREQUENCIES:
            raise ValueError(
                f"frequency must be one of {VALID_FREQUENCIES}, got {self.frequency!r}"
            )
        if self.time is not None:
            try:
                datetime.strptime(self.time, "%H:%M")
            except (ValueError, TypeError):
                raise ValueError(f"time must look like HH:MM, got {self.time!r}") from None

    def priority_value(self) -> int:
        """Convert the priority label into a number for sorting."""
        return PRIORITY_ORDER[self.priority]

    def mark_complete(self) -> "Task | None":
        """Mark this task as done; for daily/weekly tasks, return the next occurrence.

        The next due date is counted from this task's due date (or today if it has
        none), so finishing a task late doesn't shift the routine. Other frequencies
        return None.
        """
        today = date.today()
        self.completed = True
        self.completed_on = today
        delta = RECURRENCE_DELTAS.get(self.frequency)
        if delta is None:
            return None
        # Stay on the routine's cadence, but never land on a day that has already
        # started: finishing today's walk must not make an identical one due today.
        next_due = (self.due_date or today) + delta
        while next_due <= today:
            next_due += delta
        return replace(self, completed=False, completed_on=None, due_date=next_due)

    def is_due(self, on: date | None = None) -> bool:
        """True if this task is pending and due on `on` (default today) or overdue."""
        on = on or date.today()
        return not self.completed and (self.due_date is None or self.due_date <= on)

    def is_upcoming(self, on: date | None = None) -> bool:
        """True if this task is pending but not due until after `on` (default today)."""
        on = on or date.today()
        return not self.completed and self.due_date is not None and self.due_date > on

    def done_on(self, day: date | None = None) -> bool:
        """True if this task was completed on `day` (default today)."""
        day = day or date.today()
        return self.completed and (self.completed_on or date.today()) == day

    def occurs_on(self, day: date) -> bool:
        """Whether this task belongs on the calendar for `day`.

        Completed tasks appear only on the day they were finished. Pending tasks
        appear on their due day; daily ones every day after it, weekly ones every
        7 days; overdue pending tasks are treated as due today.
        """
        if self.completed:
            return self.done_on(day)
        today = date.today()
        base = today if self.due_date is None or self.due_date < today else self.due_date
        if self.frequency == "once":
            return day == base
        if day < base:
            return False
        if self.frequency == "daily":
            return True
        return (day - base).days % 7 == 0  # weekly


@dataclass
class Pet:
    """A pet and its list of care tasks."""

    name: str
    species: str
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a care task for this pet."""
        self.tasks.append(task)

    def mark_task_complete(self, title: str) -> "Task | None":
        """Complete a task by title and, if it recurs, add the next occurrence to this pet.

        Args:
            title: Title of the pending task to complete.

        Returns:
            The newly created next occurrence for a daily or weekly task,
            or None if the task doesn't repeat.

        Raises:
            KeyError: If this pet has no pending task with that title.
        """
        for task in self.tasks:
            if task.title == title and not task.completed:
                next_task = task.mark_complete()
                logger.info("task_completed pet=%s title=%s recurs=%s",
                            self.name, title, next_task is not None)
                if next_task is not None:
                    self.add_task(next_task)
                return next_task
        raise KeyError(f"No pending task titled {title!r} for {self.name}")

    def edit_task(self, title: str, duration: int, priority: str) -> None:
        """Update the duration and priority of an existing task."""
        if priority not in VALID_PRIORITIES:
            raise ValueError(
                f"priority must be one of {VALID_PRIORITIES}, got {priority!r}"
            )
        for task in self.tasks:
            if task.title == title:
                task.duration_minutes = duration
                task.priority = priority
                return
        raise KeyError(f"No task titled {title!r} for {self.name}")

    def remove_task(self, title: str) -> None:
        """Remove a task by its title."""
        for task in self.tasks:
            if task.title == title:
                self.tasks.remove(task)
                return
        raise KeyError(f"No task titled {title!r} for {self.name}")


@dataclass
class Owner:
    """A household (family) with shared pets, available time, and family members.

    `name` is the household name. Any member can add or complete tasks for any pet.
    """

    name: str
    available_minutes: int
    preferences: dict = field(default_factory=dict)
    pets: list[Pet] = field(default_factory=list)
    members: list[str] = field(default_factory=list)

    def add_member(self, name: str) -> None:
        """Add a family member; names are unique (case-insensitive)."""
        name = name.strip()
        if not name:
            raise ValueError("member name can't be empty")
        if any(m.lower() == name.lower() for m in self.members):
            raise ValueError(f"{name} is already in the family")
        self.members.append(name)

    def remove_member(self, name: str) -> None:
        """Remove a member; their tasks become unassigned instead of disappearing."""
        if name not in self.members:
            raise KeyError(f"No family member named {name!r}")
        self.members.remove(name)
        for task in self.get_all_tasks():
            if task.assigned_to == name:
                task.assigned_to = None

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""
        self.pets.append(pet)

    def remove_pet(self, name: str) -> None:
        """Remove a pet and all of its tasks."""
        for pet in self.pets:
            if pet.name == name:
                self.pets.remove(pet)
                return
        raise KeyError(f"No pet named {name!r}")

    def tasks_on(self, day: date) -> list[tuple[Pet, Task]]:
        """Every (pet, task) pair that belongs on the calendar for `day`."""
        return [(pet, t) for pet in self.pets for t in pet.tasks if t.occurs_on(day)]

    def get_all_tasks(self) -> list[Task]:
        """Return every task across all of the owner's pets."""
        return [task for pet in self.pets for task in pet.tasks]

    def filter_tasks(
        self,
        pet_name: str | None = None,
        completed: bool | None = None,
        member: str | None = None,
    ) -> list[Task]:
        """Return the tasks that match the given pet name, completion status, and/or member.

        Args:
            pet_name: Only include tasks belonging to the pet with this name.
                None means don't filter by pet.
            completed: True for finished tasks, False for pending ones.
                None means don't filter by status.
            member: Only include tasks assigned to this family member.
                None means don't filter by member.

        Returns:
            A list of matching tasks. It is empty if nothing matches, including
            when no pet has the given name.
        """
        return [
            task
            for pet in self.pets
            if pet_name is None or pet.name == pet_name
            for task in pet.tasks
            if completed is None or task.completed == completed
            if member is None or task.assigned_to == member
        ]


@dataclass
class DailyPlan:
    """The result of scheduling: what got scheduled, what got skipped, and why."""

    # (task, start time in minutes from midnight), in the order they run
    scheduled_tasks: list[tuple[Task, int]] = field(default_factory=list)
    # (task, reason it was skipped)
    skipped_tasks: list[tuple[Task, str]] = field(default_factory=list)
    total_minutes: int = 0

    def add_scheduled(self, task: Task, start_minute: int) -> None:
        """Add a task at the given start time and add its duration to total_minutes."""
        self.scheduled_tasks.append((task, start_minute))
        self.total_minutes += task.duration_minutes

    def add_skipped(self, task: Task, reason: str) -> None:
        """Record a task that didn't fit, along with the reason."""
        self.skipped_tasks.append((task, reason))

    def explain(self) -> str:
        """Return the plan as text: scheduled tasks with times, then skipped tasks with reasons."""
        lines = []
        if self.scheduled_tasks:
            lines.append("Scheduled:")
            for task, start in self.scheduled_tasks:
                end = start + task.duration_minutes
                lines.append(
                    f"  {_format_time(start)}-{_format_time(end)}  {task.title} "
                    f"({task.duration_minutes} min) [priority: {task.priority}]"
                )
        else:
            lines.append("Nothing could be scheduled.")
        if self.skipped_tasks:
            lines.append("Skipped:")
            for task, reason in self.skipped_tasks:
                lines.append(f"  {task.title} - {reason}")
        lines.append(f"Total time: {self.total_minutes} min")
        return "\n".join(lines)


class Scheduler:
    """Builds a daily plan from the owner's tasks and available time."""

    def __init__(self, owner: Owner):
        """Store the owner whose pets' tasks will be scheduled."""
        self.owner = owner

    def sort_tasks(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks by priority (highest first), shorter tasks first within a priority."""
        return sorted(tasks, key=lambda t: (-t.priority_value(), t.duration_minutes))

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """Sort tasks by their "HH:MM" time, earliest first; tasks with no time go last.

        Args:
            tasks: The tasks to sort. The list itself is not modified.

        Returns:
            A new list in time order. Tasks with the same time (or no time) keep
            their original relative order, because sorted() is stable.
        """
        # Zero-padded "HH:MM" strings sort correctly as plain text.
        # (t.time is None) is False/True, so timed tasks come before untimed ones.
        return sorted(tasks, key=lambda t: (t.time is None, t.time or ""))

    def detect_conflicts(self) -> list[str]:
        """Return a warning for each pair of pending timed tasks whose times overlap.

        A person can only do one thing at a time, so only tasks with the same
        assignee clash (across all pets); tasks assigned to different family members
        can overlap freely. Unassigned tasks count as one shared "nobody" group.
        Tasks that merely touch (one ends exactly when the next starts) don't conflict.
        Returns an empty list when there are no conflicts; never raises.
        """
        timed = []
        for pet in self.owner.pets:
            for task in pet.tasks:
                if task.time and task.is_due():
                    hours, minutes = task.time.split(":")
                    start = int(hours) * 60 + int(minutes)
                    timed.append((start, start + task.duration_minutes, pet.name, task))
        timed.sort(key=lambda entry: entry[0])

        warnings = []
        for i, (start_a, end_a, pet_a, task_a) in enumerate(timed):
            for start_b, _end_b, pet_b, task_b in timed[i + 1:]:
                if start_b >= end_a:
                    break  # sorted by start, so nothing later can overlap task_a
                if task_a.assigned_to != task_b.assigned_to:
                    continue  # different people can do things at the same time
                who = f" [{task_a.assigned_to}]" if task_a.assigned_to else ""
                where = f"for {pet_a}" if pet_a == pet_b else f"({pet_a} and {pet_b})"
                warnings.append(
                    f"Conflict {where}{who}: '{task_a.title}' {_format_time(start_a)}-{_format_time(end_a)}"
                    f" overlaps '{task_b.title}' starting {_format_time(start_b)}"
                )
        if warnings:
            logger.warning("conflicts_detected count=%d", len(warnings))
        return warnings

    def find_next_available_slot(
        self,
        duration: int,
        after: int = 8 * 60,
        day_end: int = 22 * 60,
        member: str | None = None,
    ) -> int | None:
        """Find the earliest start time where a task of this length fits without a conflict.

        Pending timed tasks (across all pets) are treated as busy blocks. The search
        walks forward from `after`, jumping past each block that overlaps the
        candidate slot, so it only looks at each block once.

        Args:
            duration: Length of the new task in minutes.
            after: Earliest allowed start, in minutes from midnight (default 08:00).
            day_end: The slot must finish by this minute (default 22:00).
            member: If given, only that family member's tasks count as busy time.
                None (default) treats everyone's tasks as busy.

        Returns:
            The start time in minutes from midnight, or None if nothing fits today.
        """
        busy = []
        for pet in self.owner.pets:
            for task in pet.tasks:
                if task.time and task.is_due() and (
                    member is None or task.assigned_to == member
                ):
                    hours, minutes = task.time.split(":")
                    start = int(hours) * 60 + int(minutes)
                    busy.append((start, start + task.duration_minutes))
        busy.sort()

        candidate = after
        for start, end in busy:
            if start >= candidate + duration:
                break  # the gap before this block is big enough
            candidate = max(candidate, end)  # overlaps (or ends after) candidate: jump past it
        return candidate if candidate + duration <= day_end else None

    def generate_plan(self, start_minute: int = 8 * 60) -> DailyPlan:
        """Sort all pending tasks by priority and fit them into the owner's available time."""
        plan = DailyPlan()
        pending = [t for t in self.owner.get_all_tasks() if t.is_due()]
        remaining = self.owner.available_minutes
        current = start_minute

        for task in self.sort_tasks(pending):
            if task.duration_minutes <= remaining:
                plan.add_scheduled(task, current)
                current += task.duration_minutes
                remaining -= task.duration_minutes
            else:
                plan.add_skipped(
                    task,
                    f"needs {task.duration_minutes} min but only {remaining} min left",
                )
        logger.info("plan_generated scheduled=%d skipped=%d total_min=%d",
                    len(plan.scheduled_tasks), len(plan.skipped_tasks), plan.total_minutes)
        return plan
