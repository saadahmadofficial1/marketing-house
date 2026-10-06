export const meta = {
  name: 'research-fanout',
  description: 'Sweep the open-source agent-harness ecosystem and distil ideas worth adopting into a personal AI production system',
  phases: [
    { title: 'Research', detail: 'one researcher per harness pillar, web sweep' },
    { title: 'Synthesise', detail: 'rank what is worth stealing vs skipping' },
  ],
}

const OURS = `
WHAT WE ALREADY HAVE (judge every candidate against this — most will lose):
- Memory: a local file-based brain (markdown logs + MCP search/log tools), corrections logged
  in real time, a distilled "how the owner works" document, auto-memory. Works daily.
- Tools: dozens of small Python scripts (video pipeline: captions, call-out boxes,
  CapCut project surgery, verification, dashboards). Routine checks run locally; cloud
  calls (voice, generation) go through a data-policy gate. Most have a --test self-check.
- Workflows: multi-agent fan-outs with adversarial verification (a 52-agent measuring fleet
  with independent visual verification held a 25/27 yield).
- Time: a self-paced in-session loop + wakeups; nightly local vision-indexing routine.
  WEAKEST PILLAR: no durable out-of-session scheduling (a launchd attempt failed on macOS
  permissions; everything depends on the session being open).
- Feedback loops: live watcher reading the owner's CapCut edits from the project file,
  screen capture of the editor window, a diff of his finished work vs the machine build,
  distilled technique files. Strongest pillar.
- Guardrails: routine image checks run on LOCAL Ollama and frames never go to generation services; write-tools refuse while the
  target app is open; backups before every write; finished work is never touched; verifiers
  use three outcomes (ok / wrong / no-answer) and refuse rather than guess.

HOUSE RULES (hard):
- Owner is non-technical; routine checks run locally and upload nothing; local-first.
- Never adopt a framework wholesale — distil the 2-3 useful rules, bin the rest.
- Prefer a 100-line native script over a dependency. Any install must be inspectable,
  actively maintained, and must not phone home.
`

const FINDINGS = {
  type: 'object', additionalProperties: false,
  required: ['pillar', 'steal', 'skip'],
  properties: {
    pillar: { type: 'string' },
    steal: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['idea', 'source', 'why_it_beats_ours', 'how_small'],
      properties: {
        idea: { type: 'string', description: 'the specific mechanism, not the project name' },
        source: { type: 'string', description: 'project/repo/article it comes from' },
        why_it_beats_ours: { type: 'string' },
        how_small: { type: 'string', description: 'the minimal native way to adopt it — lines of code, not frameworks' },
        install_instead: { type: 'string', description: 'ONLY if a real install genuinely beats reimplementing: the package, its licence, maintenance state, and what to inspect before installing' },
      } } },
    skip: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['name', 'why'],
      properties: { name: { type: 'string' }, why: { type: 'string' } } } },
  },
}

const PILLARS = [
  ['memory', `Agent memory systems: Letta/MemGPT, Mem0, Zep, LangMem, compaction/consolidation
strategies, memory decay, episodic vs semantic splits, self-editing memory. Our brain is
markdown + grep and it works — what specific mechanism would make it sharper without a
database dependency?`],
  ['tools-skills', `Tool/skill ecosystems: Anthropic skills format, MCP server patterns,
tool self-description, tool-use verification, auto-generated tool docs, tool test harnesses.
What conventions make a large script toolbox easier for an agent to wield correctly?`],
  ['workflows', `Multi-agent orchestration: LangGraph, AutoGen, CrewAI, OpenHands, SWE-agent,
claude-flow, swarm patterns. We already do fan-out + adversarial verify well. What specific
coordination/verification patterns are proven that we lack — e.g. debate, plan-then-execute
contracts, checkpointing mid-workflow?`],
  ['time', `Durable scheduling and long-running autonomy on a developer Mac: launchd done
right (Full Disk Access nuances), cron alternatives, Temporal-lite patterns, watchdogs,
heartbeat monitors, resumable job state. THIS IS OUR WEAKEST PILLAR — an overnight job died
on macOS TCC permissions. What is the reliable minimal pattern for unattended nightly work
on macOS, and for a loop that survives the session closing?`],
  ['feedback', `Self-improvement loops: eval harnesses, regression suites for agent behaviour,
Reflexion-style self-critique, trajectory replay, learned preference files, A/B against a
human's finished work. We diff the owner's final edits against machine builds — what would
compound that further?`],
  ['guardrails', `Guardrail systems: guardrails-ai, NeMo Guardrails, Anthropic's constitutional
patterns, pre-flight check frameworks, permission sandboxes, undo/rollback systems. Ours are
per-tool conventions — is there a proven pattern for centralising pre-flight checks and
rollback without a framework?`],
]

phase('Research')

const results = await parallel(PILLARS.map(([key, brief]) => () =>
  agent(
`You are researching the open-source agent-harness ecosystem for one pillar, to find ideas
worth adopting into a working personal AI production system.

PILLAR: ${key}
${brief}

${OURS}

Use WebSearch (and WebFetch on the most promising results) to survey what exists NOW
(August 2026). Read actual READMEs/docs, not just search snippets, for your top candidates.

Return via the schema:
- steal: 2-5 SPECIFIC mechanisms worth taking. A mechanism, not a vibe — "X keeps a rolling
  errors.md that the agent must read before repeating a failed command" is a mechanism.
  For each, say the smallest native way to adopt it. Recommend an actual INSTALL only when
  reimplementing would be genuinely worse, and then name licence + maintenance state + what
  to inspect first.
- skip: the famous things in this pillar we should NOT adopt, each with a one-line reason
  grounded in our house rules.

Be sceptical. Our system works; the bar for change is "this fixes a weakness we actually
have", not "this is popular".`,
    { label: `research:${key}`, phase: 'Research', schema: FINDINGS },
  )
))

phase('Synthesise')

const all = results.filter(Boolean)
const report = await agent(
`Six researchers surveyed the open-source agent-harness ecosystem, each judging against the
same working system and house rules. Their findings:

${JSON.stringify(all, null, 1)}

${OURS}

Write the decision document, in plain British English, for a non-technical owner (Saad) AND
the agent that will implement it. Structure:

# Harness ideas worth stealing — and what we ignored
1. **Do now** — the 3-5 highest-value ideas, ranked. For each: what it is in one plain
   sentence, which of our real weaknesses it fixes, and the concrete implementation step
   (file to create/change, ~size). Time pillar fixes rank first — it is our weakest.
2. **Do later** — worthwhile but not urgent.
3. **Installs** — ONLY if any survived scrutiny: package, licence, what to inspect first.
   If none survived, say plainly "nothing needs installing — ideas only".
4. **What we already do better** — the famous tools the researchers rejected and the one-line
   reasons, so nobody re-litigates this next month.

Keep it under 900 words. No hype, no framework names without a reason attached.`,
  { label: 'synthesise', phase: 'Synthesise' },
)

return { report, pillars: all.map(a => ({ pillar: a.pillar, steal: a.steal.length, skip: a.skip.length })) }
