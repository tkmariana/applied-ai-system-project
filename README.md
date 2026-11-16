# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## ✨ Features

- **Owner, pet and task setup:** add an owner, any number of pets, and care tasks with a duration, priority, optional time, and how often they repeat.
- **Priority-based daily plan:** the highest priority tasks get scheduled first, shorter ones first within a priority, until the owner's available time runs out. Anything that doesn't fit is skipped with a reason.
- **Sorting by time:** tasks can be listed in clock order, with untimed tasks at the end.
- **Filtering:** show tasks for one pet, only pending or completed ones, or both together.
- **Conflict warnings:** if two timed tasks overlap, across all pets, the app shows a warning that names both tasks. It warns but never crashes.
- **Daily and weekly recurrence:** when a daily or weekly task is marked done, the next one is created automatically for the next day or week.
- **Next available slot:** given a task length, finds the earliest time today where it fits without overlapping an existing timed task.
- **Plan explanation:** the plan lists each task with its start and end time, then the skipped tasks and why.

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🛠️ Implementation Summary

I built the logic layer for PawPal+ in `pawpal_system.py`. It has five classes that work together:

- **Task** is one care activity (title, duration, priority, frequency, optional time, and whether it's done).
- **Pet** holds a pet's info and its list of tasks.
- **Owner** holds the owner's available time and all of their pets. `get_all_tasks()` collects every pet's tasks into one list.
- **Scheduler** gets the tasks from the owner (not from a single pet), sorts them by priority, and fits as many as it can into the available time.
- **DailyPlan** is the result: what got scheduled with start times, what got skipped and why, and an `explain()` method that prints it.

`main.py` is a quick terminal demo, and `tests/test_pawpal.py` has the first tests. The Streamlit app (`app.py`) uses this logic to show the task list, filters, conflict warnings, and the daily schedule.

## 🖥️ Sample Output

Output from running `python main.py`:

```
Today's Schedule for Jordan (90 min available)
==================================================
Scheduled:
  08:00-08:10  Feeding (10 min) [priority: high]
  08:10-08:40  Morning walk (30 min) [priority: high]
  08:40-09:00  Play session (20 min) [priority: medium]
Skipped:
  Grooming - needs 45 min but only 30 min left
Total time: 60 min
```

## 🧪 Testing PawPal+

Run the tests from the project root:

```bash
python -m pytest
```

The scheduler tests in `tests/test_pawpal.py` cover:

- **Sorting:** `sort_by_time()` returns chronological order, puts untimed tasks last, keeps ties in their original order, and handles an empty list.
- **Filtering:** `filter_tasks()` by pet, by status, by both, and with an unknown pet name.
- **Recurring tasks:** daily tasks recur the next day and weekly tasks 7 days later. One-off tasks don't recur. A task with no due date recurs from today. The next occurrence can recur again. Completing an unknown or already-finished task raises `KeyError`.
- **Conflict detection:** same-time tasks (same pet and different pets), partial overlaps, one long task covering several others, back-to-back tasks (not a conflict), completed and untimed tasks ignored, and a pet or owner with no tasks.
- **Basics:** marking a task complete and adding a task to a pet.

Test output:

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\tkmar\Documents\codepath\ai110-module2show-pawpal-starter
plugins: anyio-4.15.1, platformdirs-4.13.0
collected 18 items

tests\test_pawpal.py ..................                                  [100%]

============================= 18 passed in 0.06s ==============================
```

**Confidence Level: ⭐⭐⭐⭐ (4/5)**

All 53 tests in the suite pass (scheduler, RAG, guardrails, agent), and the sorting, recurrence, and conflict logic is covered including its edge cases. `Task.time` and `frequency` are now validated, so a bad value like `"abc"` is rejected at creation. I'm not giving 5 because `generate_plan()` isn't tested for how it handles preferred times or due dates, and the Streamlit UI has no tests.

## 🤖 AI Assistant (RAG + agent)

PawPal Assistant answers pet-care questions and proposes tasks. It combines:

- **RAG** (`rag.py`): the markdown guides in `data/knowledge/` are split by heading and ranked with TF-IDF (pure Python, light stemming). Results are filtered by the pet's species and dropped below a minimum score, so the assistant can say "no guidance" instead of guessing.
- **Agentic workflow** (`agent.py`): a Gemini function-calling loop (capped steps) with tools `search_care_guide`, `list_tasks`, `check_conflicts`, `next_free_slot` and `propose_task`. The agent only *proposes*; you approve each task in the UI and `apply_proposal` re-validates before adding it.
- **Guardrails** (`guardrails.py`): prompt length/control-character cleanup, prompt-injection phrase blocking, scope check (pet care only; no diagnoses or medication doses, with a vet disclaimer), strict field validation of every proposed task (title, 1-480 min, priority, `HH:MM`, frequency, known pet), a total-time budget check, a step cap, graceful handling of API errors and model refusals, and guaranteed source citations appended to answers. `Task` itself now rejects bad `time`/`frequency`.
- **Logging** (`logging_config.py`): rotating `logs/pawpal.log` plus console. Records retrieval queries and scores, each agent step and tool call with latency, proposals rejected, guardrail trips, and plan/conflict events. API keys are redacted and user text is truncated.

Flow diagram: [diagrams/ai_flow.mmd](diagrams/ai_flow.mmd).

### Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...           # PowerShell: $env:GEMINI_API_KEY="..."
streamlit run app.py
```

Get a free key at https://aistudio.google.com/apikey. The model defaults to `gemini-3.5-flash` (falling back to `gemini-3.1-flash-lite` if it is overloaded); override with the `PAWPAL_MODEL` environment variable (for example another model from your key's model list). Without a key the rest of the app works and the assistant section explains what to set.

### Reliability testing

- `python -m pytest` runs everything offline. `tests/test_agent.py` uses a scripted fake backend to check: proposals aren't applied without approval, invalid/over-budget/unknown-pet proposals are rejected, the step cap ends a looping agent, API errors and refusals degrade gracefully, and blocked prompts never reach the API.
- `python -m evals.run` prints a pass rate for retrieval accuracy, no-answer behavior and guardrails (currently 13/13, average top retrieval score 0.45). Building it exposed a real bug: "walk" didn't match "walks/walking", which led to adding stemming.

### Limitations

Retrieval is keyword-based, so synonyms ("stroll") won't match; the knowledge base is small and general; the scope check is regex-based and can misjudge edge cases; live Gemini behavior isn't covered by the offline tests. This is not veterinary advice.

## 📐 Smarter Scheduling

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Sorting | `Scheduler.sort_by_time()`, `Scheduler.sort_tasks()` | By time of day, or by priority then duration |
| Filtering | `Owner.filter_tasks()` | By pet name and/or completion status |
| Conflict detection | `Scheduler.detect_conflicts()` | Warns about overlapping timed tasks |
| Recurring tasks | `Task.mark_complete()`, `Pet.mark_task_complete()` | Daily and weekly tasks |
| Next available slot | `Scheduler.find_next_available_slot()` | Earliest gap that fits a new task |

### Sorting
- **`Scheduler.sort_by_time(tasks)`** orders tasks by their `"HH:MM"` time, earliest first. Zero-padded times sort correctly as plain strings, so the key is `(t.time is None, t.time or "")`. Tasks with no time go last, and ties keep their original order.
- **`Scheduler.sort_tasks(tasks)`** is what `generate_plan()` uses. It orders by priority (high first), then shorter tasks first.

### Filtering
- **`Owner.filter_tasks(pet_name=None, completed=None)`** returns the matching tasks across all pets. Each argument is optional and `None` means "don't filter on this", so they combine: `filter_tasks(pet_name="Mochi", completed=False)` gives Mochi's pending tasks. An unknown pet name returns an empty list.

### Conflict detection
- **`Scheduler.detect_conflicts()`** returns a list of warning strings, one per overlapping pair. It never raises, and an empty list means no conflicts.
- It looks at pending tasks that have a time, across **all pets** (the owner can only be in one place). Two tasks conflict when one starts before the other ends. Tasks that only touch, like 09:00-09:30 and 09:30-10:00, don't conflict.
- Tasks are sorted by start time, and the inner loop stops at the first task that starts after the current one ends, so it doesn't compare every pair.
- Tradeoff: it only warns. It doesn't move tasks, and `generate_plan()` doesn't use preferred times yet.

```
WARNING: Conflict (Mochi and Luna): 'Grooming' 16:00-16:45 overlaps 'Vet call' starting 16:00
WARNING: Conflict for Mochi: 'Grooming' 16:00-16:45 overlaps 'Medication' starting 16:30
```

### Next available slot
- **`Scheduler.find_next_available_slot(duration, after=08:00, day_end=22:00)`** returns the earliest start time (in minutes from midnight) where a task of that length fits, or `None` if nothing fits today.
- Pending timed tasks across all pets are the busy blocks. The search walks forward from `after` and jumps past any block that overlaps the candidate slot, so each block is looked at once after sorting. A gap that fits exactly is used.

### Recurring tasks
- **`Task.mark_complete()`** marks the task done. For `daily` or `weekly` tasks it also returns a new, uncompleted copy with `due_date` moved forward 1 or 7 days. Other frequencies return `None`.
- **`Pet.mark_task_complete(title)`** is the method to call from the app. It completes the first pending task with that title and adds the next occurrence to the pet's task list. It raises `KeyError` if there is no pending task with that title.
- The next due date is counted from the task's own `due_date` (or today if it has none), so finishing a task late doesn't shift the routine.
- Tradeoff: `generate_plan()` doesn't filter by `due_date` yet, so future occurrences still appear in today's plan.

## 📸 Demo Walkthrough

### What you can do in the app
Run it with `streamlit run app.py`. In the app you can:
- set the owner's name and how many minutes they have today
- add pets (dog, cat, or other)
- add tasks to a pet with a title, duration, priority, an optional time like `07:30`, and daily, weekly or once
- view all tasks in a table, sorted by time, and filter it by pet and by pending or completed
- mark a task done
- generate today's schedule

### Example workflow
1. Set the owner to 90 available minutes and add two pets, Mochi (dog) and Luna (cat).
2. Add tasks: Mochi's "Grooming" at 16:00 (45 min), Luna's "Vet call" at 16:00 (15 min), and Mochi's "Morning walk" at 07:30 (30 min, daily).
3. Look at the task table. The walk is first, and Grooming and Vet call follow at 16:00.
4. A yellow warning appears right away because Grooming and Vet call overlap. It names both tasks and says to change one time.
5. Mark "Morning walk" done. The app says the next walk is tomorrow, and a new pending walk shows up in the table.
6. Use the filters to show only Mochi's tasks, or only completed tasks.
7. Click "Generate schedule" to see today's plan, with times, and any skipped tasks with the reason.

### Scheduler behaviors you can see
- **Sorting:** the task table is ordered by time, and untimed tasks come last.
- **Filtering:** the pet and status dropdowns narrow the table.
- **Conflict warnings:** overlapping timed tasks are flagged, even between two different pets.
- **Recurrence:** finishing a daily or weekly task creates the next one.
- **Skipping:** a task that doesn't fit in the available time is skipped and the reason is shown.

### Sample CLI output
Output from `python main.py`. The tasks are added out of order on purpose, and two pairs are set up to conflict:

```
As added:
  16:00  Grooming (todo)
  07:30  Morning walk (done)
  16:30  Medication (todo)
  07:30  Morning walk (todo)
  18:00  Play session (todo)
  --:--  Litter box (todo)
  08:00  Feeding (todo)
  16:00  Vet call (todo)

Sorted by time:
  07:30  Morning walk (done)
  07:30  Morning walk (todo)
  08:00  Feeding (todo)
  16:00  Grooming (todo)
  16:00  Vet call (todo)
  16:30  Medication (todo)
  18:00  Play session (todo)
  --:--  Litter box (todo)

Mochi only:
  16:00  Grooming (todo)
  07:30  Morning walk (done)
  16:30  Medication (todo)
  07:30  Morning walk (todo)

Luna only, sorted:
  08:00  Feeding (todo)
  16:00  Vet call (todo)
  18:00  Play session (todo)
  --:--  Litter box (todo)

Pending:
  16:00  Grooming (todo)
  16:30  Medication (todo)
  07:30  Morning walk (todo)
  18:00  Play session (todo)
  --:--  Litter box (todo)
  08:00  Feeding (todo)
  16:00  Vet call (todo)

Completed:
  07:30  Morning walk (done)

Mochi + pending:
  16:00  Grooming (todo)
  16:30  Medication (todo)
  07:30  Morning walk (todo)

Conflict check:
  WARNING: Conflict (Mochi and Luna): 'Grooming' 16:00-16:45 overlaps 'Vet call' starting 16:00
  WARNING: Conflict for Mochi: 'Grooming' 16:00-16:45 overlaps 'Medication' starting 16:30

Today's Schedule for Jordan (90 min available)
==================================================
Scheduled:
  08:00-08:10  Medication (10 min) [priority: high]
  08:10-08:20  Feeding (10 min) [priority: high]
  08:20-08:50  Morning walk (30 min) [priority: high]
  08:50-08:55  Litter box (5 min) [priority: medium]
  08:55-09:10  Vet call (15 min) [priority: medium]
  09:10-09:30  Play session (20 min) [priority: medium]
Skipped:
  Grooming - needs 45 min but only 0 min left
Total time: 90 min
```

