# GPT Orchestrator

Chat plans and reviews; Codex executes code tasks; Work receives manual artifact handoffs. A local Python CLI for task routing, execution briefs, bounded attempts, and evidence-based acceptance.

[中文完整说明](README.zh-CN.md) · [Security boundaries](docs/SECURITY.md) · [Validation](docs/VALIDATION.md) · [Roadmap](docs/ROADMAP.md)

**Early-stage project.** The core workflow is tested with synthetic fixtures and a fake executor. Real ChatGPT browser round-trips, real Codex model execution, quota savings, and external adoption have not been established. Work dispatch is manual. Route labels do not change a product's actual billing or usage limits.

## Start offline

Python 3.9+ on macOS/Linux; no Python dependencies for manual handoff. Windows is not tested; the locking/process implementation targets POSIX systems.

```sh
sh scripts/install.sh
./gpt-orchestrator-cli doctor
./gpt-orchestrator-cli route --task 'Fix input validation in a Python program' --kind code
./gpt-orchestrator-cli brief --task-file examples/tasks/code.md \
  --kind code --workspace "$PWD/examples/demo-workspace" --out runs/demo
```

These commands do not call a model. The installer creates project-local skill links and a local configuration. Keep the generated files private. The brief command requires a new output directory. `plan-request.md` is a prompt you manually copy into Chat after reviewing its contents.

## Workflow

1. Generate a brief, review its scope, and give the planning prompt to Chat.
2. Save Chat's JSON reply, then import it with `import-packet --run runs/demo --file runs/demo/chat-plan.txt`.
3. Review the packet and execution brief. `execute` previews by default; `--apply` authorizes the actual Codex subprocess. Choose a configured model or explicitly select `--use-codex-default`.
4. Run a trusted local check using `verify --run runs/demo --apply -- python3 -m unittest -v`. This command executes your explicit arguments; it is not an extra OS sandbox.
5. Prepare sanitized diff/check evidence for Chat review. Import its review packet, then confirm observable acceptance using `accept --run runs/demo --confirm-acceptance`.

See the Chinese guide for exact command sequences and failure recovery. Model plans are proposals, not authority to expand a task. Passing checks and an agent exit code do not prove arbitrary acceptance criteria. External edits are not automatically detected.

## What is included

- Explainable Chinese/English keyword routing with explicit overrides; usage estimates remain unknown.
- Strict `DelegationPacket` import, execution briefs, state locks, timeouts, call ceilings, and review invalidation after new execution/checks.
- Six pinned MIT Superpowers skills and their local resources, with six sequential workflow skills installed by default.
- An adaptation of the MIT chatgpt-use delegation protocol, its original protocol source and license. This is not the upstream CLI or its browser transport.
- An optional, experimental Playwright browser adapter with a dedicated manually logged-in profile. It does not export cookies or use private ChatGPT APIs. Read the security guide before opting in; it has not passed real ChatGPT integration testing.

## Measure usage offline

Run `python3 scripts/usage_report.py examples/usage.synthetic.jsonl` to summarize synthetic API usage. Cached input remains part of total input; missing counts remain unknown. No prices or subscription savings are inferred. See [measurement method](docs/MEASUREMENT.md).

## Test

```sh
sh scripts/check.sh
```

Standard tests use local synthetic fixtures and a fake Codex executor, without paid model calls. The optional browser fixture is skipped unless explicitly enabled. See the validation record for the exact observed result.

## Privacy and license

Never commit `.state/`, `.venv/`, `runs/`, local `config.json`, credentials, real task context, or private chat records. Heuristic context screening is not comprehensive redaction. Current provider rules and account UI govern actual access and usage.

Original code is MIT licensed. Vendored dependencies retain their own MIT notices and pinned manifests. See [third-party notices](THIRD_PARTY_NOTICES.md) and [contributing](CONTRIBUTING.md). AI-assisted development records were used to reconstruct the original local implementation; private conversation records are excluded.
