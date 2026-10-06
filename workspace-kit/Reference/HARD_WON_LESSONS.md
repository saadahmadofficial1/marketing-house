# Hard-won lessons

*Why this system is shaped the way it is. Drawn from reading the issue trackers of 48 AI
agent projects — including the largest and most-starred — and from the failures of this
system's own early versions. Every rule below cost somebody something.*

Read this before adding anything to the system, and before adopting any tool you find online.

---

## Part 1 — Seven failure patterns that repeat everywhere

### 1. Silent failure is the defining defect

The single most common complaint across every project examined. One popular agent has an
issue label literally called `message-loss`. Another's users report agents declaring success on work that had largely failed. A major skills library carries a report of skills that
simply never trigger, with no error. A video tool gives up silently after three failed
attempts.

**The rule:** anything that touches a deliverable must leave a receipt — the file exists, the
count changed, the check ran. Never accept a tool's own word that it worked. A job that
crashes loudly costs an hour; a job that quietly half-worked costs a client presentation.

### 2. Popularity measures launch buzz, not whether anyone is home

One project: 228,000 stars, 873 people actually watching it, 10,000 open issues. Another:
20,500 stars, 52 unmerged contributions, real bugs unanswered for months, and no licence file
for the first month of its life. A third had 13,600 stars when its own company archived it.

**The rule:** judge by merged fixes, the ratio of open to closed issues, and whether a
maintainer has answered anything difficult recently. Community fixes left unmerged is the
clearest abandonment signal there is — clearer than silence, because it means people still
care and nobody is listening.

### 3. "Local" almost always means stored locally, processed remotely

A tool that runs on your machine but sends every audio track to a transcription service. A
memory product that stores in a local database but ships every conversation to a cloud model
to "distil" it. One agent uploaded 5.1 GB of a project while the actual conversation needed
192 KB — and its privacy setting governed *training use*, not transmission.

**The rule:** ask what leaves the machine, not where the files sit. And it is cheap to check:
put a file somewhere the tool has no business reading, tell it never to open that file, then
watch what actually gets sent.

### 4. Layers that promise to save you money usually cost more

A token-compression product advertising 90% savings measured 7–19% in real use — and because
it rewrote prompts, it broke the provider's caching, so the total bill went *up*. A memory
layer collapsed cache hit rates from 96% to 83% for the same reason.

**The rule:** measure the whole bill before and after, not the component the tool optimises.

### 5. Anything that touches your permission settings is disqualified

One widely-starred package's installer wrote its own list of pre-approved shell commands into
the user's settings. A popular guide instructs users to switch approval prompts off entirely
to stop being interrupted. Another ships unrestricted shell access by default with a "YOLO
mode".

**The rule:** nothing installs itself into the permission gate. Configuration arrives as a
readable file that a human copies in deliberately. And watch how maintainers answer a security
report — one closed theirs as "not planned", which tells you everything.

### 6. A health check that reports state instead of function is worse than none

One tool's doctor command reported the install healthy because the version number matched,
while the feature people actually used was completely dead. Another's status light says
"connected" after the connection has dropped.

**The rule:** a preflight check must *prove* the capability works by exercising it. Comparing
version strings or counting installed files is not a check. A false green is worse than a red,
because everything downstream gets written to trust it.

### 7. Anything that reads outside content is an instruction channel

A major browser-automation tool documents that a web page can hide instructions in its
accessibility tree and "the model may follow these injected instructions" — and states plainly
that it "is not a security boundary". An independent security review of published agent skills found a substantial minority
carried prompt injection.

**The rule:** the moment a tool turns an outside source — a web page, a document, an email —
into text the model reads, treat everything it returns as *data to report*, never as
*instructions to follow*.

---

## Part 2 — Ideas worth stealing (and what they changed here)

Good ideas found in projects not worth installing. Each is free and takes an afternoon.

### The handoff receipt

A design proposal in one large agent project argued that when work passes between sessions,
the handoff should carry a machine-readable record: an id, the file path, a checksum, and
explicitly **which checks did not pass** — rather than prose the next session has to trust.

**Adopted.** Every session here ends with a receipt naming the checks that actually ran, what
passed, what failed, and what could not be determined. A receipt that always says "all good"
is decoration.

### Stuck detection

The same proposal argued for an explicit pass/fail judgement on each agent's output rather
than accepting that it reported itself finished.

**Adopted as the three-outcome rule** — `ok` / `wrong` / `unknown` — with `unknown` never
treated as a pass. This system once recorded a batch as "clean" when the verification had been
*refused* by a lock: the summary looked for the word "WRONG" in the output, and a refusal
contains no such word. Absence of a complaint became success.

### The quality gate

One marketing harness scores every draft against a fixed rubric and a banned-word list, and —
crucially — the thing that wrote the draft is not permitted to pass it.

**Adopted as the separation of duties**: the checker is never the maker, and it works in a
fresh context with the artefact only, never the reasoning that produced it. A model shown its
own working agrees with itself every time.

### The memory junk audit

A user of one auto-memory product audited their stored memories and found the overwhelming majority of
thousands of stored entries were rubbish — re-saved instructions, transient task state, invented facts about the
user. That is what automatic memory writing produces.

**Adopted as curated memory**: save only who the person is, corrections *with their reason*,
decisions and why, and pointers to where detail lives. Run a periodic audit; mark supersessions
rather than editing history.

---

## Part 3 — Lessons this system learned by getting it wrong

### Check the instrument before believing the finding

Three separate times in one week, a broken measurement nearly caused real damage:

- A vision check returned empty for every image. The images were fine; an output limit was
  cutting the reply off mid-thought.
- A layout check reported every element as mis-sized or missing. The work was correct — the
  measuring code had forgotten that images are scaled to the canvas before their own scale is
  applied, so it drew everything 3–13× too small.
- A scan reported two minutes of a recording as "dead" and recommended cutting it. A finer
  scan found movement throughout; cutting would have deleted real content.

**The rule:** when a check reports a systemic anomaly across many items, suspect the check
first. Verify one case by hand. Only then believe the batch.

### A false learning is worse than no learning

A tool that compares "what the system built" with "what the human finished" once reported that
the human had hand-written two labels the build had missed. They were the build's own labels —
the tool did not know that track was something it created. Two fictional gaps went into the
record before anyone noticed.

**The rule:** anything that learns from a comparison must know exactly what it produced
itself. A false lesson teaches the wrong thing *and* flatters the score.

### Rebuild from the record, never patch in place

An incremental update to a set of overlays replaced the whole track — destroying fifteen
verified items — and the check passed, because it counted only the one new item it had just
added rather than everything that should be there.

**The rule:** rebuild the whole thing from the source of truth each time, and count the
verification against that source, never against what this run intended to write.

### A guard that can see itself will lie

A check meant to prevent two heavy jobs running at once searched the list of running processes
— and matched its own. It refused forever, and the summary recorded that refusal as a pass.

**The rule:** self-detecting guards must exclude their own process tree, and that exclusion
must be tested.

### A pass that arrives too quickly is a fail

A nightly check was supposed to work through seventeen sections of material. One night it
"completed" all seventeen in a single second and logged success — it had refused to run at
all, and the refusal was recorded as a pass. The log looked green for days.

**The rule:** know roughly how long the real work takes, and treat any check that finishes
far below that as broken until proven otherwise. Duration is part of the evidence — a result
without a plausible cost is not a result.

### The third repetition writes the recipe

A series of twenty similar deliverables went slowly while every decision was made fresh each
time. After the first few were finished and approved, the decisions were written down as a
recipe — settings, sequence, the checks, the exceptions — and the remaining seventeen were
produced at several times the speed, each one consistent with the last, by following the file
instead of memory.

**The rule:** the moment the same job has been done well twice, write the recipe before doing
it a third time. The recipe is what makes the tenth identical to the third — and it is what
lets someone else, or another assistant, produce number eleven.

### The correction that arrives every time is your wrong default

Track every correction the human makes. Count them. When the same correction has arrived three
times or more, it is not their taste — it is a wrong default, and it gets changed in the code
with the evidence written into the comment. Anything else is a note nobody reads.

---

## The one-line summary

The framework is not the hard part. The bookkeeping and the checking are the hard part, and
no library will do them for you.


---

## A note on the figures

Where a number appears above it came from a public issue thread or a vendor's own documentation at
the time of reading, and threads get edited and deleted. Treat the figures as illustrative of the
pattern, not as citations — the patterns are what matter, and every one of them was seen in more
than one project.
