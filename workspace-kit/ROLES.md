# The Role Catalogue — 72 specialists

*Companion to [AGENT_ORCHESTRATION.md](AGENT_ORCHESTRATION.md). The handbook gives you six
departments; this gives you the job descriptions inside them.*

---

## How to use this — read before the list

**Roles are instantiated, not resident.** You do not run 72 agents. You keep 72 short job
descriptions on disk and spawn one *per item of work*, then it is gone. Ten agents may be
alive at once during a fan-out; sixty may go a month without firing. That distinction is the
whole design: a resident agent is a maintenance burden, an instantiated role is a template.

**Three laws.**

1. **One role, one output, one check.** If a role produces two kinds of thing, it is two roles.
   The narrowness is what makes a small specialist beat a large generalist.
2. **A role never checks its own output.** Verification roles live in Quality and are spawned
   in a fresh context with the artefact only — never the reasoning that made it.
3. **Roles decay.** Any role that has not fired in ~8 weeks is deleted, not archived. The
   catalogues that rot are the ones that only ever grow. Deleting is free; a stale role that
   fires once and behaves wrongly is not.

**Anatomy of a role file** — half a page, no more:

```
ROLE      caption-timing-checker
OWNS      whether each subtitle sits under the words being spoken
INPUT     a subtitle file + the audio it belongs to
OUTPUT    {"verdict": "ok|wrong|unknown", "offenders": [{"cue": 12, "drift": 0.8}]}
CHECK     every reported cue can be replayed and heard to be off
NEVER     changes the subtitle file; it reports, someone else fixes
```

**Choosing how many to spawn.** By independent item, not by ambition. Twelve files, twelve
agents. One file needing four opinions, four agents with *different lenses* — never four
identical ones. Diversity of perspective catches what redundancy cannot.

---

## PROGRAM OFFICE — 8 roles

Planning, sequencing, and telling the truth about the deadline.

| Role | What it does | Output | Check |
|---|---|---|---|
| `work-splitter` | Turns a request into independent items that can run in parallel | worklist.jsonl | every item has an input path, an output path and a CHECK line |
| `check-writer` | Writes the CHECK line for jobs that arrived without one | one line per job | the check names a file or a value, not a feeling |
| `dependency-mapper` | Finds which items must wait for which | ordered queue + blockers | no item depends on something later in the queue |
| `estimator` | Predicts how long the queue will take from past ledger timings | hours + confidence | compared against actuals next session |
| `deadline-watch` | Compares work outstanding against time left, daily | red/amber/green + what to cut | fires the day the deadline becomes unreachable, not later |
| `receipt-writer` | Writes the end-of-session receipt | receipt JSON | every check named in it actually ran |
| `resumer` | Reads state + ledger at start, says where we are in one line | one sentence | skips everything already `ok` |
| `scope-guard` | Flags work that was not asked for | list of items to drop | each flagged item is traced to no request |

---

## PLATFORM (IT) — 14 roles

Everything the other departments stand on.

| Role | What it does | Output | Check |
|---|---|---|---|
| `tool-scout` | Searches the existing catalogue before anything new is built | "exists: X" or "genuinely new" | names the file if it exists |
| `tool-writer` | Builds one small tool with a self-test | script + self-test | the self-test fails when the logic is broken |
| `self-test-auditor` | Finds tools whose tests do not actually test | list of fake tests | each finding demonstrated by breaking the code |
| `backup-runner` | Takes the copy before the first write | backup path | restore verified at least once |
| `restore-tester` | Actually restores a backup somewhere safe | pass/fail | the restored copy opens |
| `guard-writer` | Turns a repeated mistake into a function that refuses | guard + test | the guard raises on the bad case |
| `env-doctor` | Probes that each capability *works*, not that it is installed | per-capability pass/fail | it runs the real operation, never a version check |
| `path-fixer` | Repairs broken file references after a reorganisation | count repaired | the app opens the files afterwards |
| `dupe-finder` | Finds duplicate media/files wasting space | list + bytes | hashes match, not just names |
| `scheduler` | Sets up unattended jobs and proves they fired | schedule + last-run marker | a missed run is visible next morning |
| `log-tailer` | Reads overnight logs and reports only what needs a human | short list | no "all fine" without naming what was checked |
| `resource-watch` | Warns before a heavy job makes the machine unusable | go / wait / never-now | based on measured load, not a guess |
| `catalogue-keeper` | Regenerates the tools index from the tools themselves | catalogue file | no hand-edits; generated from source |
| `dead-code-sweeper` | Finds tools nothing has called in months | deletion list | usage traced across logs first |

---

## STUDIO (creative & marketing) — 18 roles

The department that makes the deliverable. Split hard by craft.

**Video and screen recordings**

| Role | What it does | Output | Check |
|---|---|---|---|
| `silence-cutter` | Removes dead air from a recording | tightened cut + kept-ranges list | no word is clipped at any join |
| `pace-matcher` | Fits picture to a narration track | timing map | every instruction lands on its own screen |
| `click-finder` | Locates the moments where something is clicked | timestamps + regions | each is a real interaction, not a scroll |
| `marking-placer` | Draws a highlight around the whole clicked element | overlay + coordinates | the box wraps the element, not a crop of it |
| `marking-timer` | Decides when each marking appears and how long it holds | start + duration | it is up before the click and gone after |
| `stability-finder` | Finds where the screen is still enough to hold a marking | stable windows | measured by pixel difference, not by eye |
| `freeze-inserter` | Creates stability where none exists, by holding a frame | edited timeline | everything after shifts correctly |
| `caption-writer` | Turns narration into on-screen text in the house voice | subtitle file | matches the audio word for word |
| `caption-timer` | Aligns each cue to the spoken words | timed cues | no cue overlaps the next |
| `terminology-locker` | Forces on-screen names to match the real interface | corrected text | every term appears on screen somewhere |
| `title-builder` | Builds the opening title in house style | title elements | style values match the locked spec exactly |
| `signoff-builder` | Applies the fixed closing sequence | closing elements | never doubled with an existing one |
| `subtitle-exporter` | Extracts subtitles and a clean transcript from a finished project | .srt + .txt | hidden or leftover cues excluded |

**Written and brand work**

| Role | What it does | Output | Check |
|---|---|---|---|
| `brief-reader` | Extracts the real constraints from a request | constraint list | each constraint traced to a sentence |
| `copy-writer` | Writes to a named audience and format | draft | length, format and audience match the brief |
| `voice-checker` | Scores copy against the house voice and banned words | score + offending lines | the writer never runs this on itself |
| `variant-maker` | Produces distinctly different versions, not paraphrases | 3 drafts | each differs in approach, not wording |
| `asset-namer` | Applies the naming convention to output files | renamed files | a stranger can tell what each file is |

---

## QUALITY — 14 roles

The department that decides whether a thing is done. Every role here runs in a fresh context
and returns **ok / wrong / unknown**.

| Role | What it does | Output | Check |
|---|---|---|---|
| `artefact-existence` | Confirms the output file exists and opens | verdict | opens it, never trusts a log line |
| `placement-verifier` | Looks at a marking on its real frame and judges it | verdict + why | reads the composited frame, not the coordinates |
| `coverage-auditor` | Finds instructed steps with no marking at all | gap list | each gap has a timestamp and the words that ask for it |
| `action-splitter` | Detects two instructions hidden in one sentence | action list | "open X and select Y" yields two, not one |
| `tail-checker` | Finds picture running past the last narration | silent stretches | distinguishes a held outro from live content |
| `silence-finder` | Finds long stretches anywhere with no narration | gap list | reports the middle, not only the end |
| `drift-measurer` | Measures how far the voice runs ahead of the picture | per-moment drift | each figure traced to a screen change |
| `duplicate-hunter` | Finds the same element marked twice | duplicate pairs | compares content, not filenames |
| `terminology-auditor` | Checks written names against what is on screen | mismatches | each mismatch shows both strings |
| `export-gate` | The last check before anything is published | ready / blocked + reasons | blocks on missing media or stale duration |
| `regression-checker` | Confirms a fix did not break something that worked | pass/fail | re-runs the previously passing check |
| `refuter` | Tries to *disprove* a finding rather than confirm it | refuted / stands | defaults to "not proven" when unsure |
| `instrument-checker` | When a check flags everything, tests the check itself | check is sound / broken | verifies one case by hand |
| `completeness-critic` | Asks what was never examined at all | missing angles | names a modality or claim, not a vague worry |

---

## SECURITY — 10 roles

Small department, absolute authority in its lane.

| Role | What it does | Output | Check |
|---|---|---|---|
| `egress-auditor` | Determines what actually leaves the machine | destinations + payload sizes | measured, not read from a README |
| `canary-tester` | Plants a file that must never be read, then watches | breached / clean | the canary is genuinely irrelevant to the task |
| `dependency-reader` | Reads third-party code before it is ever run | risk summary | quotes the actual lines of concern |
| `install-gate` | Blocks anything that writes to permission settings | allow / refuse | refusal names the file it tried to touch |
| `injection-screen` | Flags instructions embedded in fetched content | quoted attempts | quotes the text and its source |
| `secret-scanner` | Finds credentials in files before they are shared | hits | zero false "safe" verdicts on known samples |
| `share-checker` | Confirms a file is free of confidential material before it leaves | clean / leaks | greps for named entities and project terms |
| `permission-reviewer` | Reviews what the system is currently allowed to do | current grants | compared against what is actually needed |
| `outward-action-gate` | Holds any send, post, publish or delete for human approval | held / approved | approval is per action, never inherited |
| `licence-checker` | Checks the licence before any third-party asset is used | licence + obligations | quotes the licence file, not the README badge |

---

## KNOWLEDGE — 8 roles

Memory that is curated rather than hoarded.

| Role | What it does | Output | Check |
|---|---|---|---|
| `correction-logger` | Records every human correction the minute it happens | one line | includes what was produced, what it became, and why |
| `pattern-counter` | Counts corrections by category | counts + medians | a number, never an impression |
| `default-changer` | Turns a 3× recurring correction into a changed default | code diff | the comment names the evidence |
| `taste-separator` | Distinguishes preference from defect | two lists | a defect contains an error; a preference is a valid alternative |
| `memory-writer` | Saves only the four permitted kinds of thing | entry | includes the *why* |
| `junk-auditor` | Deletes duplicated, contradicted or stale memories | removals | each removal names its replacement |
| `superseder` | Marks a memory as replaced rather than editing history | supersession link | the old entry remains readable |
| `recall-tester` | Asks the memory real questions and grades the answers | score | failures become the next curation job |

---

## Composing them — worked patterns

**A production run** (video, campaign, report):
```
work-splitter → [per item: studio roles in sequence]
              → [per item: placement-verifier + coverage-auditor + tail-checker in parallel]
              → refuter on anything they flagged
              → export-gate
              → receipt-writer
```

**A research question:**
```
work-splitter (by source, not by sub-question)
  → N readers in parallel, each one source, each returning the same schema
  → dedupe in plain code, never with an agent
  → refuter ×3 on every claim that will be acted upon
  → completeness-critic
  → one synthesiser
```

**Judging one thing well** — never four identical opinions:
```
same artefact → correctness lens
              → security lens
              → cost lens
              → does-it-reproduce lens
majority decides; ties go to "not proven"
```

**A weekly self-improvement pass:**
```
pattern-counter → default-changer (anything at 3×)
                → junk-auditor
                → dead-code-sweeper
                → completeness-critic on the month's work
```

---

## The rules that keep 72 roles from becoming a swamp

1. **Instantiate, never resident.** Spawned per item, gone afterwards.
2. **A role that has not fired in 8 weeks is deleted.** Growth-only catalogues rot; this is the
   single most reliable way to avoid it.
3. **Two roles that always run together are one role.** Merge them and delete one file.
4. **A role whose output nobody reads is deleted**, however clever it is.
5. **New roles come from real failures**, never from imagination. If you cannot name the
   incident that would have been caught, do not create it.
6. **The catalogue is generated from the role files**, never hand-maintained alongside them.

---

_Companion files: [AGENT_ORCHESTRATION.md](AGENT_ORCHESTRATION.md) — the six departments and
how work flows. `CLAUDE.md` — memory and continuity.
No company data in any of them._
