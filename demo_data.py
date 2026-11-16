"""A ready-made household so the app (and reviewers) can be tried in one click."""

from datetime import date, timedelta

from pawpal_system import Owner, Pet, Task


def build_demo_household() -> Owner:
    """Return a family of three with two pets and a realistic mix of tasks.

    Ana's and Leo's 08:00 tasks overlap in time on purpose: they are different people,
    so the scheduler correctly reports no conflict. Rex's vet check-up is a one-time
    task due in three days, so it shows up as "Upcoming" and on the calendar, not today.
    """
    family = Owner(name="The Rivera Family", available_minutes=180)
    for member in ("Ana", "Leo", "Sofia"):
        family.add_member(member)

    rex = Pet("Rex", "dog")
    rex.add_task(Task("Morning walk", 30, "high", time="07:30", assigned_to="Ana", added_by="Ana"))
    rex.add_task(Task("Breakfast", 10, "high", time="08:00", assigned_to="Leo", added_by="Leo"))
    rex.add_task(Task("Evening walk", 30, "medium", time="18:00", assigned_to="Leo", added_by="Ana"))
    rex.add_task(Task("Bath and brush", 40, "low", frequency="weekly", assigned_to="Sofia", added_by="Sofia"))
    rex.add_task(Task("Vet check-up", 60, "high", frequency="once", assigned_to="Ana", added_by="Ana",
                      due_date=date.today() + timedelta(days=3)))

    luna = Pet("Luna", "cat")
    luna.add_task(Task("Feed Luna", 5, "high", time="08:00", assigned_to="Ana", added_by="Ana"))
    luna.add_task(Task("Clean litter box", 10, "medium", time="19:00", assigned_to="Sofia", added_by="Sofia"))
    luna.add_task(Task("Play session", 15, "low", time="20:00", added_by="Leo"))

    family.add_pet(rex)
    family.add_pet(luna)
    return family
