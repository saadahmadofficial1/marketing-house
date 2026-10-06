export const meta = {
  name: 'adversarial-verify',
  description: 'Re-check every marking in two training-video cuts (a and b), then adversarially verify every major finding',
  phases: [
    { title: 'Check', detail: 'one agent per marking, judging its START and END frame' },
    { title: 'Verify', detail: 'three refuters per major finding — a finding survives only if it cannot be refuted' },
  ],
}

const CHECK = {
  type: 'object',
  properties: {
    name: { type: 'string' },
    ok: { type: 'boolean' },
    problems: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          kind: { type: 'string', enum: ['screen', 'target', 'chip', 'script'] },
          claim: { type: 'string' },
          severity: { type: 'string', enum: ['minor', 'major'] },
        },
        required: ['kind', 'claim', 'severity'],
      },
    },
  },
  required: ['name', 'ok', 'problems'],
}

const VERDICT = {
  type: 'object',
  properties: {
    refuted: { type: 'boolean' },
    why: { type: 'string' },
  },
  required: ['refuted', 'why'],
}

function ask(dir, it) {
  return `Check one marking in a screen-recorded training video against the two frames where it is on screen.

START frame: ${dir}/${it.name}_S.png
END frame:   ${dir}/${it.name}_E.png

The marking is a blue outline box with a blue label chip reading: "${it.purpose}"
The narration playing over it says: "${it.phrase}"

Read both frames. Measure with PIL wherever a claim depends on pixels — quote the numbers you measured.

Judge four things, and file each fault you find as a separate problem with its own severity:
1. SCREEN — is the picture the SAME screen in both frames? A scroll, a dropdown opening or closing,
   a page load, a modal appearing between them is MAJOR: the marking has outlived its screen. This is
   the fault reviewers flag most, so be severe. Note that a dropdown opening changes only
   about 2% of the frame, so compare the region, not just the whole-image average.
2. TARGET — is the box on the thing the narration names? It must contain that thing fully, not slice
   text with its border, and not cross into the left sidebar (page content starts at x=${args.contentX ?? 248}).
3. CHIP — does the label chip cover anything the viewer needs to read? A chip that merely repeats the
   label of the field it sits on is acceptable. A chip covering a DIFFERENT field's value is MAJOR.
4. SCRIPT — does what is marked match what the words say? If the words name a control and the box is
   on a heading, a breadcrumb or a subtitle instead, that is MAJOR.

Be precise and be fair. Do NOT file a passing observation as a problem — if a dimension is fine, say
nothing about it. ok=true only if this marking would pass in a customer-facing training video.`
}

function refute(dir, it, p) {
  return `You are checking whether a reported fault in a training video is REAL.

START frame: ${dir}/${it.name}_S.png
END frame:   ${dir}/${it.name}_E.png
The marking's label chip reads: "${it.purpose}"
The narration says: "${it.phrase}"

THE CLAIM (filed as a major fault): ${p.claim}

Your job is to try to REFUTE it. Open the frames, measure the actual pixels with PIL, and decide.
Set refuted=true ONLY if you can demonstrate the claim is factually wrong about these frames — the
coordinates are misread, the element is in fact contained, the screens are in fact identical, the
chip covers only its own label. If the claim holds, or you cannot show it is wrong, set refuted=false.
Guessing "probably fine" is not a refutation. Quote the measurements you took either way.`
}

const ITEMS = [
  ...args.a.items.map(i => ({ ...i, side: 'a', dir: args.a.dir })),
  ...args.b.items.map(i => ({ ...i, side: 'b', dir: args.b.dir })),
]

const results = await pipeline(
  ITEMS,
  it => agent(ask(it.dir, it), { label: `${it.side}:${it.name}`, phase: 'Check', schema: CHECK }),
  (res, it) => {
    if (!res) return null
    const problems = res.problems || []
    const majors = problems.filter(p => p.severity === 'major')
    const minors = problems.filter(p => p.severity !== 'major').map(p => `${p.kind}: ${p.claim}`)
    if (!majors.length) return { side: it.side, name: it.name, confirmed: [], killed: 0, minors }
    return parallel(majors.map(p => () =>
      parallel([0, 1, 2].map(k => () =>
        agent(refute(it.dir, it, p), { label: `${it.side}:${it.name}:refute${k}`, phase: 'Verify', schema: VERDICT })))
        .then(vs => {
          const v = vs.filter(Boolean)
          return { kind: p.kind, claim: p.claim, killed: v.length >= 2 && v.filter(x => x.refuted).length >= 2 }
        })))
      .then(cs => {
        const c = cs.filter(Boolean)
        return {
          side: it.side, name: it.name,
          confirmed: c.filter(x => !x.killed).map(x => `${x.kind}: ${x.claim}`),
          killed: c.filter(x => x.killed).length,
          minors,
        }
      })
  })

const side = tag => {
  const rs = results.filter(Boolean).filter(r => r.side === tag)
  const broken = rs.filter(r => r.confirmed.length)
  return {
    checked: rs.length,
    perfect: rs.filter(r => !r.confirmed.length && !r.minors.length).length,
    majors_confirmed: broken.length,
    majors_refuted_and_dropped: rs.reduce((n, r) => n + r.killed, 0),
    with_minors_only: rs.filter(r => !r.confirmed.length && r.minors.length).length,
    faults: broken.map(r => ({ n: r.name, problems: r.confirmed })),
    minors: rs.filter(r => r.minors.length).map(r => ({ n: r.name, problems: r.minors })),
  }
}

return { a: side('a'), b: side('b') }
