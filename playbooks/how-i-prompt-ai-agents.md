# How I prompt AI agents

The habits I use when I direct AI coding agents (Claude Code and Codex) on long, real jobs – learned from running them every day, not taken from a guide. In short: brief the goal and the reason, say what must not be touched, make the agent prove its work, and put every repeated correction into memory rather than into a longer prompt. For the basics of prompting technique I follow Anthropic’s own [prompt engineering guide](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview) and do not restate it here.

**Where this is written down for the agents:** [`workspace-kit/CLAUDE.md`](../workspace-kit/CLAUDE.md) and [`workspace-kit/AGENTS.md`](../workspace-kit/AGENTS.md) (standing instructions) · [`workspace-kit/SYSTEM_PROMPT.txt`](../workspace-kit/SYSTEM_PROMPT.txt) (chat assistants) · [`workspace-kit/.claude/hooks/discipline.sh`](../workspace-kit/.claude/hooks/discipline.sh) (rules re-injected every turn) · [`workspace-kit/memory/MEMORY.md`](../workspace-kit/memory/MEMORY.md) (where corrections go) · [`workspace-kit/Reference/CLAUDE_CODE_OPS.md`](../workspace-kit/Reference/CLAUDE_CODE_OPS.md) (context and session housekeeping).
**Read with:** [Thinking prompts](thinking-prompts.md) for the six moves and the sceptic pass, and [How I engineer with AI coding agents](ai-engineering-method.md) for what counts as evidence.

| Part | Status |
|---|---|
| Briefing habits (goal, reason, boundaries) | **Built, in use** – how I work with both agents every day |
| Evidence-grounded reporting and fresh-context checks | **Built, in use** |
| Corrections into memory and code, not prompts | **Built, in use** |
| Strict-JSON output from models | **Built, in use** – in the tools that call local and hosted models |

The first version of these notes was drafted by the agent itself in July 2026, after a weekend of heavy use of Anthropic’s newest model at the time, and I kept what matched my experience. Most of it transfers to other models; the newest ones simply need less hand-holding.

---

## 1. Brief the goal, not the steps

A frontier agent plans the route itself. A ten-step instruction list makes it worse, not better.

| Weaker | Stronger |
|---|---|
| “Open the project. Find the caption track. Change line 4. Re-export. Check the length.” | “The reviewer wants this video revised – here is her email. Keep my edits; change only what she asks.” |

The pattern I use when the reason is not obvious:

```text
I'm working on [larger task] for [who]. They need [what it enables]. With that in mind: [request].
```

Three things follow from that:

- **Give it the hardest problem whole.** Agents now sustain work that would take a person days. Chopping it into small steps undersells them, and testing them only on small tasks tells you little.
- **Don’t over-prescribe.** A short instruction often steers as well as a long list, and exhaustive rule lists written for older models can make the output worse. The same goes for packaged skills: one written step by step for an older model may need loosening.
- **Don’t shout.** “CRITICAL: you MUST…” makes current models over-apply a rule everywhere. Plain wording – “use this when…” – is enough.

### Worked example: a real brief, rewritten generically

> Nine short training videos need presenter intros. Each intro is the presenter on the right, the title on the left, one spoken line. The approved intros are in the reference folder – match them exactly (framing, length, music). The wording for each video is in the script file; check it with me before generating anything, because a lip-synced clip is welded to its words. Don’t touch any timeline I have edited. Report what you checked, frame by frame, before you tell me a clip is done.

It gives the goal, the reference, the order of operations and why, the one boundary that matters, and what proof looks like. It does not tell the agent which tools to run.

---

## 2. Give the reason with the rule

An agent generalises from the *why*. A bare rule gets applied too literally, or too narrowly.

| Rule alone | Rule with its reason |
|---|---|
| “Keep the presenter on the right.” | “Keep the presenter on the right – the left third is where the title goes.” |
| “No hands in generated images.” | “No hands in generated images – reviewers reject them on sight, so they cost a regeneration.” |
| “Captions go in last.” | “Captions go in last – any change to the cut after that moves every caption.” |

With the reason attached, the agent also handles cases the rule never mentioned: a centred product shot that would cover the title, say, or a late trim to the opening.

---

## 3. Say what not to touch

Agents respect explicit boundaries well, and one sentence prevents most scope creep: “Don’t restyle the whole dashboard; only add the brief section.” My standing boundaries, written into the instruction files so I don’t have to repeat them:

- **Approved work is frozen.** Never re-grade, re-enhance or “improve” a file I have approved. My edit is the reference.
- **My timelines are my workspace.** Build a new project every time; never overwrite one I have edited. Read the current state before writing anything near it.
- **Outward actions need my explicit yes:** sending, posting, sharing, deleting, paying.
- **Standing configuration needs my explicit yes:** hooks, schedules, settings.

---

## 4. Make it prove its work

“Done” means nothing without evidence that matches the claim.

- **Ask for a self-check with every build:** “prove it works before you tell me.” Agents write assert-based checks naturally – hold them to it.
- **Ask for grounded progress reports on long runs:** “only report what you can point to evidence for.” That nearly eliminates invented status.
- **Check with fresh eyes at intervals,** not with one big review at the end. A sub-agent that starts with a clean context and compares the work with the spec catches what the author has stopped seeing.
- **Re-read the output the way its user will.** A tool that prints “written” has proved that a file exists, not that it is right. A web page is checked in a real browser; a video at its true display size; a project by opening it.
- **Unknown is not a pass.** A check that could not run, or could not see, reports *unknown* – never *ok*.

The full rules, and the incidents behind them, are in [How I engineer with AI coding agents](ai-engineering-method.md).

---

## 5. Approve at real decision points only

Stopping an agent for approval at every step slows it down and teaches me nothing. I approve where something is spent, sent or destroyed:

| Approve | Don’t make me approve |
|---|---|
| Spending money or paid credits | Reading, searching, analysing |
| Sending, posting, sharing | Drafting, building locally, testing |
| Deleting or overwriting | Writing to a new file or a scratch folder |
| Standing configuration | Using a skill that fits the task |

Two refinements that came from mistakes. **An approving-sounding remark is not a go-ahead for spending** – a positive comment about a take is not permission for another paid generation. And **a repeated request is often me checking**, not asking again: look at what is already running before starting it a second time.

---

## 6. A correction given twice belongs in memory, not a better prompt

The agents read their instruction files and memory index at the start of every session. So:

1. **The first time** I correct something, the agent logs it to memory **in the same turn**, with the reason – not at the end of the session, which may never come.
2. **The second time** the same correction is needed, the problem is the memory, not the prompt: the entry is missing, buried or too vague.
3. **The third time**, a written rule has failed, and it becomes a check in code that refuses. In my record, no written rule ever stopped a repeat; only code did. See [Learning from mistakes](learning-from-mistakes.md).

---

## 7. Think first, then act

- **Think the whole set through before executing.** When feedback arrives about two items, work out what it means for the whole set before touching a tool. A note about two cards is usually a note about the system they sit in.
- **Briefing is not a go.** When I am feeding a brief slot by slot, the agent records each item, acknowledges it in a line, and stays quiet. It holds its concerns and raises them once, when the brief is complete.
- **Check before building something new.** Search memory and the existing tools first. If something is already solved, say so and reuse it.

---

## 8. Output craft

- **Structured output: strict JSON only** – no Markdown fences, no preamble – and **parse defensively** anyway: strip any fences, take the outermost object, validate the required keys, and treat a parse failure as *unknown*, never as a pass. Two failures taught me this. A local vision model, asked to describe a text-heavy screenshot, tried to transcribe every word on the screen and the JSON was cut off mid-string. The same model returned *nothing* when its output-length cap was set too low. Ask for a bounded field, and give it room to finish.
- **Web facts carry a source link and a date** whenever they matter. Facts about AI products (model names, prices, limits) come from the official documentation, never from memory.
- **Hero visuals get a bake-off:** the same prompt on two models, judged against written criteria, rather than marrying the first output. See [My AI generation style](ai-video-and-image-generation.md).

---

## 9. How I want answers back

I am not a programmer, and the agents are set up for that:

- **Result first, in plain language** (British English). Not the steps they took.
- **Pick the best option and go.** No A/B/C menus unless I ask to choose.
- **Multi-step work is numbered,** with the state restated (“step 3 of 5 done; next…”) and **one concrete next action** at the end.
- **Always open the result.** An agent builds things on disk; a non-technical user sees nothing until it is opened in front of them.
- **Say it once.** If something doesn’t match, check it once, say so in a line, and hand over the work – don’t relitigate.

---

## 10. What to watch

| Behaviour | What I do about it |
|---|---|
| Once authorised, an agent does a lot unprompted | Great for “do what’s best”. Keep outward actions behind explicit confirmation in the instruction files |
| Long sessions fill the context | A fresh chat per task, with the session folder carrying state, beats compacting a long chat. See [Running two AI agents](running-two-ai-agents.md) |
| Conservative refusals in dual-use areas (security, for example) | Not a bug. State plainly what the work is for and whose system it is |
| Plausible-looking tool output | The sceptic pass applies to tools too: a green number on the wrong dimension is still the wrong answer |
| Third-party mega-prompts and trending tools | Take the two or three useful rules and drop the rest. Never install unread code next to work files; inspect it first, and install only after my approval |

---

## The one-line version

Write rules once, give goals rather than recipes, make the agent prove its work, keep memory current – then get out of its way.

---

## Maturity

Built, in use: these habits run my daily work with both agents. They are personal practice, not a delivered product; model behaviour will keep shifting, and the notes are revised when it does.

## Related

- [Thinking prompts](thinking-prompts.md) – the six moves and the sceptic pass
- [How I engineer with AI coding agents](ai-engineering-method.md) – routing by risk and evidence before “done”
- [Running two AI agents in one workspace](running-two-ai-agents.md) – session files, memory and hand-off
- [Learning from mistakes](learning-from-mistakes.md) – why repeated corrections became code
- [My AI generation style](ai-video-and-image-generation.md) – prompting image and video models
- [Security and data policy](security-and-data-policy.md) – vetting third-party tools
- [Why AI agents forget](why-ai-agents-forget.md) – when “put it in memory” is not enough
- [Orchestrating agent fleets](orchestrating-agent-fleets.md) – fresh-context checkers at scale
- [My creative bar](my-creative-bar.md) – how to brief me and report back
