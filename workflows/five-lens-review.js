export const meta = {
  name: 'kit-critique',
  description: 'Adversarial review of the team workspace kit before distribution',
  phases: [{ title: 'Critique', detail: 'five lenses, independently' }, { title: 'Rank', detail: 'what must be fixed before it ships' }],
}
// The folder under review: pass it as the workflow's args, e.g. {"kit": "/path/to/kit"}.
const KIT = args && args.kit
if (!KIT) throw new Error('missing args.kit - the absolute path of the folder under review')
const SCHEMA = {
  type: 'object', additionalProperties: false, required: ['findings'],
  properties: { findings: { type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['severity', 'problem', 'fix'],
    properties: {
      severity: { type: 'string', enum: ['blocker', 'serious', 'minor'] },
      file: { type: ['string', 'null'] },
      problem: { type: 'string' },
      why_it_matters: { type: ['string', 'null'] },
      fix: { type: 'string' },
    } } } },
}
const LENSES = [
  { label: 'first-timer', prompt:
`You are a graphic designer at a mid-sized company. You have never opened Terminal. You use ChatGPT in a browser sometimes. Your manager just handed you this folder and said "set this up".

Read ${KIT}/README_START_HERE.md, CHEAT_SHEET.md, FIRST_RUN.md and CLAUDE.md, and walk through the setup literally, step by step, as you would actually experience it.

Find every place you would get stuck, confused, or give up. Be specific and unforgiving: a missing step, an assumed piece of knowledge, a command that will not work as written, jargon nobody defined, a moment where nothing tells you whether it worked. Check the install command and the folder path instructions actually make sense together. Report what would make you close the terminal and go back to the browser tab.` },
  { label: 'security-it', prompt:
`You are the IT security reviewer for a large company. Someone wants to roll this workspace out to staff on company Macs holding sensitive work files.

Read everything in ${KIT} — especially CLAUDE.md, Tools/security_gate.py, Tools/autotrack.py, Tools/progress.py, Tools/share_delta.sh, brain/SETUP.md, Reference/DATA_POLICY.json, charters/security.md.

Find what you would block or demand changes to: data that could leave the machine unnoticed, files scanned that should not be, scripts doing something the docs do not disclose, missing guidance on confidential material, anything that reads from arbitrary paths, licence/ownership problems. Also check whether autotrack could read folders containing sensitive files and whether that is disclosed to the user.` },
  { label: 'skeptic', prompt:
`You are a hostile reviewer looking for claims this kit cannot back up, and for things that will break in real use.

Read ${KIT}/README_START_HERE.md, ORIGIN.md, Reference/HARD_WON_LESSONS.md, Tools/progress.py, Tools/autotrack.py, AGENT_ORCHESTRATION.md, ROLES.md.

Find: promises that overstate what this can do; measurements that could mislead (especially the productivity numbers — could they be gamed, or wrong for legitimate reasons?); instructions that would produce a bad outcome if followed literally; internal contradictions between documents; anything that assumes a capability the tools do not have. Quote the exact line each time.` },
  { label: 'three-months-later', prompt:
`You are the same employee three months after setting this up. You have used it a fair amount. Now you are looking at the folder again.

Read ${KIT} and judge it for the LONG term: what will have rotted, filled up with junk, or stopped being true? What happens when the memory folder has 200 files? When a project finishes? When they change roles or get a new laptop? When someone else needs to pick up their work? When they want to stop using it and take their data?

Find what is missing for month three that nobody thinks about on day one.` },
  { label: 'completeness', prompt:
`You are reviewing this kit for what is ENTIRELY ABSENT rather than what is wrong.

Read every file in ${KIT} (list the directory first). Compare what is here against what a person in a marketing/creative department actually needs from an AI workspace over a year of use.

Name the gaps: capabilities not covered, situations not handled, documents that should exist and do not, questions a new user will certainly ask that nothing answers. Do not list nice-to-haves — only things whose absence will actually cost someone.` },
]
phase('Critique')
const out = await parallel(LENSES.map(l => () => agent(
  l.prompt + `\n\nReturn findings with severity blocker (they cannot succeed without this fixed), serious (real cost or risk), or minor. For each: the file, the problem, why it matters, and a concrete fix. Be concise and specific — quote lines. Do not pad the list; five sharp findings beat fifteen soft ones.`,
  { label: l.label, phase: 'Critique', schema: SCHEMA })))
const all = out.filter(Boolean).flatMap((r, i) => r.findings.map(f => ({ ...f, lens: LENSES[i].label })))
phase('Rank')
const ranked = await agent(
  `Here are ${all.length} findings from five independent reviews of a workspace kit about to be distributed to colleagues:

${all.map(f => `[${f.lens}/${f.severity}] ${f.file || '-'}: ${f.problem}\n  WHY: ${f.why_it_matters || ''}\n  FIX: ${f.fix}`).join('\n\n')}

Produce the fix list, ordered, in this shape:
1. **MUST FIX BEFORE SENDING** — things that will actually stop a colleague succeeding, or create a security/trust problem. For each: one line on the problem, one line on the exact fix.
2. **SHOULD FIX** — real but not blocking.
3. **REJECT** — findings that are wrong, duplicated, or would make the kit worse (say why briefly).

Be decisive. Merge duplicates across lenses. If two lenses found the same thing, that raises its priority. Plain British English.`,
  { label: 'fix-list', phase: 'Rank' })
return { findings: all, ranked }