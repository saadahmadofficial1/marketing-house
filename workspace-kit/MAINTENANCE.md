# Keeping it healthy — and leaving with your data

Nothing here needs looking after weekly. This is for the handful of moments that come up
after a few months, when nobody remembers what to do.

---

## Once a month, ask for this

> **"Run the monthly review."**

Your assistant will: show the progress report, tidy the memory folder (removing anything
duplicated, contradicted or no longer true), archive finished projects, and tell you plainly
whether any part of the system has stopped being used.

Two minutes, and it stops the slow rot that makes these systems annoying by month six.

---

## When the memory folder gets big

It should. A hundred files after six months is healthy — it means it knows you.

What is *not* healthy is contradictory memory: two files saying different things about the
same preference. The monthly review catches that. If you ever suspect it is working from
something out of date, just say so — *"you're using an old rule about X"* — and it will find
and supersede it.

---

## When a project finishes

Say *"archive this project"*. It moves the folder aside and keeps a short summary of what was
done and what was learnt. The detail stays available; it just stops cluttering the live list.

Do not delete finished projects yourself. The summaries are what make the next similar job
faster.

---

## When you get a new laptop

Copy the whole folder across. That is the entire migration — everything it knows about you is
in these files. Two things do not travel and should be rebuilt fresh on the new machine:

- `brain/chroma_db/` (if you set up the search brain) — it rebuilds itself from your files.
- Nothing else.

Do not sync this folder live between two machines with iCloud or Dropbox while both are
running. Two assistants writing the same files at once will corrupt each other's work. Copy
it once, work on one machine.

---

## When someone else needs to pick up your work

Point them at `Projects/<the project>/` and say *"read the brief and the session log"*. The
handoff files exist precisely so that a different person — or a different assistant — can
continue without you explaining.

For a longer handover, ask: *"write a handover for this project for someone who has never seen
it."*

---

## If you stop using it

Everything is plain files. There is nothing to export and nothing to cancel:

- `Projects/` — your actual work, in normal formats
- `memory/` and `Sessions/` — plain text, readable in any editor
- `progress/` — your numbers, as JSON

Copy the folder anywhere and it is all still there. Nothing is locked in a database, nothing
needs this system to be readable, and no account holds it hostage. That is deliberate.

---

## Health check

If anything feels broken:

> **"Check the system is healthy."**

It verifies the tools still run, the folders are intact, and the memory index matches the
files. If you cannot start at all, run `claude doctor` in Terminal — it prints what is wrong
and how to fix it.
