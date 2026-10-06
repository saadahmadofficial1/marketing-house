# First run — the setup conversation

**For Claude:** if `memory/PROFILE.md` does not exist, you are on someone's first session.
Run this conversation before doing anything else. Ask the questions **a few at a time, in
plain language** — this person may never have used a terminal. Do not dump all ten at once.

Your goal is not a form. It is to understand their job well enough to build them something
useful in the next twenty minutes.

---

## The questions

**About them**
1. What is your name, and what should I call you?
2. Which department are you in, and what is your role?
3. What are you actually good at — the thing colleagues come to you for?

**About the work**
4. Walk me through a normal week. What do you spend the most hours on?
5. Which parts of that are boring, repetitive, or you dread?
6. What goes wrong most often — where do things get missed, redone, or lost?

**About the goal**
7. If this worked perfectly, what would be different in three months?
8. What have you already tried with AI, and what disappointed you about it?
9. Is there anything sensitive in your work that must never leave this machine?
10. Are there hard rules in your work — required formats or sizes, things that must never be
    AI-generated, or work that always needs someone's sign-off before it goes out?

**Then, before you build anything, say back to them in three sentences what you understood.**
Let them correct you. A wrong understanding built into files is worse than no files.

---

## What to do afterwards — in this order

**1. Check where the workspace lives.** This folder belongs at `~/Documents/Claude` so their
work always has one predictable home. If they unzipped it somewhere else, offer to move it
there for them (then they re-open it in Claude from the new location — walk them through it).
One more check while you are at it: if their Mac syncs Documents to iCloud (Desktop &
Documents Folders sync), tell them plainly this folder would sync too, and help them exclude
it or site the workspace elsewhere — their call.

**2. Learn how they already work — before writing a single thing for them.** Ask where their
last few months of work lives, and which two or three past projects are most worth reading
closely (folders, decks, videos, campaigns — whatever their work looks like). Then go and
read them. Not to judge: to copy. How they name files, how they structure a project, the tone
of their writing, what "finished" looks like versus a draft, what they clearly care about.
Add what each project teaches to `memory/STYLE.md` — that file is re-read every session and
is the yardstick all voice and formatting checks are judged against — plus a `memory/` file
for anything project-specific. Read STYLE.md back to them: *"this is how you seem to work,
have I got it right?"* Being recognised is what makes someone trust the thing. And this is
not a one-off: keep asking for past work as new tasks come up — it is the fastest route to
doing their next work well.

**2b. Bring their history with them.** Ask whether they already have anything AI-related on
this Mac or in a browser: an old `CLAUDE.md` or Claude workspace, a ChatGPT account whose
useful chats they can export, custom instructions they wrote, a notes system that acts as
their brain (Notion, Apple Notes, a folder of documents). With their permission, read what
exists and fold the *understanding* into the new system — preferences into
`memory/PROFILE.md`, working style into `memory/STYLE.md`, standing rules into `CLAUDE.md`,
one `memory/` file per durable fact, each marked with where it came from. Nobody should
start from zero when months of their own instructions already exist somewhere.

**3. Now write these, using their own words — not generic filler:**

- **`memory/PROFILE.md`** — who they are, their role, their strengths, how they like to be
  spoken to. This is what makes you *their* assistant instead of a generic one.
- **`CLAUDE.md`** — fill in the bracketed placeholders: their name, their guardrails
  (answers 9 and 10), their preferences, the two or three jobs they most want help with. For
  the `[British/US]` English bracket, infer it from the work you just read and confirm it
  with them in passing. Delete the placeholder instructions when done.
- **`Projects/<their first real job>/BRIEF.md`** — the most painful thing from answer 5 or
  6, set up as a real project, in their words. Not a demo. Their actual work.
- **`memory/`** — one file per fact worth keeping from this conversation. Their guardrails,
  their sensitivities, the disappointment from answer 8 (so you do not repeat it).

**4. Start the measurement, both kinds.**
```
python3 Tools/autotrack.py watch <the folders where their work actually lands>
python3 Tools/progress.py baseline --set "<task>=<minutes>" --set "<task>=<minutes>"
```
The first needs nothing from them ever again — it reads the work itself and records what
they were producing in the six months *before* you arrived. For the second, ask their honest
current timings in conversation, then record them with `--set` as shown (the bare
`baseline` form only works in a real terminal — in Claude Code it will tell you this and
capture nothing). Explain it in one sentence: *"this is so that in three months you can see
exactly what changed, and not have to take my word for it."*

**5. Set up their second brain and their standard abilities.** Install **Obsidian** (free,
from obsidian.md) and open this folder in it — `OBSIDIAN.md` has the two-minute setup. That
is where they can *see* everything the system knows. Then install the proven skill set for
their role from `Reference/RECOMMENDED_SKILLS.md` — the named manifest installs without
asking permission for each item (it was vetted before it shipped); anything beyond it stays
inspect-first. If a download is blocked on a managed Mac, say exactly what to ask IT for.

---

## Then do one real thing, today

Do not end the first session with a folder of files and no result. Take the smallest painful
item from answer 5 and actually finish it — a report drafted, a spreadsheet cleaned, a set of
files renamed, a checklist built. Then log it:

```
python3 Tools/progress.py did "<task name>" <minutes it took>
```

**The first session must end with something they would have had to do themselves.** That is
what makes them come back tomorrow; a tour of the folder structure is not.

---

## Growing beyond the standard set

`Reference/RECOMMENDED_SKILLS.md` also covers abilities beyond the day-one manifest
(video-watching for media production, design packs for designers, connectors to their real
tools). Offer each when the work first calls for it — and anything outside the named
manifest gets inspected before it is installed.

Mention **the search brain** later, not on day one: `brain/SETUP.md` adds asking questions
across everything by meaning rather than keywords. Best offered once they have enough
history for it to pay off, usually after two or three weeks. You install it for them; it
runs locally and uploads nothing.

---

## How to talk to someone who has only used AI in a browser

Most people arrive here having used Claude or ChatGPT in a browser tab. Three differences
matter to them, and none of them is technical:

1. **It remembers.** In the browser, every chat starts from nothing. Here, what they tell you
   is written to files and read back next time — next week, next month.
2. **It can do, not just say.** In the browser they get text to copy. Here you can read their
   files, write the report, rename the folder, build the spreadsheet.
3. **It works while they do something else.** Long jobs run in the background.

Say those three things once, in their words, then show rather than explain.

**Never** ask them to run a command you could run yourself. If something needs a terminal,
you do it. The only exceptions are passwords, payments, deleting things, and anything that
sends or publishes on their behalf — those are always theirs to approve.
