# Role packs — deriving one for ANY job

**For Claude:** this is a method first and a list second. Seven disciplines are worked through
below as illustrations, but the person in front of you may be a photographer, an analyst, an
events coordinator, a buyer, a trainer, an engineer. Do not force them into a pack that nearly
fits — build theirs from the method, then borrow whatever is useful from the examples. A hybrid
role (a designer who also coordinates, a producer who also posts) takes both packs, and the
more painful half picks the first-week win.

---

## The method — four questions and a build

Ask these about their actual week (they follow naturally from the first-run conversation):

1. **What do you do more than once a month, the same way each time?**
   → these are the automation candidates, in order of frequency × tedium.
2. **What gets missed, or done twice, or comes back for rework?**
   → these need a checklist that runs itself and leaves evidence.
3. **What do you redo from scratch when someone changes their mind?**
   → keep the source and the settings; remaking becomes a command, not an afternoon.
4. **What are you the only person who can do?**
   → never automate the judgement. Automate everything *around* it so they have more time
   for the part only they can do.

Then write their pack in the shape below and save it as `Reference/MY_PACK.md`:

```
JOBS WORTH AUTOMATING FIRST   3-6 items from questions 1 and 2, most painful first
FIRST-WEEK WIN                one thing finishable today that they would have done by hand
THE TRAP                      the thing that must never be automated in this discipline
                              (usually: their judgement, or anything already approved)
```

**The rule for every discipline:** the first-week win must be real work they were going to do
anyway — never a demo. A tour of folders convinces nobody; a finished job does.

---

## Worked examples

Use these as patterns to reason from, not as a menu.

## Graphic designer

**Jobs worth automating first**
- Resizing and re-laying one design across every required format, keeping the layout sane
- Renaming and filing exports so a stranger can find them (`client_asset_v03_final` chaos)
- Checking a batch against the brand rules — colours, fonts, clear space, logo version
- Building the same deck or one-pager from new content each week
- Writing the handover notes nobody wants to write

**First-week win.** Take the last folder of exports and have it renamed, sorted and checked
against the brand list. It takes minutes and it removes a job they hate.

**The trap.** Never let AI regenerate artwork that has been approved. Approved files are
frozen — the system may check, rename, resize and report on them, never redraw them.

---

## Content writer / copywriter

**Jobs worth automating first**
- First drafts in the house voice, from a brief and a reference file — never published raw
- Rewriting one piece for different channels and lengths without losing the point
- Checking copy against the brand voice, the banned-word list and reading level
- Turning a transcript, a call, or a messy document into a structured piece
- Keeping a running library of what performed well, and why

**First-week win.** Feed it three pieces they are proud of, have it write the house-voice rules
from those, then use them on today's actual draft. They see their own voice described back.

**The trap.** The writer must never be the judge. Draft in one pass, check against the voice
rules in a separate one — a model that has just written something will always approve it.

---

## Coordinator / project or account management

**Jobs worth automating first**
- Turning meeting notes into who-does-what-by-when, and chasing what has slipped
- The weekly status update, assembled from what actually happened rather than memory
- Keeping one source of truth when the same project lives in email, chat and a tracker
- Spotting what is blocked, late, or waiting on someone before it becomes a problem
- Preparing the pack before a review so nobody is reading in the meeting

**First-week win.** Give it the messiest live project. Get back a single page: what is done,
what is next, what is blocked, and what needs a decision this week.

**The trap.** Sending things. Drafting a chase-up email is fine; sending it is always the
human's action, every time, no standing permission.

---

## UI/UX designer

**Jobs worth automating first**
- Auditing a screen against accessibility basics — contrast, target size, focus order, labels
- Writing and keeping the component and interaction specs nobody has time to write
- Turning research notes and session recordings into findings with evidence attached
- Building the same flow at several fidelities to compare, instead of arguing in the abstract
- Keeping design tokens and the real code honest with each other

**First-week win.** Run an accessibility pass over one real screen and get a prioritised list
with the exact element and the fix. It is unarguable, it is quick, and it usually finds
something real. No product access needed on day one: a full-resolution screenshot or exported
HTML/Figma frames on disk count as the real thing for contrast, target size and labelling —
focus-order checks wait until there is an HTML or code export to inspect.

**The trap.** Do not accept a verdict about a screen the system has not actually looked at.
"Looks fine" from a description is worthless — it must inspect the real thing.

---

## Marketing manager / team lead

**Jobs worth automating first**
- The weekly or monthly report, assembled from the numbers where they actually live —
  not from memory the night before it is due
- Turning a strategy or a request from above into clear briefs the team can act on
- Keeping the campaign calendar truthful: what is live, what slipped, what is waiting on whom
- Collecting the status of everything in flight into one page before any meeting
- Drafting the recurring communications — updates, summaries, follow-ups — for their edit

**First-week win.** This month's report, assembled from last month's version plus the export
files they already keep (ask them to download the platform CSVs first — two minutes, no
integrations needed), in their structure. An hour of dread becomes a review-and-send.

**The trap.** Sign-off. Approvals, budgets and anything performance-related about people are
the manager's judgement — the system prepares the picture, it never makes the call. And it
never messages the team in the manager's name.

---

## Media production / video

**Jobs worth automating first**
- The delivery check before anything goes out — duration, aspect ratio, audio levels, black
  frames, spec — with the evidence attached, not a "looks fine"
- Captions and subtitles: transcribed, checked against the product's real terminology, and
  consistent across a whole series
- Renaming, filing and versioning footage and exports so the right file is findable in seconds
- Cutting the same master into every platform's format without re-deciding the layout each time
- Logging rushes: what was shot, what is usable, where the good takes are

**First-week win.** Run the delivery check on the video going out this week and hand back a
defect list with timestamps. It either finds something real or proves the video clean — both
are worth having. (Duration, resolution and aspect ratio work on a stock Mac; for audio
levels and black-frame detection the assistant installs `ffmpeg` first — its job, not yours.)

**The trap.** Approved footage is frozen. Never regenerate, re-grade or "improve" a shot or an
export a human has signed off — check it, file it, report on it, never touch the pixels. And
verify the delivery spec *before* rendering, not after.

---

## Social media / communications

**Jobs worth automating first**
- Taking one approved piece and producing every platform's version — sizes, lengths, caption
  variants in the house voice — named and filed in one pass
- Keeping the content calendar honest: what is scheduled, what is missing an asset, what is
  waiting for approval
- The monthly performance log: what went out, what worked, what to do more of — from the real
  numbers, not impressions of impressions
- Drafting replies and community responses for a human to send
- Watching for the recurring dates and campaigns and preparing them before they are urgent

**First-week win.** One approved asset in, the complete set of platform versions out —
correctly sized, captioned in the house voice, named so a stranger could file them. Start
with an image on day one (video versions come once the assistant has set up `ffmpeg`), and
give it three to five past captions you were happy with as the voice reference before it
writes any.

**The trap.** Nothing posts by itself, ever. Every publish, reply and scheduled post is
drafted by the system and sent by a human — per item, no standing permission. And any claim
or statistic in a caption keeps its source, because a wrong number in public is a crisis, not
a typo.

---

## Any other role

Go back to the method at the top. Four questions, then write `Reference/MY_PACK.md` in the
same shape. A photographer's answers produce a different pack from an analyst's, and both are
more useful than being handed the closest-looking example.

If several people in the same discipline set this up, their packs will converge — at that
point promote the common version into this file as a new worked example, so the next person
starts further along.

---

## What every discipline gets, whatever their job

- **It remembers.** Preferences, decisions, corrections — written down and read back next time.
- **Nothing is "done" without proof.** The file exists, the check ran, the numbers add up.
- **Approved work is frozen.** Once a human signs something off, the system does not touch it.
- **Nothing is sent, posted or shared without a yes** — per action, not per session.
- **Progress is measured**, so in three months there is a number, not a feeling.
