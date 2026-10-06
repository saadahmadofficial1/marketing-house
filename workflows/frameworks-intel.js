export const meta = {
  name: 'agent-frameworks-intel',
  description: 'Research 24 multi-agent and marketing-agent projects: what they are, what breaks, whether they beat what we already run',
  phases: [
    { title: 'Research', detail: 'two or three targets per agent — find the repo, read its issues' },
    { title: 'Judge', detail: 'one verdict across the field' },
  ],
}
const GROUPS = [
  { label: 'hermes+awesome', targets: [
    'NousResearch/hermes-agent — read ISSUE #344 specifically (https://github.com/NousResearch/hermes-agent/issues/344) plus the repo',
    'Agent-Analytics/awesome-multi-agent-orchestrators — the curated list itself: what does it contain, is it maintained' ] },
  { label: 'marketing-1', targets: [
    'coreyhaines31/marketingskills', 'hyperfx-ai/marketing-skills' ] },
  { label: 'marketing-2', targets: [
    'cgallic/kai-cmo-harness', 'Anil-matcha/Open-AI-UGC', 'jmedia65/awesome-ai-marketing' ] },
  { label: 'dify+crewai', targets: ['Dify (langgenius/dify)', 'CrewAI (crewAIInc/crewAI)'] },
  { label: 'langchain+autogpt', targets: ['LangChain (langchain-ai/langchain)', 'AutoGPT (Significant-Gravitas/AutoGPT)'] },
  { label: 'ag2+metagpt', targets: ['AG2, formerly AutoGen (ag2ai/ag2)', 'MetaGPT (FoundationAgents/MetaGPT)'] },
  { label: 'agno+mastra', targets: ['Agno (agno-agi/agno)', 'Mastra (mastra-ai/mastra)'] },
  { label: 'pydantic+llamaindex', targets: ['Pydantic AI (pydantic/pydantic-ai)', 'LlamaIndex (run-llama/llama_index)'] },
  { label: 'interpreter+omnigent', targets: ['Open Interpreter (OpenInterpreter/open-interpreter)', 'Omnigent — find the real repo, it is obscure'] },
  { label: 'e2b+ragflow', targets: ['E2B (e2b-dev/E2B)', 'RAGFlow (infiniflow/ragflow)'] },
  { label: 'mem0+copilotkit', targets: ['Mem0 (mem0ai/mem0)', 'CopilotKit (CopilotKit/CopilotKit)'] },
  { label: 'agentsquad', targets: ['Agent Squad, formerly AWS Multi-Agent Orchestrator (awslabs/agent-squad)'] },
]
const SCHEMA = {
  type: 'object', additionalProperties: false, required: ['projects'],
  properties: { projects: { type: 'array', items: {
    type: 'object', additionalProperties: false,
    required: ['name', 'url', 'what_it_is'],
    properties: {
      name: { type: 'string' }, url: { type: 'string' },
      what_it_is: { type: 'string' },
      popularity: { type: ['string', 'null'] },
      maintained: { type: ['string', 'null'] },
      top_complaints: { type: 'array', items: { type: 'string' } },
      needs: { type: ['string', 'null'] },
      relevance: { type: ['string', 'null'] },
      verdict: { type: ['string', 'null'] },
    } } } },
}
const CONTEXT = `WHO THIS IS FOR — judge everything against this, do not review in the abstract:
Saad runs in-house marketing and media production (UAE). He is NOT a developer and will never write code or run a terminal command. His Mac holds work files that must stay under his control. His actual work: software training videos, screen recordings, call-out boxes, captions, CapCut projects, social content, brand assets.
What he ALREADY has, working today: Claude Code with a workflow engine that fans out dozens of parallel subagents with structured outputs and verification passes (13-18 agents used routinely), a local memory/brain, MCP connectors for image/video/audio generation, and a large set of purpose-built Python tools. So "orchestrate multiple agents" is SOLVED here — the bar for anything new is that it must beat that, for a non-coder, without putting work data at risk.`
phase('Research')
const out = await parallel(GROUPS.map(g => () => agent(
  `${CONTEXT}

Research these projects. Find each one's real GitHub URL yourself (the names in brackets are hints, verify them — some may be renamed, moved or obscure). Desk research only: read public pages, install nothing.

Targets:
${g.targets.map(t => `- ${t}`).join('\n')}

For EACH, use WebFetch on the repo page and on its most-discussed issues:
  https://github.com/<repo>/issues?q=is%3Aissue+sort%3Acomments-desc
  https://github.com/<repo>/issues?q=is%3Aissue+is%3Aclosed+sort%3Acomments-desc

Report:
- name, url (the verified canonical URL)
- what_it_is: two plain sentences. No marketing language. If it is a curated list rather than software, say so.
- popularity: stars, and how much genuine activity (not just stars)
- maintained: last release/commit, whether maintainers answer hard issues
- top_complaints: the recurring problems real users report (3-6), most frequent first, plain English
- needs: what it actually takes to run — API keys, Docker, Python, a server, ongoing cost
- relevance: honestly, would this do anything for a non-coding marketing/video user that Claude Code's built-in parallel subagents do not already do? Say "nothing new" if that is the truth.
- verdict: one line — adopt / ideas worth stealing / ignore, and why

Be blunt. Most of these will be irrelevant to him and saying so clearly is more useful than a balanced summary.`,
  { label: g.label, phase: 'Research', schema: SCHEMA })))
const projects = out.filter(Boolean).flatMap(r => r.projects)
phase('Judge')
const verdict = await agent(
  `${CONTEXT}

Here is research on ${projects.length} agent/marketing projects:

${projects.map(p => `## ${p.name} — ${p.url}\n${p.what_it_is}\nPOPULARITY: ${p.popularity}\nMAINTAINED: ${p.maintained}\nCOMPLAINTS: ${(p.top_complaints||[]).join(' | ')}\nNEEDS: ${p.needs}\nRELEVANCE: ${p.relevance}\nVERDICT: ${p.verdict}`).join('\n\n')}

Write a decision memo for Saad in plain British English, no hype, structured as:

1. **The short answer** — 3-4 sentences: does he need any of this for multi-agent work, given what already runs on his Mac?
2. **The two or three genuinely worth knowing about** — and precisely what for (an idea to steal, a capability we lack, or a thing to watch). Be specific about what each would give him that he does not have.
3. **What the marketing-skill repos actually contain** — these are the ones closest to his day job; is there anything usable, and what would using it look like (copy a prompt? nothing?).
4. **The pattern across the field** — what these 24 projects collectively reveal about agent frameworks in 2026, tied to the failure patterns already documented (silent failure, stars ≠ maintenance, local-means-remote, installers touching permissions).
5. **What I recommend, in one line.**

Do not pad. If the answer is "install nothing", say it and justify it.`,
  { label: 'decision-memo', phase: 'Judge' })
return { projects, verdict }