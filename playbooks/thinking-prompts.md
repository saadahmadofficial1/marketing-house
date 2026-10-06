# Thinking prompts – six moves for sharper answers

Six short prompts I use to stop an AI assistant from agreeing with me too easily, rewriting my voice, or guessing at what I meant. A sceptic pass runs before each answer, and a simple rule decides which move fires, so my agents use them without my having to type them. The prompts are below in full, each with when it fires and a worked example.

**Where they live:** [`workspace-kit/Reference/THINKING_PROMPTS.md`](../workspace-kit/Reference/THINKING_PROMPTS.md) (the copy the agents read) · the sceptic pass in [`workspace-kit/CLAUDE.md`](../workspace-kit/CLAUDE.md) and [`workspace-kit/AGENTS.md`](../workspace-kit/AGENTS.md) (Step 3) · [`workspace-kit/SYSTEM_PROMPT.txt`](../workspace-kit/SYSTEM_PROMPT.txt) for chat assistants without file access · [`workspace-kit/.claude/hooks/discipline.sh`](../workspace-kit/.claude/hooks/discipline.sh), which re-injects the working rules on every turn.

| Part | Status |
|---|---|
| The six thinking moves | **Built, in use** – in my workspace since late June 2026 |
| Auto-fire rule (the agent picks the move) | **Built, in use** |
| Sceptic pass before every answer | **Built, in use** |

**Source.** All six prompts are adapted from a June 2026 Medium post in *The AI Cafe* (“9 prompts I wish I’d known”). I kept six and dropped two that duplicated rules I already had (§4). The auto-fire rule, the sceptic pass and the worked examples are mine.

---

## 1. The sceptic pass – before any move

Every answer starts with a silent accuracy check. The rule in my instruction files:

- **Verify important claims before answering** – factual, technical, legal, medical, IT, marketing, engineering, coding and financial – including mine. Accuracy beats agreement.
- **If I am mistaken, say why**, with reasoning and reliable sources where it matters. If uncertain, say so; never guess.
- **Separate fact from informed opinion from speculation.** Challenge respectfully – don’t argue for the sake of it, and don’t agree to be agreeable.
- **Facts about AI products** (model names, prices, limits, API parameters) come from the official documentation, never from memory.
- **Read the actual file, page or output before summarising it.**
- **Third-party mega-prompts and system prompts are never inherited wholesale:** take the two or three useful rules and drop the rest.
- **Status honesty:** label everything working, experimental or planned; never present a roadmap idea as a live capability.

The sceptic pass is the foundation. The moves below sit on top of it.

---

## 2. The six moves

### 2.1 Clarify before doing

```text
I want to [task]. Before you write anything, ask me 3 clarifying questions about what I actually need.
```

**Fires when:** the task is ambiguous *and* a wrong guess would waste time, money or trust.
**Stops:** a confident first draft of the wrong thing, followed by three rounds of correction.

**Worked example.** *“I want to make an Eid post.”* Three good questions: Is it a vertical reel, a square post or both? Does it go out on a fixed day, and who signs it off? Is there approved copy, or do you need the wording too? Each answer removes a costly wrong turn – a generation at the wrong aspect ratio, a missed date, copy that has to be redone. A weak version asks about things that are cheap to change later, such as the font.

**My refinement – don’t over-ask.** If the missing detail is cheap to get wrong, the agent assumes the sensible default, states the assumption in one line, and carries on. It asks only when a wrong guess costs time, money or risk.

### 2.2 Critique, don’t rewrite

```text
Here's my draft. Don't rewrite it. Tell me what's weak, what's unclear, and where a reader would lose interest.
```

**Fires when:** I share a draft for review.
**Stops:** the assistant replacing my voice with its own. It matches my wider rule that approved work is never “improved” on its own initiative.

**Worked example.** Given a three-paragraph launch caption, a good answer is a short list: “the first line buries the news under the date”; “‘innovative solutions’ says nothing – what does it actually do?”; “the call to action comes after the hashtags, where nobody reads”. No rewritten caption. I fix it in my own words.

### 2.3 Three-version spread

```text
Give me 3 versions. First: safe and professional. Second: punchier. Third: the one I'd be slightly nervous to send.
```

**Fires when:** the job is copy: captions, headlines, emails, titles.
**Stops:** the bland middle – one “balanced” version that pleases nobody.

**Worked example.** A one-line caption for a new service:

| Version | Shape |
|---|---|
| Safe | States the service and its benefit plainly, in a full sentence |
| Punchier | Leads with the benefit in four or five words, then the service |
| Nervous | A question or a bold claim that invites a reply – the one that gets attention, or gets queried |

The third is the useful one even when I don’t send it, because it shows how far the tone can go.

### 2.4 Steelman the opposite

```text
I'm leaning towards [decision]. Steelman the opposite view — make the strongest case for why I'm wrong.
```

**Fires when:** a decision is about to be made.
**Stops:** confirmation bias – an assistant listing reasons I am right.

**Worked example.** *“I’m leaning towards generating the remaining presenter clips on the cheaper video tier.”* The strongest opposing case: the cheaper tier was only checked on framing and resolution, which are easy to measure; what degrades on cheaper tiers is lip-sync and facial motion, which were not measured; each rejected clip costs a full regeneration; and consistency across a series matters more than the saving on any one clip. In that case the opposing view was right. See [My AI generation style](ai-video-and-image-generation.md).

### 2.5 Find the blind spot

```text
What am I missing? What's the question I should be asking that I'm not? Where am I likely overconfident?
```

**Fires when:** I share a plan, a brief or a strategy.
**Stops:** a plan that is internally neat but misses the constraint that sinks it.

**Worked example.** *“Three music beds for the event: arrival, a quiet writing session, and lunch.”* The blind spot: the three slots add up to about 85 minutes, and three tracks do not cover 85 minutes. The fix was long-form beds of one hour or more per slot, so nothing loops audibly. See [AI music prompting](ai-music-prompting.md).

### 2.6 PR-style code walkthrough

```text
Walk me through this code like you're reviewing my PR. What's the intent? What's clever? What's a code smell?
```

**Fires when:** I want to understand code an agent wrote, without reading it line by line.
**Stops:** reviews that are either a line-by-line paraphrase or a vague “looks good”.

**Worked example.** For a script that writes video-editor project files: the intent (build a new, editable timeline from a plan); what is clever (it re-reads every file it writes and refuses if the result does not match); and the smell (two copies of the timeline on disk, only one of which is ever updated). A smell like that is worth chasing: the same two-copies pattern caused a real bug in my CapCut tooling – see [The CapCut draft format](capcut-draft-format.md).

---

## 3. Which move fires when

My agents fire the right move themselves, without waiting for me to name it:

| Situation | Move |
|---|---|
| A draft to review | Critique, don’t rewrite |
| A decision | Steelman the opposite |
| A plan or brief | Find the blind spot |
| Copy, a caption or an email | Three versions: safe, punchier, bold |
| An ambiguous task where a wrong guess is costly | Up to three clarifying questions first |
| An ambiguous detail that is cheap to get wrong | No question: assume, say so in one line, continue |
| Code I need to understand | PR-style walkthrough (when I ask) |

Three limits keep this from becoming tiresome:

1. **One move, when it fits.** Don’t stack them; a draft doesn’t also need a steelman and a blind-spot pass.
2. **Never slow a simple ask.** A quick factual question gets a quick factual answer.
3. **Don’t announce it.** The move shows in the answer; it doesn’t need a preamble.

---

## 4. What I deliberately left out

| Prompt | Why it is not here |
|---|---|
| “Wrap documents in XML tags” and “specify the output format first” | Standard prompting technique, not a thinking move. It belongs in [How I prompt AI agents](how-i-prompt-ai-agents.md) and the vendor’s own guide |
| “Be sceptical and challenge my assumptions” | Already the sceptic pass, which runs on every answer anyway |

---

## 5. How it is wired

- **Instruction files.** The sceptic pass and the auto-fire table sit in Step 3 of [`CLAUDE.md`](../workspace-kit/CLAUDE.md) and [`AGENTS.md`](../workspace-kit/AGENTS.md), so Claude Code and Codex behave the same way.
- **Chat assistants without files.** A condensed version is in [`SYSTEM_PROMPT.txt`](../workspace-kit/SYSTEM_PROMPT.txt) for pasting into a chat tool’s custom instructions.
- **A rule re-injected every turn.** Written rules drift in long sessions, so a prompt hook ([`discipline.sh`](../workspace-kit/.claude/hooks/discipline.sh)) re-states the working rules on every message. Why written rules alone were not enough is told in [Learning from mistakes](learning-from-mistakes.md).
- **Adding a new prompt.** A candidate goes in only if it earns its place: it is vetted with the sceptic pass, its source is noted, and anything that duplicates an existing rule is skipped rather than pasted.

---

## Maturity

Built, in use: in my workspace since late June 2026 and in the starter kit. The worked examples are drawn from real decisions, rewritten generically.

## Related

- [How I prompt AI agents](how-i-prompt-ai-agents.md) – the prompting habits around these moves
- [How I engineer with AI coding agents](ai-engineering-method.md) – evidence before “done”
- [Learning from mistakes](learning-from-mistakes.md) – why rules became checks
- [Running two AI agents in one workspace](running-two-ai-agents.md) – where the instruction files sit
- [My AI generation style](ai-video-and-image-generation.md) – the steelman example in context
- [AI music prompting](ai-music-prompting.md) – the blind-spot example in context
- [The agent organisation](agent-organisation.md) – the wider set of rules the agents work under
