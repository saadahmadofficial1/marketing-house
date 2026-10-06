# Repository due diligence, 2026

Read-only due-diligence notes on 47 public GitHub repositories – agent memory, MCP servers, orchestration frameworks, marketing-skill collections, text-to-speech, lip-sync, OCR – each judged for one question: would it help a non-technical media team on a Mac that holds confidential work, without new risk? The ten patterns distilled from all of this are in [security and data policy, section 5](security-and-data-policy.md#5-how-third-party-ai-tools-are-vetted); what I took from outside ideas, and what I declined, is in the “Outside ideas” section of [how I engineer with AI coding agents](ai-engineering-method.md). The second batch was produced with [`frameworks-intel.js`](../workflows/frameworks-intel.js).

**As of August 2026.** Every figure, status and complaint below is as read in August 2026; projects move fast, so check the current state before relying on any of it. **Status: Research – nothing was installed or run.**

> These are one reader’s notes from public pages and issue trackers, written to decide what to install on one machine. They are not endorsements, and they are not accusations: where a note records a problem, it cites the issue, pull request or advisory it came from, and several of the projects had responded or fixed things since.

---

## Method

For each repository the agents read the README, the most-discussed **open** issues and the most-discussed **closed** issues – the closed ones show what actually broke and how it was fixed – plus the commit and release history. Desk research only: nothing was cloned, installed or run. Each entry records maintenance signals, what users complain about (by issue number), traps for anyone adopting it, what is worth taking without installing anything, and a verdict for this set-up.

## The short version

| Verdict | Examples |
|---|---|
| Adopt, selectively | only one: the official document skills from Anthropic’s skills repository |
| Safe to read, nothing to install | curated lists, a one-file diagram skill, a research archive |
| Do not adopt – but take an idea | most of them: memory systems, agent frameworks, marketing-skill collections |
| Do not adopt – a risk to the machine | tools that want live session cookies, run unsandboxed on the host, or uploaded whole repositories |

The thread through all of them: the failures are rarely in the clever part. They are in installation, health checks, permission boundaries, honest measurement, and what happens when the maintainer stops caring – and popularity signals none of those.

---

## Part 1 – tools, MCP servers, memory and media models

### [chopratejas/headroom](https://github.com/chopratejas/headroom)
A local proxy that compresses text (tool output, logs, files, history) before it is sent to the model, to cut token cost. Since moved to a company organisation with a paid team tier.
- **Maintenance:** very active; about 65,800 stars; the author answers issues personally, often the same day. Release packaging has failed several times (#355, #2361, #1583).
- **Complaints:** real-world savings well below the headline – #1843 measured 7–19% compression on real work, and the maintainer replied that 15–20% is realistic in coding agents and updated the README; #327 “Big drop in cache hitrate ?”; #1237 “Is file read compression really worth?”; the proxy breaks some logins and integrations (#962, 102 comments; #71).
- **Traps:** it sits in the path of every prompt, so it reads everything the agent sends; first run downloads a model and a runtime; setup means proxy and certificate changes on the work machine.
- **Worth taking:** label synthetic benchmarks as synthetic; measure the whole loop, not one step – a saving that breaks the prompt cache or forces a re-fetch is not a saving; a dashboard that counts only wins will flatter itself.
- **Verdict:** no – roughly 15–26% real saving, sometimes negative once the cache breaks, and nothing for video or images.

### [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
A curated, bot-regenerated index of Claude Code skills, hooks, commands and plugins. A link list, not software.
- **Maintenance:** about 52,000 stars; commits are almost entirely automation; human review is “best-effort”.
- **Complaints:** submission backlog of months (#169, #391); the validating bot checks form, not quality; #387 “Handle unmaintained projects” – the badge shows repository age, not last commit, so abandoned entries look alive; no releases to pin (#1139).
- **Traps:** listing is not endorsement, and every listed item runs with the agent’s shell and file access once installed; the page changes several times a day.
- **Worth taking:** the pipeline – structured intake form → schema validation → one CSV as the source of truth → every rendered page generated, never hand-edited; any index of external links needs an automatic decay rule.
- **Verdict:** safe to browse as a catalogue; treat nothing on it as vetted.

### [browser-use/video-use](https://github.com/browser-use/video-use)
A skill that edits video by conversation: transcribe with word timestamps, build an edit decision list, cut and render with FFmpeg.
- **Maintenance:** about 20,500 stars; weak – about six weeks without commits at the time, 52 open pull requests against 27 ever closed; three real bugs unanswered (#118, #121, #125); a direct question about what gets uploaded (#18) closed without an answer.
- **Complaints:** subtitle burn-in crashes on the documented macOS install because the default FFmpeg build lacks libass (#118, fix PR #120 unmerged); a hard-coded font turns non-Latin subtitles into empty boxes (#118); no dependency pre-flight (#121); shipped with no licence until three issues asked for one (#19, #20, #25).
- **Traps:** every source clip’s audio goes to a cloud transcription service; the model reads the transcript, not the picture, so it is blind to visual faults; output is a rendered file, not an editable project.
- **Worth taking:** the core idea – feed the model a word-timed transcript, not frames, and have it emit an edit decision list; bounded self-review capped at three re-renders; font choice as data, never code, for anything that will carry Arabic.
- **Verdict:** don’t adopt; rebuild the transcript-to-edit-list idea locally instead.

### [obsidianmd/obsidian-releases](https://github.com/obsidianmd/obsidian-releases)
The public catalogue behind Obsidian’s community plugins and themes – JSON lists and release manifests. Not software.
- **Maintenance:** bot-updated several times a day; issues are disabled, so complaints live on the forum.
- **Complaints (forum):** review queues of weeks to months; a review bot that did not re-scan after fixes.
- **Traps:** the README described a submission flow that a new directory replaced in May 2026; plugins are fetched from each author’s own releases, so the catalogue vouches for the listing, not every future update.
- **Worth taking:** keep a machine-written catalogue separate from the human conversation; automated first-pass review with a human second pass; per-plugin transparency notes (network, clipboard, file access).
- **Verdict:** nothing to adopt; treat any Obsidian plugin as third-party code.

### [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
A design-reference skill: UI styles, palettes, font pairings and UX rules as local CSV and Markdown tables with a small search script.
- **Maintenance:** about 115,000 stars in eight months; active releases; issue handling largely automated, with several substantive reports closed “not planned”.
- **Complaints:** install breakage across environments (#215, #172, #109, #318); the bundle can exceed the skill host’s file limit or contain a symlink (#334, #235); #333 reported the installer writing allowed commands into the agent’s local settings file, closed “not planned”; #335 a prompt-injection flag, also closed; #353 version drift between repository and package; #161 a buyer’s report that a paid subscription vanished and refunds went unanswered – the premium tier was later paused with pro-rata refunds.
- **Traps:** check what the installer writes into your agent’s permission file before anything else; the free half runs locally, the premium half was a hosted API.
- **Worth taking:** “data as skill” – knowledge in searchable rows plus a tiny search script, so the agent pulls only matching rows; ship configuration as a separate file a person copies in deliberately.
- **Verdict at the time:** no. Later I allowed its free, data-only skill files in a starter kit for design roles, after checking what they contain – the installer’s settings writes remain the thing to inspect.

### [anthropics/skills](https://github.com/anthropics/skills)
Anthropic’s public collection of Agent Skills, including the document skills (Word, PDF, PowerPoint, Excel) and the skill specification.
- **Maintenance:** about 167,700 stars; curated rather than collaborative – few commits on main, many open pull requests and issues without replies.
- **Complaints:** skills that never trigger – #556 reported a 0% trigger rate in the repository’s own evaluation script, #1169 similar; one skill injecting about 156,000 tokens in a call (#1487); community skills placed under an official-looking namespace (#492); duplicate installs (#189, #206).
- **Traps:** a skill is code, not just a prompt; the four document skills are source-available, not open source; the repository says its skills are for demonstration and education.
- **Worth taking:** the description line is the whole retrieval system – write triggers in the user’s own words; progressive disclosure, with a tiny always-loaded part and detail read on demand; ship an evaluation with the claim; keep “ours” and “someone else’s” visibly separate.
- **Verdict:** **yes, selectively** – the official document skills run locally; never install community skills without reading their scripts.

### [ruvnet/ruflo](https://github.com/ruvnet/ruflo)
A large orchestration add-on for coding agents (formerly claude-flow) promising agent swarms, shared memory and federation across machines.
- **Maintenance:** about 67,600 stars; extremely active, mostly one maintainer plus bots; plain user questions unanswered (#958, #1196).
- **Complaints:** #958 “Still can’t figure out how to get v3 to actually perform work”; an independent audit in Discussion #1513 reported that only about 10 of roughly 300 tools executed; Discussion #1666 summarised agents self-reporting success on failed work; token overhead from repeated memory injection; macOS and install failures (#62, #2286, #564, #662); no uninstall for months (#670).
- **Traps:** self-published benchmark figures; an invasive install that rewrites agent configuration; federation can move prompts and memory off the machine.
- **Worth taking:** tool count is a vanity metric; never let a worker mark its own homework; measure overhead against a real baseline.
- **Verdict:** no.

### [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp)
Microsoft’s MCP server for driving a real browser through the page’s accessibility tree.
- **Maintenance:** about 36,000 stars; active, monthly releases; bugs are filed in the main Playwright repository, so this tracker looks empty.
- **Complaints:** heavy context use – independent write-ups measured about 114,000 tokens for a seven-step task against about 27,000 with the CLI, and the README now recommends the CLI for coding agents (#889); the shared-profile lock (#769, #942, #891); snapshot gaps on some pages (#535, #447); a corrupted screenshot that broke every later call (#1211).
- **Traps:** #1479 documents prompt injection through a page’s accessibility tree, and the README states it is not a security boundary; the persistent profile keeps every login on disk unless `--isolated` is used; #1637 warns that an unscoped look-alike package is not Microsoft’s.
- **Worth taking:** text beats pixels for machine control; cap what a tool returns; make isolation the default; tell users when your tool is the wrong one.
- **Verdict:** only with guard rails (the official scoped package, `--isolated`, never on logged-in work systems) – and it does nothing for video.

### [glifxyz/glif-mcp-server](https://github.com/glifxyz/glif-mcp-server)
A connector for running hosted generative workflows from an agent. In July 2026 the local server was deprecated in favour of a hosted, closed-source one.
- **Maintenance:** small (about 200 stars); recent commits are housekeeping.
- **Complaints:** very few issues filed; #32 a broken token link, closed “not planned” during the retirement; #29 a dependency scan reporting 16 vulnerabilities.
- **Traps:** every prompt and reference image goes to the vendor’s servers; generation is credit-metered; it is generative end to end.
- **Worth taking:** the asynchronous job pattern (start returns a job id, poll for the result); a small, well-named tool surface; deprecation done well – package marked deprecated, old code kept on a named branch, README pointing at the successor.
- **Verdict:** no for this set-up.

### [hangwin/mcp-chrome](https://github.com/hangwin/mcp-chrome)
A Chrome extension plus local helper that hands the user’s everyday, logged-in browser to an AI assistant.
- **Maintenance:** about 12,300 stars; no commits for about seven months at the time; two pull requests ever merged, 26 open – including community fixes for the top bug; #361 “this project is dead”.
- **Complaints:** “Connected, service not started” recurring since mid-2025 (#29 and many duplicates); connects once and then fails until restarted (#306; fixes in #346 and #354 unmerged); client connection problems (#199, #182); features broken in places (#53, #275, #289).
- **Traps:** #316 sets out the injection risk to a logged-in browser; the local endpoint has no authentication (#363); a developer-mode install.
- **Worth taking:** stars measure interest, merged pull requests measure health; never share one server object across connections; a status light must reflect reality; ship the safety rails – allow-lists, per-tool switches, confirmations – in version one.
- **Verdict:** no; official browser-control alternatives exist.

### [Cocoon-AI/architecture-diagram-generator](https://github.com/Cocoon-AI/architecture-diagram-generator)
A Claude skill – one instruction file – that turns a described system into a self-contained HTML/SVG architecture diagram.
- **Maintenance:** about 6,900 stars from one newsletter mention; ten commits; one issue ever.
- **Complaints:** none filed; the author documents the known failure modes inside the skill (overlapping boxes, legend collisions).
- **Traps:** no layout engine – the model places coordinates; the export buttons load scripts from a public CDN; dark theme only.
- **Worth taking:** a product can be one well-written instruction file; turn every past bug into an explicit numeric rule inside the instructions.
- **Verdict:** near-zero risk and off-target – useful only for a system diagram in a deck.

### [TencentCloud/TencentDB-Agent-Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory)
A memory system for coding agents that distils conversations into chat memory, skills, a wiki and a code graph.
- **Maintenance:** about 19,500 stars; very active, with a sponsored student programme driving much of the contributor traffic; several genuine reports unanswered at the time.
- **Complaints:** three architectures in four months; a Docker build failing on a clean clone (#765); #62 reported one user’s recall returning another user’s data; #158 injection detection missing from a built release; #120 measured prompt-cache hit rates falling after install; #73 benchmark scores not reproduced; settings in the schema never read (#163).
- **Traps:** local storage, but conversations go to an LLM endpoint for extraction by default; Node 22 and Docker required.
- **Worth taking:** the distillation ladder – raw log → facts → context blocks → stable profile; a third memory state between “global rule” and “discard” – a rule tagged with the situation it applies in (#48 shows a one-off preference promoted to a permanent rule).
- **Verdict:** no – the local memory already covers the need.

### [google-research/timesfm](https://github.com/google-research/timesfm)
A pretrained time-series forecasting model. Numbers in, forecast out – nothing to do with media.
- **Maintenance:** about 27,300 stars; code moving, community queue less so; the README says it is not an officially supported product.
- **Complaints:** install conflicts on the old stack (#1, open since 2024); a GPU-only dependency that breaks CPU installs (#443, fix in #453); fine-tuning documentation (#242).
- **Worth taking:** pretrain once, serve many; distribution beats packaging; choose the boring, mainstream runtime.
- **Verdict:** not relevant here.

### [supertone-inc/supertonic](https://github.com/supertone-inc/supertonic)
A small (99M-parameter) on-device text-to-speech model in 31 languages, with many language bindings.
- **Maintenance:** the README announced archiving and the end of official support; the hosted voice builder and API were scheduled to close on 31 August 2026.
- **Complaints:** words dropped from the output (#83, #187, #48); custom voices only through the closed paid builder (#44); uneven quality by language (#124, #75); a purchased voice that stopped working after an upgrade (#97).
- **Traps:** weights carry a use-restricted licence; first run downloads them; output cannot be trusted unheard.
- **Worth taking:** right-size the model; one core file with thin bindings; a model that fails silently is worse than one that fails loudly.
- **Verdict:** marginal – on-device privacy is genuinely good, but it is ending; a scratch toy at most.

### [xai-org/grok-build](https://github.com/xai-org/grok-build)
A terminal coding agent whose client source was published in July 2026; the model runs on the vendor’s servers.
- **Maintenance:** daily bot syncs from an internal repository; issues, discussions and outside pull requests are disabled.
- **Reported (July 2026):** a published wire-level analysis of an earlier version reported whole repositories being uploaded to vendor storage while the conversation needed a tiny fraction of that – including a canary file the agent was told never to open – and that the privacy toggle governed training use rather than transmission. The behaviour was switched off server-side.
- **Traps:** no bug tracker; a pipe-to-shell installer; builds not reproducible from the published source.
- **Worth taking:** the audit method – plant a canary, tell the agent never to open it, capture the traffic, and compare bytes sent with bytes needed; label a privacy control by what it actually stops.
- **Verdict:** no – and it does nothing for video.

### [bytedance/LatentSync](https://github.com/bytedance/LatentSync)
A lip-sync model that repaints the mouth of a talking-head video to match new audio.
- **Maintenance:** about 6,000 stars; no code pushed for over a year at the time; recent requests for newer GPUs unanswered.
- **Complaints:** teeth and mouth distortion (#268, #356); a visible mask edge (#297); quality falling on clips past about 30 seconds (#151); memory blow-ups (#50, #45); duration drift (#64, #169).
- **Traps:** NVIDIA-only, no Mac path – so footage would go to rented cloud GPUs; 18 GB of VRAM for the current version; strict input limits.
- **Worth taking:** publish the failure envelope, not just the showreel; keep the previous version installable before switching.
- **Verdict:** no – and putting new words in a real person’s mouth is a consent question before it is a technical one.

### [baidu/Unlimited-OCR](https://github.com/baidu/Unlimited-OCR)
A 3-billion-parameter document OCR model that reads whole documents into Markdown.
- **Maintenance:** about 23,400 stars; recent commits are README edits; substantive issues unanswered at the time (#27, #18, #48, #55, #66).
- **Complaints:** invents plausible text on poor scans (community comparisons ranked it last on faithfulness); repetition loops on some pages (#55); a custom install stack (#27); no Mac support (#48, #18); scores not reproduced (#66).
- **Worth taking:** judge a tool by its failure mode, not its headline score; a guard tuned to one size fails silently at others.
- **Verdict:** no; better-ranked OCR options existed in the same comparison.

### [garrytan/gbrain](https://github.com/garrytan/gbrain)
A self-hosted memory system: Markdown notes and chat history indexed in Postgres with vector, keyword and graph search, served over MCP.
- **Maintenance:** about 28,200 stars; very active; issue creation restricted to maintainers.
- **Complaints:** frequent breaking changes; a crash on macOS (#223) and hangs (#1269); edits failing silently without a flag (#1434), dropped links (#1413), skipped pages without a reason (#3984); a scope leak through a shared cache (#2200); keyword search inert for CJK text (#3986).
- **Traps:** embeddings and synthesis call cloud APIs by default; the embedded database tops out around 50,000 pages.
- **Worth taking:** **Markdown as the source of truth, the database as a rebuildable index** – you can diff what your agent learned overnight; hybrid retrieval, verified per language.
- **Verdict:** not yet – the idea is the valuable part, and it matches how my own memory already works.

### [openclaw/openclaw](https://github.com/openclaw/openclaw)
A personal assistant you run locally that connects a model to your files, shell and messaging apps.
- **Maintenance:** about 386,000 stars; extremely active, a release roughly every 18 hours; triage largely automated.
- **Complaints:** messages silently lost (#116277, then #121058; #44925); provider changes breaking it (#57523, #32828); UI regressions after updates (#4855, #52823, #45471); a gateway memory leak labelled P0 (#91588); open security tickets (#11829, #25592).
- **Traps:** tools run on the host unsandboxed by default (per the README); the README warns that inbound messages are untrusted input; a long list of published security advisories with named CVEs, since fixed in later versions; a pipe-to-shell installer.
- **Worth taking:** draw the trust boundary per tool and action, not per process; fail loudly with a receipt; add integrations one at a time; separate fast and stable release tracks from day one.
- **Verdict:** no for a machine holding confidential work.

### [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
A self-hosted agent that keeps memory between sessions and writes its own reusable skills.
- **Maintenance:** about 228,600 stars but under 900 watchers; code active; a very large backlog (about 20,000 open pull requests).
- **Complaints:** provider logins breaking (#15080, #6475, #26847); crashes on unexpected model output (#11179, #7237, #69078); desktop app freezes (#63047) and Full Disk Access revoked on every update (#52010); #4379 measured about 73% of each call as fixed overhead.
- **Traps:** an outside audit filed as #7826 (open at the time) describes permissive defaults – host shell, no read deny-list; CVE-2026-9366 (prompt injection; the CVE record states no fixed version and no vendor response at the time); CVE-2026-53870 (world-readable databases); self-written skills persist as an injection vector.
- **Worth taking:** **#344, the most useful issue in the whole batch** – machine-readable hand-over receipts (id, path, checksum, *which checks did not pass*) and stuck detection with an explicit pass/fail judge per agent; #11692 – stamp outputs with the template version that produced them; self-improvement only works where success is measurable.
- **Verdict:** no as software; the ideas in #344 went on my build list.

### [PrimeIntellect-ai/experiments-autonomous-speedrunning](https://github.com/PrimeIntellect-ai/experiments-autonomous-speedrunning)
A data archive from a two-week experiment in which two coding agents tuned a small training run on their own.
- **Maintenance:** published once; no issues filed; no licence file.
- **What the authors themselves report:** one agent idled for long stretches waiting for a human; the other looped on one parameter; neither pruned what was not helping; the result came from sweeping known methods, not new ideas.
- **Worth taking:** publish the failures with the win; long-running agents need a watchdog for idling and a limit for loops – instructions alone fix neither.
- **Verdict:** nothing to install; ten minutes with the write-up is worth it.

### [harnessclaw/harnessclaw](https://github.com/harnessclaw/harnessclaw)
An Electron desktop shell for running agents and installing skills from a marketplace, with a separate Go backend.
- **Maintenance:** about 300 stars; quiet for five to six weeks at the time; most issues filed by the maintainers themselves; #121 “Are you using Harnessclaw?” had no replies.
- **Complaints:** onboarding settings not taking effect (#53, #74, #73); a hard-coded model list (#55); misleading errors (#77, #78).
- **Traps:** version 0.0.x; marketplace skills run third-party code; prompts go to whichever provider is configured.
- **Worth taking:** make every set-up step reversible and visibly effective; never show a feature you haven’t built; a skill marketplace is a supply chain.
- **Verdict:** no – it duplicates what a coding agent already provides.

### [AIwithhassan/harnessclaw-projects](https://github.com/AIwithhassan/harnessclaw-projects)
One person’s two set-up guides for the desktop shell above. No code, no licence.
- **Traps:** one guide recommends switching the agent’s permission mode to “don’t ask” to get past prompts, with no step to switch it back; API keys pasted into local configuration.
- **Worth taking:** the artefact type – a failure → fix log written while setting something up; when configuration lives in two stores, document which one wins.
- **Verdict:** no.

### [Panniantong/Agent-Reach](https://github.com/Panniantong/Agent-Reach)
A command-line tool and agent skill that routes an assistant to read social platforms and sites through third-party scrapers, using the user’s browser session cookies.
- **Maintenance:** about 70,400 stars in under six months; active, effectively one maintainer; no test suite.
- **Complaints:** logins and cookies breaking (#33, #9, #108, #13); #498 an account-suspension warning after two days of use; documentation describing channels and commands that did not exist (#429, #58, #547); a doctor command reporting healthy while routes were dead (#566, #508); credential handling issues since patched (#412, #446).
- **Traps:** live session cookies are bearer credentials; auto-update instructions fetched from a remotely editable file; installs from a moving branch; platform terms of service forbid cookie-based automation.
- **Worth taking:** wrap proven tools rather than reimplement them, with a primary and fallback per source; **a version check is not a health check**; allow-list what is safe to print rather than guessing what is secret; deleting a broken feature beats shipping it broken.
- **Verdict:** no.

---

## Part 2 – 24 agent frameworks and marketing-skill repositories

**Decision memo, in short.** None of the 24 offered a multi-agent capability the set-up did not already have: Claude Code’s own workflow runner already fans out 13–18 agents with structured returns and verification passes. Twenty of the 24 are developer libraries with no interface. The recommendation was **install nothing** and copy two ideas – machine-readable hand-over receipts with checksums, and an explicit pass/fail judge per sub-agent – plus a third: a quality gate for written copy in which whatever wrote the draft may never pass it. Patterns across the field: stars measure 2023, not 2026 (watchers, installs and release dates are the honest signals); “local” usually means remote processing; silent failure is the defining defect; and the installer is the attack surface.

One of the 24, hermes-agent, was also in the first batch and is written up in Part 1, so 23 entries follow here and the page covers 47 distinct repositories.

| Project | Verdict here | The one thing worth taking |
|---|---|---|
| [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | No (see Part 1) | Hand-over receipts and stuck detection (#344) |
| [Agent-Analytics/awesome-multi-agent-orchestrators](https://github.com/Agent-Analytics/awesome-multi-agent-orchestrators) | Ignore | – |
| [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) | Ignore for this work | Read the shared brand-context file before asking the user anything |
| [hyperfx-ai/marketing-skills](https://github.com/hyperfx-ai/marketing-skills) | Ignore | – |
| [cgallic/kai-cmo-harness](https://github.com/cgallic/kai-cmo-harness) | Ignore as an install | The copy quality gate |
| [Anil-matcha/Open-AI-UGC](https://github.com/Anil-matcha/Open-AI-UGC) | Ignore | – |
| [jmedia65/awesome-ai-marketing](https://github.com/jmedia65/awesome-ai-marketing) | Ignore | – |
| [langgenius/dify](https://github.com/langgenius/dify) | Ignore | A canvas that shows a non-technical person what a multi-step job is doing |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | Ignore | On retry, never re-run the steps that send, post, upload or spend |
| [langchain-ai/langchain](https://github.com/langchain-ai/langchain) | Ignore | – |
| [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT) | Ideas only | A visual, re-runnable saved pipeline |
| [ag2ai/ag2](https://github.com/ag2ai/ag2) | Ignore | Budget caps and a kill switch per agent |
| [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT) | Ignore | – |
| [agno-agi/agno](https://github.com/agno-agi/agno) | Ignore | – |
| [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | Ignore | – |
| [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | Ignore – well run, wrong layer | – |
| [run-llama/llama_index](https://github.com/run-llama/llama_index) | Ignore | – |
| [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter) | Ignore | – |
| [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent) | Ignore as an install | Reach a running session from a phone; hard spend caps |
| [e2b-dev/E2B](https://github.com/e2b-dev/E2B) | Ignore | – |
| [infiniflow/ragflow](https://github.com/infiniflow/ragflow) | Ignore as software | Answers that cite the exact page they came from |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | Ignore as software | A periodic memory junk audit (#4573’s categories) |
| [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit) | Ignore | – |
| [2FastLabs/agent-squad](https://github.com/2FastLabs/agent-squad) | Ignore | – |

### [Agent-Analytics/awesome-multi-agent-orchestrators](https://github.com/Agent-Analytics/awesome-multi-agent-orchestrators)
A curated list of about 40 multi-agent orchestrators, run by a company that lists its own product in it.
- **Maintenance:** 69 stars; the visible activity is a bot updating star counts twice a day; no human edit for about two months at the time; outsiders cannot open issues.
- **Traps:** entries carry no dates or “last checked”; no licence file.
- **Verdict:** skim once if curious.

### [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)
Forty-nine plain-text playbooks for B2B software marketing – pricing pages, sign-up flows, cold email, SEO, churn.
- **Maintenance:** about 43,900 stars, 383 watchers; active, essentially one author.
- **Complaints:** plugin installs failing schema validation in April 2026 (#261, #262, #263, #270, fixed); other-agent support pending (#295); spam and blank template submissions in the tracker.
- **Fit:** no captions, screen recordings, call-outs or editing projects; the one “video” skill steers towards video-as-code.
- **Worth taking:** every skill reads a shared brand-context file first and asks only for what is missing.
- **Verdict:** ignore for this work.

### [hyperfx-ai/marketing-skills](https://github.com/hyperfx-ai/marketing-skills)
Twenty-four playbooks that drive a vendor’s paid hosted marketing platform.
- **Maintenance:** 70 stars; no issues ever filed.
- **Traps:** the tools come from the vendor’s service (subscription plus credits) and need OAuth access to ad, email and analytics accounts.
- **Verdict:** ignore – paid-media work this team does not do, and company accounts wired into a third party.

### [cgallic/kai-cmo-harness](https://github.com/cgallic/kai-cmo-harness)
A Claude Code plugin with dozens of marketing commands and skills, built to profile a software product’s codebase and market it.
- **Maintenance:** 40 stars; near-daily commits by one author, who fixed an outside install bug within a day.
- **Complaints:** missing declared dependencies on a clean install (fixed June 2026); a very large install footprint; a licence split that changed in August 2026.
- **Worth taking:** **the quality gate** – a draft is scored against a fixed rubric and a banned-word list, and whatever wrote it may not pass it.
- **Verdict:** ignore as an install.

### [Anil-matcha/Open-AI-UGC](https://github.com/Anil-matcha/Open-AI-UGC)
A self-hosted web app that turns a script and a reference image into a vertical AI advert through one paid API – essentially a resellable SaaS template.
- **Maintenance:** 240 stars; 30 commits; issues closed without visible replies.
- **Complaints:** a report of a token committed in plain text, closed without a visible response; no licence file until July 2026.
- **Traps:** generated people (against a no-people rule for AI video); product footage through a third-party aggregator.
- **Verdict:** ignore.

### [jmedia65/awesome-ai-marketing](https://github.com/jmedia65/awesome-ai-marketing)
A list of about 80 AI marketing tools. Last commit December 2025; 17 pull requests unanswered.
- **Verdict:** ignore – a stale list in the fastest-moving category there is.

### [langgenius/dify](https://github.com/langgenius/dify)
A self-hosted visual builder for chatbots, document search and agent workflows.
- **Maintenance:** about 152,000 stars; heavily maintained, monthly releases; triage partly automated.
- **Complaints:** upgrades breaking knowledge bases and embeddings; model-key configuration failing after self-hosting; Docker deployment problems; a hard-to-stop workflow; no per-node tracing.
- **Traps:** an always-on Docker server; your own API keys; a licence with added conditions.
- **Verdict:** ignore – a server for building chatbots for other people.

### [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI)
A Python library for defining role-based agents and running them in sequence or parallel.
- **Maintenance:** about 56,900 stars; several releases a week; the busiest open threads are off-topic.
- **Complaints:** the most-discussed bug – agents producing plausible tool output instead of calling the tool; argument-shape errors; empty model responses; breaking changes; no duplicate protection when a task retries; telemetry on by default (switchable off).
- **Worth taking:** **idempotency** – when a step retries, never blindly re-run the parts that send, post, upload or spend.
- **Verdict:** ignore – a code-only version of what already runs.

### [langchain-ai/langchain](https://github.com/langchain-ai/langchain)
The general-purpose Python and JavaScript library for building LLM applications.
- **Maintenance:** about 144,000 stars; funded and active; enterprise asks often closed as out of scope.
- **Complaints:** too many abstraction layers; churn across major versions; output parsing (#1358 among the most commented); integrations breaking upstream.
- **Traps:** the optional tracing service ships prompts and traces off the machine.
- **Verdict:** ignore – raw material for building what already exists here.

### [Significant-Gravitas/AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)
Now a hosted, low-code agent platform; the 2023 agent sits in a `classic/` folder.
- **Maintenance:** about 186,500 stars; weekly beta releases; self-hosting problems open for over 18 months (#8918, #7179).
- **Traps:** the platform folder carries a source-available licence with a non-compete clause; hosted use runs on their cloud.
- **Worth taking:** a visual, re-runnable saved pipeline a non-coder can re-run by clicking.
- **Verdict:** ideas only.

### [ag2ai/ag2](https://github.com/ag2ai/ag2)
The community continuation of AutoGen: a Python library for agents that talk to each other.
- **Maintenance:** about 4,800 stars but about 460,000 monthly installs; active; several hard bugs took nine to eleven months to close (#1451, #1756, #103).
- **Complaints:** confusion over which AutoGen is which; a v1.0 that moved the classic API to a separate repository; repeated configuration redesigns (#1412, #1946); non-OpenAI providers second-class (#2243, #288).
- **Verdict:** ignore.

### [FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT)
Simulates a software company (product manager, architect, engineer, tester) to generate a project from one line.
- **Maintenance:** about 69,800 stars but about 20,800 monthly installs; last release in March 2025 at the time; recent reports unanswered (#2110).
- **Complaints:** narrow Python version support; non-OpenAI providers failing; crashes on malformed model output; uncapped cost per run.
- **Verdict:** ignore.

### [agno-agi/agno](https://github.com/agno-agi/agno)
A Python toolkit plus self-hosted runtime (API, Postgres, dashboard) for agent products.
- **Maintenance:** about 41,700 stars; very active; hard issues answered slowly.
- **Complaints:** session history bloat; team and streaming bugs; MCP reconnection; migration churn between major versions.
- **Verdict:** ignore – a developer platform; the parallel-agent part is already solved here.

### [mastra-ai/mastra](https://github.com/mastra-ai/mastra)
A TypeScript framework for agents and workflows inside a Node application.
- **Maintenance:** about 27,100 stars; very active; maintainers answer at length in public tracking issues.
- **Complaints:** memory and database bloat; breaking changes (they ship codemods); streaming and suspend/resume bugs.
- **Security:** public incident reports in June 2026 described an attacker using a former contributor’s unrevoked npm token to publish malicious package versions; the maintainers unpublished them within hours and tightened token rules.
- **Verdict:** ignore – and a reminder that `npm install` is the risk, not the runtime.

### [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai)
A Python library for agents whose inputs and outputs are validated against typed schemas.
- **Maintenance:** about 19,200 stars; very actively maintained; hard issues closed with milestones.
- **Complaints:** a shortened window between major versions; provider-specific bugs; slow arrival of headline features.
- **Verdict:** ignore – excellent library, but a building block for something already finished here.

### [run-llama/llama_index](https://github.com/run-llama/llama_index)
A framework for document retrieval (“chat with your documents”), now fronting a paid parsing service.
- **Maintenance:** about 51,600 stars; maintenance-mode releases; many hard questions answered by a bot.
- **Traps:** the strongest feature (document parsing) uploads documents to the vendor’s cloud.
- **Verdict:** ignore – it duplicates a local memory search that already works.

### [openinterpreter/openinterpreter](https://github.com/openinterpreter/openinterpreter)
Formerly a Python tool for running model-written code locally; since July 2026 a Rust fork of a terminal coding agent tuned for cheaper models.
- **Maintenance:** about 68,000 stars inherited from the old project; the old backlog was mass-closed in the rewrite.
- **Verdict:** ignore – a cheaper-model rival to a coding agent, with nothing for media work.

### [omnigent-ai/omnigent](https://github.com/omnigent-ai/omnigent)
A Python control layer above several coding agents, with spending rules and phone or browser access to a running session. Labelled alpha.
- **Maintenance:** about 8,500 stars, 35 watchers; very active, weekly releases.
- **Complaints:** platform breakage (#16); instructions ignored on 13 of 24 wrapped agents (#3530); sub-agent fan-out errors (#3870); high idle CPU.
- **Traps:** telemetry on by default; the phone feature needs an always-on server and a shareable session link.
- **Worth taking:** phone or browser access to a running job, and hard spend caps with approval before risky actions – both buildable without the stack.
- **Verdict:** ignore as an install.

### [e2b-dev/E2B](https://github.com/e2b-dev/E2B)
A paid cloud service that runs agent-written code in throwaway virtual machines.
- **Maintenance:** about 13,300 stars; active; some hard bugs slow (#884 took about eight months).
- **Traps:** your files go to their servers to be useful.
- **Verdict:** ignore – isolation this work does not need, at the cost of data leaving the machine.

### [infiniflow/ragflow](https://github.com/infiniflow/ragflow)
A self-hosted document search server that answers with a citation to the exact page.
- **Maintenance:** about 87,200 stars; heavily developed; long-running bug threads.
- **Complaints:** slow, memory-hungry parsing of large PDFs; documents stuck “parsing”; Docker first-run failures; local-model connection problems.
- **Traps:** a 16 GB, always-on Docker stack.
- **Worth taking:** page-level citations.
- **Verdict:** ignore as software.

### [mem0ai/mem0](https://github.com/mem0ai/mem0)
A memory library that extracts “facts” from conversations with an extra model call and stores them in a vector database.
- **Maintenance:** about 63,000 stars; funded and active; silent data-loss bugs open at the time (#5245, #5509).
- **Complaints:** #4573, a 32-day production audit, found 97.8% of 10,134 stored memories were junk (re-saved prompts, scheduler noise, invented user details) – closed without a linked fix; JSON failures with non-OpenAI models; cost per write.
- **Traps:** conversation text goes to a model provider on every write by default.
- **Worth taking:** **a periodic junk audit of your own memory** using #4573’s categories; curate memory deliberately rather than writing it automatically.
- **Verdict:** ignore as software.

### [CopilotKit/CopilotKit](https://github.com/CopilotKit/CopilotKit)
A React toolkit for putting an AI chat panel inside a web app you are building.
- **Maintenance:** about 36,700 stars; very fast release cadence.
- **Verdict:** ignore – it needs a web app to live in.

### [2FastLabs/agent-squad](https://github.com/2FastLabs/agent-squad)
A library that routes each incoming message to one of several specialised agents (formerly an AWS Labs project, now under its original authors’ own organisation).
- **Maintenance:** about 7,700 stars, 50 watchers; releases paused for about a year, then resumed in July 2026; 16 of 29 open issues had no reply at the time.
- **Complaints:** install breakage from upstream changes (#631, #456, #253); no way to see why a message was routed (#152); slow cold start (#126); state not saved (#350).
- **Verdict:** ignore – a one-agent-per-message switchboard, the opposite of a parallel fan-out.

---

Related: [security and data policy](security-and-data-policy.md) (the ten patterns and the vetting rule) · [how I engineer with AI coding agents](ai-engineering-method.md) · [orchestrating agent fleets](orchestrating-agent-fleets.md) · [`frameworks-intel.js`](../workflows/frameworks-intel.js) · [third-party vetting log template](templates/third_party_vetting_log.md)
