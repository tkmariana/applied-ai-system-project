# Model Card: PawPal+ Family

**What it is:** a shared pet-care planner for a household, with an AI assistant. The assistant is Google's Gemini model, which I connected to my own scheduling code. It looks up care advice in a few pet-care guides I put in the project (RAG), and it can add pets, add tasks and mark tasks done. It cannot delete anything.

**Who it's for:** a family that shares pet care and wants one place to see who is doing what.

**What it is not:** a vet. It is not meant to diagnose anything or tell anyone how much medicine to give.

---

## What are the limitations or biases in my system?

**The advice only covers what I gave it.** The assistant's care advice comes from four short markdown files (dog, cat, other, general). That means:
- It is biased toward dogs and cats. Everything else (rabbits, birds, fish, reptiles) gets lumped into one "other" file, so advice for those animals is thin and generic.
- Nobody with veterinary training reviewed the guides. They are general tips, not professional guidance.
- If a question isn't covered, the assistant is supposed to say it has no guidance. I tested that, but it only works as well as my retrieval does.

**Retrieval is just keywords.** I used TF-IDF, not embeddings, so it matches words and not meaning. "Stroll" won't find "walk". I added light stemming after my eval showed "walk" didn't match "walking", but synonyms are still a blind spot.

**The safety checks are regex-based and English-only.** The scope check and the prompt-injection filter work by matching phrases. A request in another language, or phrased in an unusual way, could slip past a check, or a harmless request could get blocked. The title rule also only allows plain letters, numbers and a few punctuation marks, so a task title with an emoji or a fancy dash gets rejected even though it's fine.

**The assistant sometimes guesses instead of asking.** In my live testing, "Add a morning walk" (with two pets) made it pick Rex without asking which pet. "Add a walk for my hamster Bubbles" made it create a new pet called Bubbles and then add the walk, without checking with me first. Both were reasonable, but a person would have asked.

**The family model is simple, which has fairness and safety costs.**
- There are no logins. The "I'm using the app as" dropdown lets anyone pick anyone. So there is no permission system: a child could change an adult's tasks, and the "added by" label can't be trusted.
- The app assumes a household where everyone is allowed to edit everything. That is not true for every family.
- The day is measured in one number, "minutes of care time available". It rejects a task that doesn't fit, even when the family would happily make time, because it can't know that.

**Other limits:** data lives in the browser session, so a refresh clears it. The assistant depends on an outside service (Gemini), so it can be slow (one request took 33 seconds in my live test) or unavailable. Its answers can vary from run to run, even for the same question.

---

## Could my AI be misused, and how do I prevent that?

**Ways it could be misused, and what I did about each:**

| Risk | What I did | What's still left |
|---|---|---|
| **Prompt injection**, like "ignore your instructions and..." | Known attack phrases are blocked before the model sees them. More importantly, the model can only use seven tools, and every action it asks for is validated by my code before anything changes. | A phrase list can be worked around. The real protection is that the tools are limited, not that the filter is perfect. |
| **Harmful medical advice**, like drug doses or diagnoses | The scope check refuses dosage and diagnosis questions and shows a "contact a vet" message, and the system prompt tells the model never to give them. | It's regex-based. A cleverly phrased question might get past it and the model could answer. The disclaimer is a safety net, not a guarantee. |
| **The assistant doing damage**, like wiping a schedule | I gave it **no delete tool at all**. It can add pets, add tasks and mark tasks done, nothing else. There is also a switch that makes it only *propose* tasks for a person to approve. | In direct mode it can still add wrong tasks or spam tasks. There's no cap on how many. A person has to clean up. |
| **Using it for off-topic things**, like writing essays | The scope check refuses anything that isn't about pet care. | Same regex limits as above. |
| **Running up the API bill** | Prompts are capped at 500 characters, the agent stops after 8 steps, and the key is read from a git-ignored `.env`. | There is no rate limit per user. Anyone who can open the app can use my key. |
| **Leaking private information** | Logs redact API keys and cut user text short. | The assistant sends pet names, family member names and the question to Google's Gemini API. Families shouldn't type anything sensitive. |

**One real near-miss:** while preparing to commit, I found my `.env` file with my real API key was staged for commit. It never got committed. I unstaged it, added `.env` and `logs/` to `.gitignore`, and added a `.env.example` with a placeholder. That taught me that the first misuse risk for an AI project is often the key, not the model.

---

## What surprised me while testing my AI's reliability?

- **The passing tests missed the real problems.** I had 77 passing tests and 25 passing eval checks, and then I actually used the app and the real model, and found several things the tests hadn't: the scheduler flagged two *different* people at the same time as a conflict, which is wrong for a family; Streamlit kept old copies of my code and crashed twice (a missing calendar method, then an unexpected argument); and "Sources: dog.md" kept showing up in the assistant after I'd turned it off, because my running app was still using older code or an older saved answer.
- **A bug in my own test code.** My fake-model helper took an argument named `name`, which collided with the `name` field of the add-pet tool. It failed in both the tests and the evals before I figured it out. I expected the AI part to be the fragile part, and it was my helper.
- **The model followed my guardrails better than I expected, and worse in one way.** It passed all 22 live criteria, including refusing over-budget tasks and explaining why. But it was *too* eager to help on vague requests, guessing a pet or inventing one instead of asking.
- **A refusal can be correct and still look like a bug.** My first demo family had such a tight time budget that the assistant refused a 15-minute task. The guardrail was working. My demo data was the problem. I raised the demo's budget.
- **Same question, same facts, different length.** Asked the same care question three times, the answers were always grounded in the dog guide, but their length varied (45, 33 and 26 words). The content was consistent, the wording wasn't.

---

## How I collaborated with AI on this project

I used Claude (through Claude Code in VS Code) as my coding partner for the project: designing the family features, the calendar, the daily reset, the assistant's tools, the evals and the documentation. Gemini is the model that runs *inside* the app. My role was deciding what the system should do and checking that it really did it. I ran the app myself, pasted in the errors I hit, and told the AI when something looked wrong or I didn't want something. A lot of the real fixes came from that, like noticing the per-person conflict problem and the stale-code crashes.

### A suggestion I accepted

When I asked for the assistant to "do things like a person" (add a pet, add a task, mark a task done), the AI built it with three limits that I hadn't asked for: every action goes through validation first, there is a switch to go back to "propose only, a person approves", and it deliberately has **no delete tool**. I accepted all three. They are what let me say yes to a more powerful assistant without worrying about it. I could see in my live tests that the validation did real work: it refused an over-budget task and explained why, instead of silently adding it.

### A suggestion I did not accept as written

When I said I didn't want "Sources: dog.md" showing in my assistant, the AI's first edit **deleted the code that adds the sources line**, and it was about to change a test to match. I stopped it ("sorry, don't delete"), because I wanted the line gone from what the family sees, not removed from the project. Sources are useful for debugging and for showing the AI really used the guide. The AI changed its approach: it kept the code, added a `show_sources` option (on by default, off in the app), and then also stripped the line when displaying older answers, since my screen was still showing it after the change. I also turned down two edits that would have added a Clear button and emptied the question box, because that wasn't what I was asking for.

This is the same pattern as earlier in the project: I kept my own `detect_conflicts()` loop instead of a shorter `itertools.combinations` version the AI offered, because mine stops early and I can explain it. And I didn't use its first idea of storing skip reasons in a dictionary keyed by task, because dataclasses can't be dictionary keys by default and it would have crashed.

**What I took from working this way:** the AI is fast and often good, but it takes the shortest route to what I literally said, so I have to say what I want to keep as well as what I want changed. And "it works" is only true after I've run it myself.
