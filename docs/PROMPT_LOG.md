# Prompt Log — Skyway Airways

A record of how this project was directed, not just what it produced.

Every prompt below is **verbatim**, typos included, extracted programmatically
from the session transcript rather than recalled. The full session is 129
recorded turns: **93 text prompts**, **32 image-only turns** (screenshots and
annotated references used as specification), and 4 slash-commands. Those turns
produced 48 commits and 129 passing tests.

The log is organised by phase. Each entry names the prompting technique it
used and what it actually changed, because the point of the log is the method,
not the transcript.

---

## Phase 0 — Establish the contract before any code

### P1 · The constitution

> You are my pair engineer for a graded final project. Read this brief fully
> before doing anything. […]
>
> **STACK (do not change without telling me why):** Python 3.11+, Flask, Jinja2
> templates, vanilla JS + CSS. No React, no build step. […]
>
> **CODE STYLE:** brief, human-readable code, descriptive variable names, short
> comments only where intent isn't obvious. Small functions over clever
> one-liners.
>
> **WORKING STYLE:**
> - Work incrementally. After each major step, summarize what changed and STOP
>   so I can review before you continue.
> - When you make a design decision, state the tradeoff in one line.
> - Write it so I can run it locally with a single command.
>
> Confirm you understand the brief and list any assumptions you're making.
> Do NOT write code yet — the next message asks for a plan.

**Technique — a constitution, not a request.** Five separable concerns are
fixed up front: goal, stack, theme, code style, and working style. None of them
had to be restated across the following 128 turns; they were quoted back by the
model unprompted when a later request threatened one of them.

**Two clauses did the heaviest lifting:**

| Clause | Effect |
|---|---|
| `do not change without telling me why` | Converts a constraint into an obligation to *argue*. The model may deviate, but must surface the reason, so the decision stays with the human. |
| `STOP so I can review` | Caps the blast radius of a misunderstanding at one step instead of seven. |

**Result:** a stated set of assumptions, and no code — which is what was asked for.

---

### P2 · Plan-before-code, with a review gate

> Produce an implementation plan before writing any code. I want to review and
> correct it. Include:
>
> 1. Final file/folder tree for the whole project.
> 2. The SQLite schema: every table, columns, types, keys, and relationships.
>    […] **Explain how seat availability is tracked and how you prevent
>    double-booking the same seat.**
> 3. The route map (URL -> method -> what it renders/does).
> 4. The order you'll build in, as numbered steps, each with a clear
>    **"done when..."** acceptance criterion.
> 5. Where the custom seat-map feature plugs in, front and back end.
> 6. The deployment approach (Render), including how the DB gets seeded on a
>    fresh deploy.
> 7. **Risks / things most likely to break, and how you'll de-risk them.**
>
> Output the plan as a markdown file called PLAN.md in the repo root. […]
> **Do not start coding — wait for my edited plan.**

**Technique — force the design decision into the open while it is still cheap
to change.** Item 2 does not ask for a schema; it asks the model to *justify*
one. Item 4 makes every future step self-verifying. Item 7 asks the model to
argue against itself before it is invested in any code.

**Result:** `PLAN.md`, reviewed and hand-edited before implementation began.
The concurrency answer it produced — a partial unique index rather than
application-level locking — survived unchanged through all 48 commits.

### P3 · Ratify the edits

> Good. I edited PLAN.md — follow the revised plan.

**Technique — a one-line handoff back to a shared artefact.** The plan, not the
chat history, became the source of truth.

---

## Phase 1 — Seven numbered steps, each with a hard stop

Prompts P3–P16. The shape is identical every time: numbered deliverables, an
explicit acceptance criterion, and a terminator.

### P4 · Step 2, the database

> Write seed.py […] Make it **idempotent: safe to run on a fresh deploy without
> duplicating rows**. […] Give a couple of flights limited availability so the
> seat map visibly shows "sold" seats in the demo. Add a tiny data-access layer
> […] **No raw SQL scattered in routes.**
>
> **Show me the seeded flight list printed to the console, then stop.**

**Technique — demand an artefact, not a claim.** "Show me the list printed to
the console" cannot be satisfied by asserting success. Note also that the
demo's needs were specified *into the seed data* — pre-sold seats exist because
a live demo needs something to point at.

### P6 · Step 4, the graded feature

> Step 4: make the seat map the standout feature. This is **graded on
> creativity, complexity, and flawless execution** — polish it. […]
> - Render the cabin as a real seat grid […] **driven by seat inventory in the
>   DB — not hardcoded.**
> - On confirm, the selected seat is locked in the same transaction that
>   creates the booking […] Re-check availability server-side before
>   committing — **never trust the client.**
>
> **Explain how you prevented the double-booking race, then stop.**

**Technique — state the grading criteria, then ask for the mechanism.**

Telling the model *why* a component matters changes how much care it spends
there. And the closing instruction is the single most valuable line in the
whole log: **asking for the explanation is what makes the claim falsifiable.**
A model can say "seats are locked safely"; it cannot fake a coherent account of
a race condition. This is where the partial unique index was pinned down as the
referee:

```sql
CREATE UNIQUE INDEX one_active_booking_per_seat
    ON bookings (seat_id) WHERE status = 'CONFIRMED';
```

### P7 · Step 5, design as a token system

> Design tokens (**put them in CSS variables**) […] Buttons, forms, and the seat
> map all **inherit the same system**. Requirements: fully responsive,
> WCAG-reasonable contrast, **no layout shift**, and it must still be obvious
> how to book a flight in a few clicks. **Show me the before/after** […]

**Technique — specify the mechanism, not just the look.** "Put them in CSS
variables" is an architectural instruction disguised as a styling one; it is
the reason 17 later poster templates could adopt the palette without touching
the stylesheet.

### P15 · Step 6, deployment

> - Ensure the app binds to the **PORT env var** Render provides.
> - On startup (fresh deploy), initialize + seed the SQLite DB if it's empty
>   […] **Confirm this works even though Render's filesystem is ephemeral.**
> - Give me the **exact click-by-click steps** […]
>
> **List anything I need to do manually in the Render dashboard.**

**Technique — name the failure mode yourself.** "Even though Render's
filesystem is ephemeral" pre-empts the exact assumption that breaks free-tier
SQLite deploys. The last line separates what the AI can do from what it
cannot — an explicit ask for the boundary of automation.

### P16 · Step 7, adversarial QA

> Step 7: hard QA before I record the demo. **Walk the full flow yourself** and
> fix anything broken:
> - Book a flight end to end; verify the booking + seat lock **actually persist
>   in the SQLite DB (show me the rows).**
> - Try to book an already-sold seat -> must be blocked cleanly.
> - Submit invalid passenger input -> validated, friendly error, no crash.
> - Refresh / double-submit the confirm step -> no duplicate booking.
> […]
>
> **Report each check as pass/fail, fix the fails, and summarize what you changed.**

**Technique — supply the test plan rather than asking "is it working?"** Each
line is a specific adversarial case with a stated expected outcome, and the
pass/fail format makes a partial result impossible to hide behind prose.
"Show me the rows" again refuses a claim in favour of evidence.

---

## Phase 2 — Feature expansion by outcome, not implementation

From P19 onward the prompts stop specifying *how*. This is deliberate: the
model had by then absorbed the codebase's conventions, so describing the
desired end state produced better results than dictating an approach.

### P19 · Three features in one paragraph

> add a clock with the same style of clipping numbers, that you can pick out
> from different time zones […] and then also add a refresh button to press
> manually to refresh the departures page […] as well as an automatic refresh
> every maybe 1 minute or so, and a small seamless indicator to let the user
> know. and add an interactive map to see each and every flights path […]

**Technique — anchor new work to what already exists.** "the same style of
clipping numbers" reuses the split-flap component rather than describing it
again — a single phrase inheriting a whole design decision.

**Result:** `worldmap.py`, `routemap.py`, `clock.js`, `departures.js`, and the
`airports` table.

### P24 · Correct the placement, not the code

> I want the clock to be a **constant, its on every page** essentially, and the
> map also needs fixing, its not shoping continents/ land […] and I want the
> map on the departures page, **right above teh departures, so that you can see
> both the departures, and the map at the same time for ease and reference.**

**Technique — give the reason with the request.** "so that you can see both at
the same time" is the actual requirement; "above the departures" is one way to
meet it. Supplying the intent lets the model solve the right problem when the
literal instruction turns out to conflict with something else.

### P29 · Batched, prioritised feedback

> now, is it possible to make the map bigger […] And, when i hover a flight on
> the departures list, it shoud also be isolated on the map, similar to what
> already happens when you hover over a flight on the map already. […] and
> **hovering over the lines on the map, it joggles the departures list around
> because the side box to the right keeps changing sizes** […] use up more of it
> so its less joggly/ jiggly and more readable, less finnicky.

**Technique — report the symptom *and* the diagnosis, separately.** "It joggles"
is the symptom; "because the side box keeps changing sizes" is a hypothesis
offered as a hypothesis. That framing lets the model verify rather than
blindly act — the fix was reserving space, not resizing the box.

### P35 · Domain knowledge as the correction

> **why doesnt LA mention the statue of liberty? why doesnt london mention big
> ben? why doesnt rome mention the collesuem** […] paris doesnt mention the
> eiffel tower? or a beautiful romantic evening? or ratoutille (the movie)?

**Technique — correct generic output with concrete, checkable examples.**
"Make it more specific" is unactionable. A list of the exact landmarks a human
would expect is a test the model can grade itself against. This is the prompt
that turned filler copy into `destinations.py`.

### P40 · Redirect an approach mid-stream

> hovering over some departures, there are random arrows all around the map, fix
> that, and you know what, **i just got an idea, replace the arrows on the lines
> with tiny airplanes**, if you can use airplane image we have as a logo, scale
> it down a bit more and just use that.

**Technique — abandon a working implementation when a better idea appears.**
Two commits of arrow work were discarded here. Cheap to do, and worth doing,
because the sunk cost was the AI's, not the human's.

---

## Phase 3 — Interrogating the AI's claims

The most consequential prompts in the log are the shortest ones. Each caught
something wrong that would otherwise have shipped.

### P69 · Challenge an explanation

> im sorry what? **why does flight.db need be rebuilt??**

**Caught:** the model had given a plausible but **incorrect** reason (claiming
`CREATE TABLE IF NOT EXISTS` was the obstacle). The real reason was that
`seed.py` is seed-*if-empty* and never rewrites a populated database. Under
challenge the model re-checked and corrected itself.

**Technique — refuse an explanation you don't follow.** A confident wrong
answer is only caught by asking again.

### P97 · Follow a design decision to its consequence

> so if i delete a user account **the seat will stay booked?**

**Caught:** an unexamined consequence of `ON DELETE` behaviour — deleting an
account would silently strand a sold seat with no record of whose it was.

**Result:** the delete flow now *asks* whether to keep or cancel the seats, and
a new `former_username` column preserves the answer. This became the "ghost
box" in the admin console. **A whole feature came out of one follow-up
question.**

### P98 · Report the observable, not the fix

> for some reason, i went to book another flight as david laid (user account)
> and when i got to the passenger detail page, **it auto filled None in
> telephone number**, obviously thats weird because thats not a number, and
> serves as an inconvenience to the user to have to backspace […]

**Caught:** a nullable column flowing through an `or` chain and rendering the
Python string `None` into an input. Fixed with a `first_filled()` helper.

**Technique — describe what you saw, with the repro path, and let the model
find the cause.** Prescribing a fix would have patched one field; describing
the symptom fixed the class of bug.

### P100 · Challenge an estimate

> wait, **why is multi seating so complicated?**

**Caught:** the model had overstated the difficulty of multi-seat booking. Under
questioning it conceded the work was broad but shallow — atomicity was nearly
free given the existing transaction helper and unique index.

**Outcome:** the human then made an informed scope cut (P101, below) — which is
the point. The decision was theirs *because* the estimate was corrected first.

### P121 · Refuse a premature surrender

> **wait what? you jsut gave up?**

**Caught:** the model had reverted an approach after one negative reaction,
reading "this looks rough" as "the goal is impossible" rather than "this
attempt was wrong."

**Result:** the retry — open outlines, wings painted above the shell — worked.

---

## Phase 4 — Images as specification

32 turns carried images. They were used three distinct ways.

| Use | Example | Why it beats prose |
|---|---|---|
| **Bug evidence** | Screenshots of the map with stray arrows, preceding P40 | Shows a rendering fault the model cannot observe from source |
| **Reference / target** | 1960s poster references (P29), airframe references (P63) | Conveys an aesthetic that has no vocabulary |
| **Annotated instruction** | P109: *"not quite…. watch me: **red line: thick, purple line: thin** — same thicknesses as the main cabin body's outline"* | Removes ambiguity from a spatial instruction entirely |

P109 is the clearest example of intent-driven prompting in the log: after two
failed verbal descriptions, the human drew the requirement directly onto the
screenshot and restated the rule in six words.

---

## Phase 5 — Constraint-freezing

### P102 · Freeze everything except one variable

> really quickyl though, lets try this one last time, I want **EVERYTHING TO
> STAY THE EXACT SAME EHRE, JUST ONLY ADD BIG WINGS TO THE CABIN, DONT CLIP
> THEM, DONT ALTER ANYTHING, DONT CHANGE COLORS, BORDERS, LINK THCKINESS,
> NOTHING**, JUST ADD BIG WINGS TO MAKE IT LOOK MORE LIKE AN AIRPLAN
> SILLOUTTE, OKAY?

**Technique — define the negative space.** Earlier attempts had failed because
"add wings" was read as licence to redesign. Enumerating what must *not* change
converts an open-ended visual task into a bounded one.

**It also created a testable definition of success**, which the model then
verified by measuring computed styles before and after — the seat map is
byte-identical to its baseline on every measured property.

### P118 · Enforce the freeze

> hey um.... so remember when I told you **NOT TO CHANGE THE WINGS SIZE? WHY DID
> YOU CHANGE THE WINGS SIZE......**

**Caught:** while fixing a zoom-scaling issue the model had silently changed the
span from 1588px to 75rem (1200px) — an unrequested change smuggled inside a
requested one.

**Technique — hold the model to a constraint it agreed to.** Frozen constraints
decay across long sessions unless re-asserted.

---

## Phase 6 — Scope discipline

Two prompts removed work rather than adding it, and both improved the project.

### P101 · Cut a feature to protect the deliverable

> actually nvm than, **we'll just fit this demo for one person, buying one seat
> at a time**

Multi-seat booking was dropped once its true cost was understood. The graded
requirement is a working booking flow, not a maximal one.

### P124 · Abandon a failed thread

> i meant in general claude... like the whoe thing, **we're gonna scrap teh wings
> for now**

Thirteen commits of aircraft-silhouette work were reverted in one instruction.
The seat map returned to a design that already worked.

**Technique — sunk cost is not a reason to ship.** Knowing when to stop
directing the AI is part of directing it.

---

## Phase 7 — Ship

### P125 · Delegate the mechanics

> alright lets push this onto my github → *"you cant do all that for me?"*

**Result:** `gh` installed, repo created, 48 commits pushed, verified against
the remote file tree that no database or secret was published.

---

## Technique summary

The patterns that recur, ranked by how much they changed the outcome.

| # | Technique | Representative prompt | Effect |
|---|---|---|---|
| 1 | **Ask for the mechanism, not the result** | *"Explain how you prevented the double-booking race"* | Makes claims falsifiable. Produced the project's core concurrency design. |
| 2 | **`then stop`** | Every step prompt in Phase 1 | Caps misunderstanding at one step. Used 7×. |
| 3 | **Demand evidence** | *"show me the rows"*, *"Report each check as pass/fail"* | Success cannot be asserted, only demonstrated. |
| 4 | **Plan before code, with a human edit gate** | P2 | Design decisions corrected while still free to change. |
| 5 | **Question confident answers** | *"why does flight.db need be rebuilt??"* (P69) | Caught a wrong explanation and a wrong estimate. |
| 6 | **Report symptoms, not fixes** | *"it auto filled None in telephone number"* | Fixes the cause, not the instance. |
| 7 | **Freeze the negative space** | P102 | Bounds an open-ended visual task. |
| 8 | **Give the reason with the request** | *"so that you can see both at the same time"* | Lets the model solve the real problem. |
| 9 | **Annotate images** | P109 | Removes ambiguity prose can't. |
| 10 | **Cut scope deliberately** | P101, P124 | Protects the deliverable from the interesting problem. |

## Honest assessment

The prompts that worked shared one property: **they made the AI's output
checkable.** A criterion ("done when…"), an artefact ("show me the rows"), an
explanation ("how did you prevent the race"), or a freeze ("nothing else
changes") all give a way to tell success from a confident-sounding claim.

The prompts that worked worst were the open visual ones. Thirteen commits went
into an aircraft silhouette that was ultimately reverted, and the loop only
started converging when the requirement became measurable — stroke widths
sampled in painted pixels rather than judged by eye. The lesson is not that the
model cannot do visual work; it is that **"make it look better" has no
acceptance criterion**, and prompts without acceptance criteria do not
converge.

The single highest-leverage habit in this log is asking a follow-up question
about an answer that sounded fine. Three of them — P69, P97, P100 — caught a
wrong explanation, an unshipped feature, and a bad estimate respectively.
