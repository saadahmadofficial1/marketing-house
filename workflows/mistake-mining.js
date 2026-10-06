export const meta = {
  name: 'mistake-patterns',
  description: 'Analyse every mistake since day one, find the recurring patterns, and identify which still lack a systemic guard',
  phases: [
    { title: 'Excavate', detail: 'readers over the full correction history, oldest first' },
    { title: 'Pattern', detail: 'classify into recurring failure modes' },
    { title: 'Audit', detail: 'which patterns have real guards vs apologies' },
  ],
}

// Workspace root: pass it as the workflow's args, e.g. {"root": "/path/to/workspace"}.
const W = args && args.root
if (!W) throw new Error('missing args.root - the absolute path of the workspace to mine')

const SOURCES = `
THE RECORD — mistakes live here. Read deeply; the oldest material is at the BOTTOM of
newest-first files:
  ${W}/SA_FEEDBACK.md      the corrections log. The core source.
  ${W}/SA_WORKLOG.md       what was done, including failures admitted in passing.
  ${W}/SA_INSTINCTS.md     reflexes already distilled — these are mistakes that GOT a guard.
  ${W}/Reference/PIPELINE_TRAPS.md       traps that cost rework, with their guards.
  ${W}/Reference/SAAD_EDITING_TECHNIQUE.md  includes wrong conclusions that were corrected.
  ${W}/Reference/MODEL_PLAYBOOK.md       earlier model's traps if present.
  ${W}/Sessions/*/log.jsonl              session-by-session record.
`

const MISTAKE = {
  type: 'object', additionalProperties: false,
  required: ['mistakes'],
  properties: {
    era: { type: 'string' },
    mistakes: { type: 'array', items: { type: 'object', additionalProperties: false,
      required: ['what', 'date', 'root_cause', 'cost', 'guard_now'],
      properties: {
        what: { type: 'string', description: 'the mistake, concretely — what was done wrong' },
        date: { type: 'string' },
        project: { type: 'string' },
        root_cause: { type: 'string', description: 'the REAL cause, not the symptom' },
        cost: { type: 'string', description: 'what it cost — rework hours, credits, trust, a wrong deliverable' },
        guard_now: { type: 'string', enum: ['systemic', 'noted-only', 'none'],
          description: 'systemic = a test/tool/check now PREVENTS it; noted-only = written down but nothing enforces it; none = could recur silently' },
        guard_detail: { type: 'string', description: 'what the guard is, or what is missing' },
      } } },
  },
}

phase('Excavate')

// One brief per period of YOUR history: what happened then and where it is recorded.
// Readers go deeper on a narrow era than on the whole record, so split a long history;
// keep one era for meta-mistakes (errors in HOW the agent worked, not in deliverables).
const ERAS = [
  ['early', `The first months: the first deliverables and the first corrections. Read the
OLDEST part of the feedback log (the BOTTOM of a newest-first file) and the earliest
instincts.`],
  ['middle', `The middle period: the first larger projects and the first tools built for
them. The middle of the feedback log, plus the worklog and session logs for those months.`],
  ['recent', `The most recent delivery work: defects found in review, rework, pacing and
sign-off problems. The top of the feedback log and the pipeline-traps list.`],
  ['meta', `The meta-mistakes, across the whole record: recency blindness (a conclusion drawn
from a few weeks of one project), confident root causes stated before reading the actual
error, a model's non-answer counted as a defect, a low-yield automation nearly shipped,
benchmarks run with a placeholder prompt, the wrong file tested, the agent's own writes
logged as the owner's, the owner asked to do work a standing rule says the agent does.
Usually logged candidly at the top of the feedback log and in the worklog.`],
]

const digs = await parallel(ERAS.map(([key, brief]) => () =>
  agent(
`You are excavating every MISTAKE the AI agent (Claude/the system) made in one era of a
long collaboration with its owner. Read-only. This is a post-mortem the owner asked for
(analyse the mistakes and how each can be solved). Honesty is the point —
flattery or softening makes it worthless.

ERA: ${key}
${brief}

${SOURCES}

Extract every distinct mistake THE AGENT made (not the owner's, not the team's). For each: what
happened, the real root cause, what it cost, and crucially whether TODAY there is a
systemic guard (a test, a tool check, an enforced rule) or it is merely written down.
To judge "systemic", check whether a Tools/*.py self-test or built-in check enforces it —
grep the Tools directory when unsure.

Ten to twenty well-evidenced mistakes beat fifty vague ones. Exact dates and quotes where
the record has them.`,
    { label: `dig:${key}`, phase: 'Excavate', schema: MISTAKE },
  )
))

const all = digs.filter(Boolean).flatMap(d => d.mistakes)
log(`${all.length} mistakes excavated across ${ERAS.length} eras`)

phase('Pattern')

const patterns = await agent(
`${all.length} mistakes from a long AI-human collaboration, each with root cause and
guard status:

${JSON.stringify(all, null, 1)}

Classify them into RECURRING PATTERNS — the underlying failure modes, not the surface events.
A pattern must have at least two instances from different months or projects to count.
Examples of the kind of abstraction wanted: "verified the parameter, not the picture",
"a limit invented for one purpose reused as a test for another", "confident root-cause
stated before reading the actual error", "the newest data treated as the whole history".

For each pattern: name it memorably, list its instances with dates, state the mechanism that
would prevent the CLASS (not the instance), and whether that mechanism exists today.
Also list the mistakes that genuinely never recurred — one era, fixed, done — separately
and briefly. Return well-structured markdown.`,
  { label: 'pattern', phase: 'Pattern' },
)

phase('Audit')

const audit = await agent(
`Here is a pattern analysis of an AI agent's mistakes over many months:

${patterns}

And the raw mistakes with their guard status:

${JSON.stringify(all.map(m => ({ what: m.what.slice(0, 100), guard: m.guard_now })), null, 1)}

You are the auditor. Produce the final document, plain British English, for a non-technical
owner and the agent itself:

# Every mistake since day one — the patterns, and what actually stops them

1. **The scoreboard** — mistakes found, how many have a real systemic guard, how many are
   only written down, how many could recur silently.
2. **The patterns** (from the analysis, verified against the raw list — cut any pattern with
   fabricated instances). For each: name, 2-4 dated examples, the guard that exists or the
   guard that is MISSING, stated as a concrete buildable thing.
3. **The top 5 missing guards**, ranked by how much the pattern has already cost. Each one:
   what to build, roughly how small, and which past mistakes it would have caught.
4. **What genuinely got fixed** — patterns that have not recurred since their guard landed,
   as proof the loop works.

Under 1100 words. No self-flagellation, no praise — an engineering document.`,
  { label: 'audit', phase: 'Audit' },
)

return { document: audit, mistakeCount: all.length,
         guardless: all.filter(m => m.guard_now !== 'systemic').length }
