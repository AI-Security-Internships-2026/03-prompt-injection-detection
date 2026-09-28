# KV5 — Mitigation Trade-off (Security vs. Performance)

**Status:** Complete. Addresses KV5 issue #26.

## What this report contains

- `results/kv5_v2/kv5_tradeoff.csv` — full joined table (9 rows: 3 mitigations x 3 concurrency levels)
- `results/kv5_v2/kv5_pareto.png` — Pareto figure (attack success vs. p99 TTFT)
- `experiments/kv5_perf_load.py` — the runner (V3: TTFT and total-latency measured separately; deterministic prompt reuse to exercise the cache)
- `analysis/compute_kv5_tradeoff.py` — the analysis script that generates both files above directly from the raw CSVs

## Key results

| Mitigation | Attack success | Cache hit rate | p99 TTFT (c=25) |
|---|---|---|---|
| shared (baseline) | **0.9333** (28/30) | 0.95-1.00 | 249 ms |
| tenant_isolated | **0.0000** | 0.95-0.97 | 247 ms |
| disabled | **0.0000** | 0.00 | 242 ms |

- **Tenant isolation blocks the attack with no measurable TTFT cost** (247 ms vs 249 ms at c=25).
- **Cache-disabling also blocks the attack** but eliminates all same-tenant reuse (hit rate 0.00).
- **TTFT is clearly separated from full generation latency** (135-163 ms TTFT vs 2187-2639 ms full latency across conditions).

## Baseline provenance

The 0.9333 attack-success number for the `shared` mitigation is COMPUTED from
`results/sglang/kv2/pin_chained_shared.csv` (the KV2 vulnerable baseline) by
applying the original attacker's argmax-on-cached_tokens reconstruction per
trial, then comparing to `ground_truth_pin`. 28/30 trials reconstruct the PIN
exactly. The 2 failures are both leading-zero cases (`78922` inferred as
`078922`, `50033` inferred as `050033`) — a real, documented failure mode
rather than a bug.

tenant_isolated and disabled attack success is computed from the KV5
`security_*.csv` files as per-trial exact-match on `position_correct`.

## Reproducibility

- Runner: `experiments/kv5_perf_load.py` (V3)
- Analysis: `analysis/compute_kv5_tradeoff.py` (V3)
- Server: SGLang, Qwen2.5-7B-Instruct, port 30010, `--mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096`
- Cache-disabled mode adds `--disable-radix-cache` to the launch
- 3 repeats per (mitigation x concurrency) cell
- All CSVs, summaries, and master log preserved under `results/kv5_v2/`

## What is NOT in this report

- DeepSeek-side KV5 rerun (only Qwen2.5-7B-Instruct measured)
- Baseline/paper-figure polish (annotations at c=25 overlap in the current PNG)

## Native isolation

SGLang's `extra_key` (a.k.a. `cache_salt`) is used as an existing native
per-request field, not invented by this project. `--disable-radix-cache` is
likewise a native launch flag.
