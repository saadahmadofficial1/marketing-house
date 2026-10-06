# Fix-log and escaped-defect entries – blank formats

Two fill-in formats for keeping a record of what went wrong so the second occurrence costs minutes instead of hours. The first is a **fix-log entry**, written the day a fault is found and fixed. The second is an **escaped-defect ledger entry**, for a defect that got past a check that said it was fine. Both come from my own workspace; the method and the real numbers behind them are in [learning-from-mistakes.md](../learning-from-mistakes.md).

Copy the block you need into your own fix log or ledger and replace every `<placeholder>`. The filled examples below are invented to show the shape; they describe no real project.

---

## A. Fix-log entry

Write it **the same day** the fault is found. A fix log written later is written from memory, and memory is what it exists to replace.

### Before you fill it in: suspect the check first

When a check reports something wrong across many items, suspect the check before the work. Open one case by hand – the file, the frame – before believing a batch. And if your fix doesn’t fail against the old code in a reproduction, your diagnosis is wrong, not your reproduction.

### The eight classes

Pick exactly one. Recognising the class is usually faster than recognising the bug.

| Class | In one line |
|---|---|
| `measurement-lied` | The tool reported a problem that doesn’t exist. |
| `name-vs-content` | A check keyed to a *name* (a track, a layer, a file) accused finished work after something was renamed. |
| `tool-damaged-work` | A tool overwrote or destroyed finished work, and its own check passed. |
| `false-learning` | Something that learns from a comparison credited a human with what the machine had made itself. |
| `guard-saw-itself` | A guard matched its own process or wrapper and refused – or logged the refusal as *ok*. |
| `silent-failure` | A run did nothing and reported success. |
| `stale-artefact` | A stored size, duration or reference went wrong when the thing it described changed. |
| `one-observation` | A rule drawn from a single case; the full set disagrees. |

### The format

```markdown
### <YYYY-MM-DD> – <the symptom, in the words of what you saw>

- **Symptom:** <What a person would OBSERVE – the wrong output, the false report, the visible
  damage. Written so someone can recognise it again without reading anything else.>
- **First rule applied:** <Did you suspect the check before the work? What did one case checked
  by hand show?>
- **Class:** <one of the eight above>
- **Root cause:** <The actual cause, not the first theory. If the first theory was wrong, say
  what it was in one line – that is useful too.>
- **Guard (as code):** <file> – <function> – <what it now refuses or reports>.
  Write NONE if no guard exists yet, and open a ledger entry (format B) as well.
- **Evidence it fails on the old case:** <How you showed the guard catches the original fault:
  the self-test assertion, the reproduction that now fails on the old code, the live refusal.>
- **Status:** OPEN | GUARDED
```

### Example (invented)

```markdown
### 2026-01-15 – “Missing captions” reported on a video that is fully captioned

- **Symptom:** The export check blocked a finished video as “no captions”; the captions are
  visibly on screen in the exported file.
- **First rule applied:** Yes. Opened the project by hand: 42 caption layers present, on a
  track the editor had renamed from “Captions” to “Subs EN”.
- **Class:** name-vs-content
- **Root cause:** The check counted layers on the track called “Captions” and found none.
- **Guard (as code):** tools/<export_check>.py – count_captions() – counts text layers by
  content and style, whatever the track is called.
- **Evidence it fails on the old case:** The self-test renames the caption track and asserts
  the count is unchanged; that assertion fails on the old version.
- **Status:** GUARDED
```

---

## B. Escaped-defect ledger entry

The ledger holds defects that **got past a passing check** – the most valuable kind, because they show exactly where your verification is blind. The best source is a diff between the last machine-built version and the human’s final edit: every difference that a check had passed is an entry.

### The ledger’s three rules

Put these at the top of the ledger file, verbatim:

> 1. Each entry escaped **once**.
> 2. An entry is closed only when a check exists that **fails on its recorded case**.
> 3. Never delete an entry. Mark it CLOSED.

A ledger with a deletion in its history can no longer tell you how often your checks were blind. Withdrawn entries (a false reading) stay in the file, marked WITHDRAWN, with the reason.

### The format

```markdown
## <YYYY-MM-DD> – <the piece of work, by a neutral label>

- **OPEN** | **CLOSED** | **WITHDRAWN**
  - **What passed:** <which check, and what it said – e.g. “box check: ok”>
  - **What the human changed:** <the correction, with the measured delta – position (dx, dy) in
    canvas units, timing in seconds, a word changed, a step added at <time>s>
  - **Closing check:** <file> – <function> – <the assertion that fails on this recorded case>.
    Leave blank while OPEN.
  - **Closed on:** <YYYY-MM-DD>, <evidence: the run or test that showed it failing on the case>
```

### Examples (invented)

```markdown
## 2026-01-20 – <tutorial A>

- **OPEN**
  - **What passed:** call-out position check: ok
  - **What the human changed:** moved the call-out box by (-0.25, +0.10) canvas units to
    uncover the label it was sitting on
  - **Closing check:**
- **OPEN**
  - **What passed:** step coverage: ok
  - **What the human changed:** added a missing step label at 23.5 s (“Click <button>”)
  - **Closing check:**
- **CLOSED**
  - **What passed:** timing check: ok
  - **What the human changed:** retimed one box 1.8 s later, to the moment of the click
  - **Closing check:** tools/<timing_check>.py – check_box_timing() – fails when a box starts
    more than 1.0 s before the click it marks
  - **Closed on:** 2026-02-02 – the self-test replays this case: the new check fails it, the
    old code let it through
- **WITHDRAWN**
  - **What passed:** step coverage: ok
  - **What the human changed:** none – the “added” labels were the build’s own; the diff tool
    did not know that track was machine-made. Tool fixed; entry kept for the record.
```

---

## How the two fit together

| Situation | Write |
|---|---|
| A fault was found and fixed, with a guard | A fix-log entry (A), status GUARDED. |
| A fault was found and fixed, but no guard exists yet | A fix-log entry (A) with guard NONE, plus a ledger entry (B), OPEN. |
| A human corrected something a check had passed | A ledger entry (B), OPEN. |
| A check now exists that fails on a ledger case | Mark the ledger entry CLOSED with its evidence; add or update the fix-log entry. |

Keep both indexed by **symptom** – what you see – rather than by cause. The cause is usually not what it first appears to be. My own symptom index is in [learning-from-mistakes.md, section 4](../learning-from-mistakes.md#4-the-fix-log-suspect-the-check-first).

**Related:**

- [learning-from-mistakes.md](../learning-from-mistakes.md) – the post-mortem, the fix log, the guards that didn’t exist and the ledger’s real numbers
- [ai-engineering-method.md](../ai-engineering-method.md) – the diagnosis loop these entries come out of
- [`../../workflows/fix-log-mining.js`](../../workflows/fix-log-mining.js) – mining an existing record into fix-log entries and checking each claimed guard against the code
- [`../../tools/sa_finaldiff.py`](../../tools/sa_finaldiff.py) – the final-edit diff that feeds the ledger
