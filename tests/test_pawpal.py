from datetime import date, timedelta

FUTURE = date.today() + timedelta(days=5)  # a routine that starts in the future

import pytest

from pawpal_system import Owner, Pet, Scheduler, Task


def test_mark_complete_changes_status():
    task = Task("Morning walk", 30, "high")
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_adding_task_increases_pet_task_count():
    pet = Pet(name="Mochi", species="dog")
    assert len(pet.tasks) == 0

    pet.add_task(Task("Feeding", 10, "high"))

    assert len(pet.tasks) == 1


def test_daily_task_creates_next_occurrence_tomorrow():
    pet = Pet(name="Mochi", species="dog")
    pet.add_task(Task("Walk", 30, "high", frequency="daily", due_date=FUTURE))

    nxt = pet.mark_task_complete("Walk")

    assert pet.tasks[0].completed is True
    assert nxt is not None and nxt.completed is False
    assert nxt.due_date == FUTURE + timedelta(days=1)
    assert pet.tasks == [pet.tasks[0], nxt]


def test_weekly_task_creates_next_occurrence_in_seven_days():
    pet = Pet(name="Luna", species="cat")
    pet.add_task(Task("Grooming", 20, "low", frequency="weekly", due_date=FUTURE))

    nxt = pet.mark_task_complete("Grooming")

    assert nxt.due_date == FUTURE + timedelta(days=7)


def test_one_off_task_does_not_recur():
    pet = Pet(name="Mochi", species="dog")
    pet.add_task(Task("Vet visit", 60, "high", frequency="once"))

    assert pet.mark_task_complete("Vet visit") is None
    assert len(pet.tasks) == 1


def _owner_with(*pet_tasks):
    owner = Owner(name="Jordan", available_minutes=120)
    for pet_name, tasks in pet_tasks:
        pet = Pet(name=pet_name, species="dog")
        for task in tasks:
            pet.add_task(task)
        owner.add_pet(pet)
    return owner


def test_conflict_detected_across_pets_at_same_time():
    owner = _owner_with(
        ("Mochi", [Task("Walk", 30, "high", time="09:00")]),
        ("Luna", [Task("Vet call", 15, "medium", time="09:00")]),
    )

    warnings = Scheduler(owner).detect_conflicts()

    assert len(warnings) == 1
    assert "Walk" in warnings[0] and "Vet call" in warnings[0]


def test_back_to_back_tasks_are_not_a_conflict():
    owner = _owner_with(
        ("Mochi", [Task("Walk", 30, "high", time="09:00"), Task("Feed", 10, "high", time="09:30")])
    )

    assert Scheduler(owner).detect_conflicts() == []


def test_untimed_and_completed_tasks_are_ignored():
    done = Task("Walk", 30, "high", time="09:00", completed=True)
    owner = _owner_with(
        ("Mochi", [done, Task("Feed", 10, "high", time="09:00"), Task("Play", 10, "low")])
    )

    assert Scheduler(owner).detect_conflicts() == []


# ---- Sorting ----

def test_sort_by_time_is_chronological_with_untimed_last():
    owner = _owner_with(
        ("Mochi", [Task("Dinner", 10, "low", time="18:00"), Task("Litter", 5, "low")]),
        ("Luna", [Task("Walk", 30, "high", time="07:30"), Task("Lunch", 10, "low", time="12:15")]),
    )

    ordered = Scheduler(owner).sort_by_time(owner.get_all_tasks())

    assert [t.title for t in ordered] == ["Walk", "Lunch", "Dinner", "Litter"]


def test_sort_by_time_keeps_original_order_for_ties():
    a = Task("A", 10, "low", time="09:00")
    b = Task("B", 10, "high", time="09:00")
    owner = _owner_with(("Mochi", [a, b]))

    assert Scheduler(owner).sort_by_time([a, b]) == [a, b]


def test_sort_by_time_handles_empty_list():
    assert Scheduler(Owner("Jordan", 60)).sort_by_time([]) == []


# ---- Filtering ----

def test_filter_by_pet_and_status():
    done = Task("Walk", 30, "high", completed=True)
    owner = _owner_with(
        ("Mochi", [done, Task("Feed", 10, "high")]),
        ("Luna", [Task("Play", 10, "low")]),
    )

    assert owner.filter_tasks(pet_name="Mochi") == owner.pets[0].tasks
    assert owner.filter_tasks(completed=True) == [done]
    assert [t.title for t in owner.filter_tasks(pet_name="Mochi", completed=False)] == ["Feed"]
    assert owner.filter_tasks(pet_name="Nobody") == []


# ---- Recurrence edge cases ----

def test_completing_unknown_or_already_completed_task_raises():
    pet = Pet(name="Mochi", species="dog")
    pet.add_task(Task("Walk", 30, "high", frequency="once"))
    pet.mark_task_complete("Walk")

    with pytest.raises(KeyError):
        pet.mark_task_complete("Walk")  # already done
    with pytest.raises(KeyError):
        pet.mark_task_complete("Nope")


def test_recurring_task_with_no_due_date_recurs_from_today():
    pet = Pet(name="Mochi", species="dog")
    pet.add_task(Task("Walk", 30, "high", frequency="daily"))

    nxt = pet.mark_task_complete("Walk")

    assert nxt.due_date == date.today() + timedelta(days=1)


def test_next_occurrence_is_a_separate_task_that_can_recur_again():
    pet = Pet(name="Mochi", species="dog")
    pet.add_task(Task("Walk", 30, "high", due_date=FUTURE))

    second = pet.mark_task_complete("Walk")
    third = pet.mark_task_complete("Walk")

    assert second is not pet.tasks[0]
    assert third.due_date == FUTURE + timedelta(days=2)
    assert len(pet.tasks) == 3


# ---- Conflict edge cases ----

def test_two_tasks_for_same_pet_at_exact_same_time_conflict():
    owner = _owner_with(
        ("Mochi", [Task("Walk", 30, "high", time="09:00"), Task("Bath", 20, "low", time="09:00")])
    )

    warnings = Scheduler(owner).detect_conflicts()

    assert len(warnings) == 1
    assert "for Mochi" in warnings[0]


def test_one_long_task_conflicts_with_each_task_inside_it():
    owner = _owner_with(
        ("Mochi", [
            Task("Grooming", 90, "low", time="10:00"),
            Task("Meds", 5, "high", time="10:15"),
            Task("Treat", 5, "low", time="11:00"),
        ])
    )

    assert len(Scheduler(owner).detect_conflicts()) == 2


def test_pet_with_no_tasks_and_owner_with_no_pets_have_no_conflicts():
    assert Scheduler(Owner("Jordan", 60)).detect_conflicts() == []
    assert Scheduler(_owner_with(("Mochi", []))).detect_conflicts() == []


# ---- Next available slot ----

def test_next_slot_is_start_of_day_when_nothing_is_scheduled():
    assert Scheduler(Owner("Jordan", 60)).find_next_available_slot(30) == 8 * 60


def test_next_slot_skips_past_a_busy_block():
    owner = _owner_with(("Mochi", [Task("Walk", 60, "high", time="08:00")]))

    assert Scheduler(owner).find_next_available_slot(30) == 9 * 60


def test_next_slot_uses_a_gap_between_tasks_when_it_fits():
    owner = _owner_with(
        ("Mochi", [Task("Walk", 60, "high", time="08:00"), Task("Vet", 30, "high", time="10:00")])
    )
    scheduler = Scheduler(owner)

    assert scheduler.find_next_available_slot(60) == 9 * 60  # 09:00-10:00 fits exactly
    assert scheduler.find_next_available_slot(90) == 10 * 60 + 30  # too big for the gap


def test_next_slot_ignores_completed_tasks_and_returns_none_when_day_is_full():
    done = Task("Walk", 60, "high", time="08:00", completed=True)
    owner = _owner_with(("Mochi", [done, Task("Long", 14 * 60, "low", time="08:00")]))
    scheduler = Scheduler(owner)

    assert scheduler.find_next_available_slot(30) is None
    assert Scheduler(_owner_with(("Mochi", [done]))).find_next_available_slot(30) == 8 * 60


# --- Family / household features ---

def test_add_member_rejects_blank_and_duplicates():
    family = Owner("Rivera family", 120)
    family.add_member("Ana")
    with pytest.raises(ValueError):
        family.add_member("  ")
    with pytest.raises(ValueError):
        family.add_member("ana")
    assert family.members == ["Ana"]


def test_filter_tasks_by_member():
    family = Owner("Rivera family", 120)
    rex = Pet("Rex", "dog")
    rex.add_task(Task("Walk", 20, "high", assigned_to="Ana"))
    rex.add_task(Task("Feed", 5, "high", assigned_to="Leo"))
    family.add_pet(rex)
    assert [t.title for t in family.filter_tasks(member="Ana")] == ["Walk"]


def test_remove_member_unassigns_their_tasks():
    family = Owner("Rivera family", 120)
    family.add_member("Ana")
    rex = Pet("Rex", "dog")
    rex.add_task(Task("Walk", 20, "high", assigned_to="Ana"))
    family.add_pet(rex)
    family.remove_member("Ana")
    assert family.members == [] and rex.tasks[0].assigned_to is None


def test_recurring_task_keeps_assignee():
    task = Task("Walk", 20, "high", assigned_to="Ana", added_by="Leo")
    nxt = task.mark_complete()
    assert nxt.assigned_to == "Ana" and nxt.added_by == "Leo"


def test_remove_pet_deletes_pet_and_its_tasks():
    family = Owner("Rivera family", 120)
    rex = Pet("Rex", "dog")
    rex.add_task(Task("Walk", 20, "high"))
    family.add_pet(rex)
    family.remove_pet("Rex")
    assert family.pets == [] and family.get_all_tasks() == []
    with pytest.raises(KeyError):
        family.remove_pet("Rex")


# --- Conflicts are per person ---

def test_same_time_different_assignees_is_not_a_conflict():
    owner = _owner_with(
        ("Rex", [Task("Morning walk", 20, "high", time="08:00", assigned_to="Ana")]),
        ("Mochi", [Task("Morning walk", 20, "high", time="08:00", assigned_to="Leo")]),
    )
    assert Scheduler(owner).detect_conflicts() == []


def test_same_time_same_assignee_is_a_conflict_and_names_them():
    owner = _owner_with(
        ("Rex", [Task("Walk", 20, "high", time="08:00", assigned_to="Ana")]),
        ("Mochi", [Task("Feed", 20, "high", time="08:10", assigned_to="Ana")]),
    )
    warnings = Scheduler(owner).detect_conflicts()
    assert len(warnings) == 1 and "[Ana]" in warnings[0]


def test_next_slot_for_member_ignores_other_peoples_tasks():
    owner = _owner_with(
        ("Rex", [Task("Walk", 60, "high", time="08:00", assigned_to="Ana")]),
    )
    scheduler = Scheduler(owner)
    assert scheduler.find_next_available_slot(30) == 9 * 60
    assert scheduler.find_next_available_slot(30, member="Leo") == 8 * 60
    assert scheduler.find_next_available_slot(30, member="Ana") == 9 * 60


# --- Daily reset / calendar ---

TODAY = date.today()


def test_completing_overdue_daily_task_does_not_reappear_today():
    task = Task("Walk", 20, "high", frequency="daily", due_date=TODAY - timedelta(days=3))
    nxt = task.mark_complete()
    assert nxt.due_date == TODAY + timedelta(days=1)
    assert task.completed_on == TODAY and not nxt.is_due()


def test_once_task_never_comes_back():
    pet = Pet("Rex", "dog")
    pet.add_task(Task("Vet visit", 60, "high", frequency="once"))
    assert pet.mark_task_complete("Vet visit") is None
    assert len(pet.tasks) == 1
    assert not pet.tasks[0].occurs_on(TODAY + timedelta(days=1))
    assert pet.tasks[0].occurs_on(TODAY)  # shown only on the day it was done


def test_yesterdays_completed_task_is_not_done_today():
    task = Task("Walk", 20, "high", completed=True, completed_on=TODAY - timedelta(days=1))
    assert not task.done_on() and task.done_on(TODAY - timedelta(days=1))


def test_future_task_is_upcoming_and_ignored_by_scheduler():
    later = Task("Walk", 30, "high", time="09:00", due_date=TODAY + timedelta(days=1))
    now = Task("Feed", 30, "high", time="09:00")
    owner = _owner_with(("Rex", [later, now]))
    assert later.is_upcoming() and not later.is_due()
    assert Scheduler(owner).detect_conflicts() == []
    assert [t.title for t, _ in Scheduler(owner).generate_plan().scheduled_tasks] == ["Feed"]


def test_occurs_on_daily_weekly_once():
    start = TODAY + timedelta(days=2)
    daily = Task("D", 5, "low", frequency="daily", due_date=start)
    weekly = Task("W", 5, "low", frequency="weekly", due_date=start)
    once = Task("O", 5, "low", frequency="once", due_date=start)
    assert not daily.occurs_on(TODAY) and daily.occurs_on(start + timedelta(days=9))
    assert weekly.occurs_on(start + timedelta(days=14)) and not weekly.occurs_on(start + timedelta(days=3))
    assert once.occurs_on(start) and not once.occurs_on(start + timedelta(days=1))


def test_overdue_pending_task_shows_today():
    overdue = Task("Walk", 5, "low", frequency="once", due_date=TODAY - timedelta(days=2))
    assert overdue.occurs_on(TODAY) and not overdue.occurs_on(TODAY - timedelta(days=2))
