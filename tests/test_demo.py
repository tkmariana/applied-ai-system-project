from demo_data import build_demo_household
from pawpal_system import Scheduler


def test_demo_household_is_realistic_and_valid():
    family = build_demo_household()
    assert family.members == ["Ana", "Leo", "Sofia"]
    assert [p.name for p in family.pets] == ["Rex", "Luna"]
    assert len(family.get_all_tasks()) == 8
    assert all(t.assigned_to in (None, *family.members) for t in family.get_all_tasks())


def test_demo_has_no_conflicts_because_overlaps_are_different_people():
    family = build_demo_household()
    assert Scheduler(family).detect_conflicts() == []


def test_demo_vet_visit_is_upcoming_not_due_today():
    family = build_demo_household()
    vet = next(t for t in family.get_all_tasks() if t.title == "Vet check-up")
    assert vet.is_upcoming() and not vet.is_due()
    # and it fits in the family's time budget today (upcoming tasks don't count yet)
    plan = Scheduler(family).generate_plan()
    assert plan.skipped_tasks == []
