---
name: gpt-orchestrator
description: Route a task between local tools, Chat planning/review, Work artifacts and Codex code execution; produce bounded execution briefs and verify handoffs. Use when asked to orchestrate these surfaces or conserve model usage across a task.
---

# GPT Orchestrator

Use the local CLI in the enclosing project (`python3 -m gpt_orchestrator`). Read
[the CLI workflow](../README.md) when executing it; read
[browser boundaries](../docs/SECURITY.md) before selecting browser automation.
Treat account availability and usage as unknown unless the user supplies current
evidence. Work and Codex may share limits. There is no guaranteed free route or
supported API for turning Chat subscription messages into API credits.

## Classify and route

Use explicit user classification first. CLI keyword inference is a fallible
suggestion; override with `--kind` when needed.

| Need | Planner | Executor | Review |
| --- | --- | --- | --- |
| Known deterministic operation/check | local tool | local tool | actual exit/output |
| Text reasoning, explanation, drafting | Chat | Chat | criteria/context in Chat |
| Docs, sheets, slides, browser-produced deliverable | Chat | Work handoff with required tools | actual artifact + Chat |
| Repository edits, code, tests | Chat | Codex | local checks + Chat review |
| Sensitive/unshareable context | local/manual | local/manual | local/manual |

Use `route` for a zero-model-call recommendation. Avoid adding a Chat round-trip
to a known deterministic operation. For reasoning-only requests the user can
complete the task in Chat; the plan pipeline is intended for work needing an
executor. Work dispatch is a manual handoff; do not claim the CLI switches the
ChatGPT product's mode. Local/sensitive routes cannot use browser or Codex dispatch.

## Model selection and bounded escalation

1. Prefer an existing approved plan and compact excerpts; never send the whole
   repository, hidden files or credentials. Local routing makes no model call.
2. Simple tasks start at configured `cheap`; medium tasks use `standard`; complex
   tasks use `strong` when their dependencies/risk require it. These are local
   aliases, not invented model IDs or measured prices. Configure IDs available
   to this account. The browser uses the model selected manually in its own UI.
3. On the same diagnostic failure twice, stop. Propose the next configured tier
   with the failure evidence and scope; use `execute --tier ... --retry --apply`
   only when the user chooses that continuation. Never silently switch models.
4. Defaults cap web and Codex calls at two each per run. This bounds attempts,
   not token usage, money or subscription percentage. No parallel workers by
   default. No model auto-upgrade or provider fallback loop.

## Superpowers integration

The project pins the six selected skills and their local resources from MIT upstream. Its installer discovers the
sequential subset: brainstorming, writing-plans, executing-plans,
systematic-debugging, test-driven-development, verification-before-completion.
Use the relevant installed skills rather than repeatedly loading every skill.
The controller includes writing-plans in Chat planning prompts and verification
guidance in review prompts. The transport's DelegationPacket JSON format adapts
upstream's Markdown document format. Use the user's requested location/format.

## Execution Brief contract

Every brief contains:

- Original goal, selected route and model tier; cost/usage explicitly unknown.
- Workspace, supplied context, scope exclusions and authorization boundaries.
- Numbered plan: action, exact target and observable success criterion per step.
- Tests, acceptance criteria, risks, forbidden/out-of-scope changes.
- Required evidence: actual changed files, executed checks and exit codes,
  artifact inspection and unresolved limitations.
- Stop, escalation, manual handoff and rollback rules.

CLI output is `execution-brief.md` plus versioned `run.json`. Chat planning uses
chatgpt-use's goal/summary/plan/risks/tests/acceptance/do_not_do/verdict packet.
Import only schema-valid packets. A `proceed` plan is readiness, not permission
to expand scope; review it before `execute --apply`. Revise/blocked stops execution.

## Acceptance and fallback

Codex executes a reviewed brief using `workspace-write`; it does not receive
unrestricted execution flags. `execute` is a dry run until `--apply`. Run explicit
local checks with `verify`; never evaluate tests supplied by a model as shell code.
For review, explicitly supply sanitized diff/result excerpts. Logs are local and
are not uploaded automatically. `accept` needs recorded passing checks, a fresh
`proceed` review and explicit confirmation of observable acceptance. Agent exit 0
alone is insufficient. The CLI does not prove arbitrary acceptance criteria or
detect out-of-band workspace edits; recheck/review if files change.

If the browser is signed out, throttled, challenged, has a changed UI or gives an
ambiguous submission, stop and inspect it. Never defeat CAPTCHA or auto-resubmit.
Use manual copy/paste with the same packet contract, or pause. Preserve a response
that fails parsing and correct/import it without spending another call.

For code failure, retain the diff and check evidence. Propose a minimal correction
or reverse patch; never run reset/clean or overwrite unrelated user work. No
automatic switch to a paid API, no public tunnel and no web-controlled local shell.
