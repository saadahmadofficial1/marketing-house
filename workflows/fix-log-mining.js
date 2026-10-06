export const meta = {
  name: 'fix-log-mine',
  description: 'Mine the workspace history for every defect that was found and fixed, with its guard and test',
  phases: [
    { title: 'Mine' },
    { title: 'Verify guards' },
  ],
}

const REC = {
  type: 'object',
  properties: {
    fixes: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          symptom: { type: 'string', description: 'What you would OBSERVE — the wrong output, the false report, the visible damage. Written so it can be recognised again.' },
          cause: { type: 'string', description: 'The actual root cause, not the first theory' },
          fix: { type: 'string', description: 'What was changed' },
          where: { type: 'string', description: 'file(s) and function(s), exactly as they appear on disk' },
          guard: { type: 'string', description: 'the check/test that now stops it recurring, or NONE' },
          date: { type: 'string' },
          class: { type: 'string', description: 'one of: measurement-lied, tool-damaged-work, false-learning, name-vs-content, stale-artefact, silent-failure, confidentiality, other' },
        },
        required: ['symptom', 'cause', 'fix', 'where', 'class'],
      },
    },
  },
  required: ['fixes'],
}

// Workspace root: pass it as the workflow's args, e.g. {"root": "/path/to/workspace"}.
const ROOT = (args && args.root) || '/path/to/your/workspace'

phase('Mine')

const SOURCES = [
  { k: 'traps', p: 'Read ' + ROOT + '/Reference/PIPELINE_TRAPS.md IN FULL. Extract every trap as a structured fix record. The symptom field must describe what a person would SEE going wrong, so it can be recognised again without reading the whole file. Preserve the exact file and function names given.' },
  { k: 'mistakes', p: 'Read ' + ROOT + '/Reference/MISTAKE_PATTERNS.md and ' + ROOT + '/Reference/DEBUG_PLAYBOOK.md IN FULL. Extract every distinct mistake and diagnosis rule as a fix record. Where a rule is about HOW to diagnose rather than a specific bug, still record it with symptom = the situation that should trigger it.' },
  { k: 'gaps', p: 'Read ' + ROOT + '/Reference/VERIFIER_GAPS.md IN FULL. These are defects that got PAST a passing check — the most valuable kind. Extract each as a fix record. If a gap is still open with no guard, set guard to "NONE — still open".' },
  { k: 'worklog', p: 'Read the last 400 lines of ' + ROOT + '/SA_WORKLOG.md and the last 200 lines of ' + ROOT + '/SA_FEEDBACK.md. Extract every entry that describes a DEFECT THAT WAS FOUND AND FIXED in a tool or a video build. Ignore entries that are only progress updates or project news. Focus on the most recent month.' },
  { k: 'code', p: 'Search ' + ROOT + '/Tools/*.py for comments that document a past failure — they typically name a date and what went wrong (for example "12 Aug:", "found by getting it wrong on", "this is why this branch exists"). Use grep for patterns like Aug, "was wrong", nearly, destroyed, lied, false. Each such comment marks a real defect whose fix is in that code. Extract them as fix records, setting the where field to the exact file and function.' },
]

const mined = await parallel(SOURCES.map(s => () =>
  agent('You are building a fast-lookup fix log for a video production workspace, so that when a\n' +
    'defect recurs it can be identified and fixed in minutes instead of re-derived from scratch.\n\n' +
    s.p + '\n\n' +
    'Be precise and concrete. Never invent a file path, a function name or a date — if the source\n' +
    'does not give one, say "not recorded". Prefer the source own wording for what went wrong.',
    { label: 'mine:' + s.k, phase: 'Mine', schema: REC })))

const all = mined.filter(Boolean).flatMap(m => m.fixes)
log('mined ' + all.length + ' fix records from ' + mined.filter(Boolean).length + ' sources')

phase('Verify guards')

const CHECK = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          symptom: { type: 'string' },
          guard_real: { type: 'string', enum: ['exists-and-tested', 'exists-untested', 'claimed-but-absent', 'none'] },
          evidence: { type: 'string' },
        },
        required: ['symptom', 'guard_real'],
      },
    },
    duplicates: { type: 'array', items: { type: 'string' } },
    still_open: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdicts'],
}

const verdict = await agent('You are checking a fix log for honesty before it becomes the\n' +
  'reference people trust.\n\n' +
  'For each record below, verify the claimed guard ACTUALLY EXISTS in the code. Open the named\n' +
  'file in ' + ROOT + '/Tools/ and look for the check and for a corresponding assertion in its\n' +
  '_test() function. A guard described in prose but with no test is "exists-untested". A guard\n' +
  'that is not in the code at all is "claimed-but-absent" — that is the most important thing to\n' +
  'catch, because a fix log claiming protection it does not have is worse than no log.\n\n' +
  'Also list records that duplicate each other across sources, and every defect with no guard.\n\n' +
  'RECORDS:\n' + JSON.stringify(all, null, 1).slice(0, 90000),
  { label: 'verify:guards', phase: 'Verify guards', schema: CHECK, effort: 'high' })

return { fixes: all, verdict }
