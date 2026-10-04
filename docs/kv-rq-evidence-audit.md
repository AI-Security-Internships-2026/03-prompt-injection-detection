# KV7 — RQ-to-Evidence Audit

**Status:** Final submission package.
**Frozen baseline:** paper-kv-results-freeze-v2 (KV6).
**Freeze commit:** 0f538bbfe27d675f6b9999210f5ef8e350fcb8b0
**Audit date:** 2026-10-04

## Status key

- **KV6-VERIFIED** — number traces to paper-results/paper_numbers_kv.json
- **PRIOR-EVIDENCE** — number computed before KV6 from KV2/KV4 raw CSVs; manuscript labels it accordingly. Raw CSV is in paper-results/raw/
- **MISSING** — no source; must be removed from manuscript

## RQ1 — Leakage Conditions

| Sub-claim | Section | Evidence source | Status |
|-----------|---------|-----------------|--------|
| cached_tokens distinguishes victim-present from victim-absent | Baseline Results Table 1 | raw/kv2/pin_chained_shared.csv | PRIOR-EVIDENCE |
| Timing gap with >=1s idle: d ~ 3.4-4.0, p ~ 2e-4 | Baseline Results Table 1 | results/sglang/cross_tenant_*.csv | PRIOR-EVIDENCE |
| Partial-match timing: d=-0.734, p=0.017 | Baseline Results Table 1 | results/sglang/cross_tenant_*.csv | PRIOR-EVIDENCE |

Verdict: supported; all three prior-evidence.

## RQ2 — Practical Exploitability

| Sub-claim | Section | Evidence source | Status |
|-----------|---------|-----------------|--------|
| Candidate ID, 4 entropy categories, 100% (N=30 each) | Info-Recovery Table 2 | raw/kv2/pin_chained_shared.csv variants | PRIOR-EVIDENCE |
| Full 6-digit PIN reconstruction | Info-Recovery Table 2 | KV6 recomputes as 28/30 = 93.3% [78.7, 98.2] | REPLACED (was 100%) |
| Chained probing uses attacker-recovered digits only | Method 5.4 | code audit | structural |

Verdict: supported; 100% must become 93.3% with footnote.

## RQ3 — Cross-Framework Behavior

| Sub-claim | Section | Evidence source | Status |
|-----------|---------|-----------------|--------|
| vLLM 0.27.1 DeepSeek shared: 97.8% per-digit | Cross-Tenant Leakage | results/phase4/kv3_v3/level3_vllm_shared_deepseek.csv | PRIOR-EVIDENCE |
| vLLM 0.27.1 DeepSeek disabled: 12.2% | Same | level3_vllm_disabled_deepseek.csv | PRIOR-EVIDENCE |
| vLLM Qwen: 0.0% in both modes | Same | level3_vllm_*_qwen.csv | PRIOR-EVIDENCE |
| SGLang 0.5.17 near chance in all 4 conditions | Same | results/sglang/kv2/candidate_*.csv | PRIOR-EVIDENCE |

Verdict: supported.

## RQ4 — Robustness and Detectability

| Sub-claim | Section | Evidence source | Status |
|-----------|---------|-----------------|--------|
| Detector P/R/F1=1.000, FPR=0.000 | Detection Method | results/sglang/mitigation/detection_threshold_sweep.csv | PRIOR-EVIDENCE |
| Detection latency = 10 requests, all 30 trials | Same | detection_latency.csv | PRIOR-EVIDENCE |
| Rejected signal: rate/burst | Same | negative result preserved | structural |
| Background load threshold degradation | Discussion | Issue #18 marked unreplicated | EXCLUDED |

Verdict: supported; detector numbers are prior evidence, must be footnoted.

## RQ5 — Mitigation Trade-Off

| Sub-claim | Section | Evidence source | Status |
|-----------|---------|-----------------|--------|
| Attack success: shared 0.933, isolated 0.000, disabled 0.000 | Mitigation Eval | paper_numbers_kv.json kv5.attack_success | KV6-VERIFIED |
| TTFT p50/p95/p99 for 3 mitigations x 3 conc | Performance | paper_numbers_kv.json kv5.perf | KV6-VERIFIED |
| Cache-hit rate shared 0.95-1.00, isolated 0.95-0.97, disabled 0.00 | Same | paper_numbers_kv.json | KV6-VERIFIED |
| Throughput 0.36/4.28/10.38 req/s | Same | paper_numbers_kv.json | KV6-VERIFIED |
| Welch t: shared-vs-isolated p>0.25, shared-vs-disabled p~0 | Mitigation Eval | paper_numbers_kv.json kv5.significance_tests | KV6-VERIFIED |
| Legit-traffic hit rate | Performance | KV6 recomputes as 95-100% [85,100] at c1, 100% at c10/c25 | REPLACED (was 98.3%) |
| N=1800 cached_tokens=0 under mitigation | Mitigation Eval | raw/kv2/pin_chained_isolated.csv | PRIOR-EVIDENCE |
| Cohen d=76.5, p<10^-300 | Same | Same | PRIOR-EVIDENCE |

Verdict: supported. Legit hit rate becomes 95-100%.

## Every in-text quantitative claim: summary

- Abstract: 6 claims — 1 KV6-VERIFIED, 4 PRIOR-EVIDENCE, 1 replaced
- Intro/Contributions: 3 — 0, 3, 0
- Baseline Table 1: 5 — 0, 5, 0
- Info-Recovery Table 2: 6 — 0, 5, 1 replaced
- Detection Method: 4 — 0, 4, 0
- Mitigation Table 3: 8 — 4, 4, 0
- Performance Table 4/5: 12 — 8, 4, 0
- Comparison table: 5 — 0, 5, 0
- Discussion/Limitations: 3 — 0, 3, 0
- TOTAL: 52 — 13 KV6-VERIFIED, 37 PRIOR-EVIDENCE, 2 replaced

Zero MISSING after the two corrections.

## Non-quantitative claims

All 4 "X is important" statements are either supported by a quantitative row above, or downgraded to Discussion/Future Work. Reviewed; all supported.
