# Validation record

Revalidated 2026-10-21 (Asia/Hong_Kong), macOS and Python 3.9.6, after restoring the implementation from development records.

- `sh scripts/check.sh`: 30 tests discovered; 29 passed, one optional real-browser fixture skipped. Twelve Python files passed static parse/compile checks; shell syntax checks passed.
- Tests cover routing, explicit overrides, sensitive-context dispatch refusal, path/byte boundaries, packet validation, call ceilings, unknown submission state, failed-check acceptance blocking, review invalidation, and the complete state flow with a fake executor.
- Pinned selected Superpowers skill sources and chatgpt-use reference files were downloaded again at the exact locked commits. Their licenses and file hashes are retained.

No real ChatGPT conversation, real Codex model execution, Work dispatch, token-savings benchmark, or browser round-trip was run in this restoration. A historical browser-launch failure is not a fresh browser test result. Use manual handoff as the documented starting path.

Maintenance validation, 2026-10-21: after adding the usage helper, 37 tests were discovered, 36 passed and the same optional browser fixture was skipped. Fourteen Python files passed static parse/compile checks. The seven new tests cover schema boundaries, unknown cache values, weighted ratios, synthetic totals and no partial/error-data output. This does not establish real savings.
