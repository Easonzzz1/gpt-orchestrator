# Measure a workflow before claiming savings

This checklist grew out of discussions about Chat planning, Work/Codex execution,
and agent caching. It is a measurement method, not evidence of savings. The
bundled fixture contains invented numbers. No account inspection or API calls
are performed by the reporting helper.

## Offline usage report

```sh
python3 scripts/usage_report.py examples/usage.synthetic.jsonl
```

Supply UTF-8 JSONL with one final API usage object per request, wrapped in
`{"usage": {...}}`. Responses fields (`input_tokens`, `output_tokens`,
`input_tokens_details`) and Chat Completions fields (`prompt_tokens`,
`completion_tokens`, `prompt_tokens_details`) are supported. Optional
`latency_ms` is a manually measured non-negative duration. Read/write cache
counts are optional. Missing counts remain unknown; an overall cache ratio is
reported only when every record supplies cached tokens. The ratio is weighted
by input tokens, not the average of per-request percentages. Do not include
streaming snapshots and their final total as separate requests.

The synthetic example yields 30,000 input tokens, 1,500 output tokens and 12,000
cached tokens: 40% of input. **The total input remains 30,000.** Read-cache reuse
is not a reduction of the provider's reported total input. Output reasoning
tokens are not added again to the output total. Cache-write counts are reported
separately; absence does not mean zero writes.

The helper emits no prices, invoice estimate, subscription conversion, model
text, request IDs or private file paths. Current billing can depend on model,
cache writes/lifetimes and other terms. Compare actual billing separately.
API usage cannot establish ChatGPT subscription quota savings. Relevant current
field definitions: [OpenAI prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
(checked 2026-10-21). Recheck provider definitions when schemas change.

## A fair comparison

1. Use the same public/synthetic task, starting files and observable acceptance
   criteria for a direct executor baseline and a Chat → executor → review run.
2. Record every planning, execution, retry and review call, including failures;
   record model/version, settings, elapsed time, tool calls and human work
   separately. A smaller executor context can still mean more total calls.
3. Keep warm-cache and cold-cache conditions separate. Repeat trials with task
   order balanced, and retain failures rather than selecting only fast runs.
4. Compare completion quality first, then totals and distribution of latency.
   State sample size, unknown measurements and which product surfaces expose
   usage. Do not substitute prompt character count for tokens.
5. Review any raw exports locally and retain only needed usage fields before
   sharing. Do not publish prompts, responses, session IDs or account details.

The report does not measure the orchestration CLI automatically. Work handoffs
remain manual, and provider UI limits remain authoritative. Future benchmarks
must publish their method and actual observations separately from this template.
