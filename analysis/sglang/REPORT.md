# SGLang Cross-Tenant KV/Prefix-Cache Experiment — Report

**Model:** deepseek-ai/DeepSeek-R1-Distill-Llama-8B
**SGLang version:** 0.5.17
**Hardware:** NVIDIA GB10 (DGX Spark), CUDA 13.0, sm_121

## Research Question
Can a controlled multi-tenant SGLang deployment produce measurable cross-tenant
information leakage through shared prefix-cache behavior, and how does this
compare to prior vLLM findings (Phase 2 d≈39.7, Phase 3 d≈0.831)?

## Stage 1 — Installation
Clean pip install in isolated conda env (`sglang-exp`). CUDA kernels JIT-compiled
on first run, cached thereafter. No source-build failures.

## Stage 2 — Single-Tenant Validation

**Short prefix (~78 tokens):** fresh_warm vs repeat d=0.8394, p=0.0062 (significant).
repeat vs modified d=-0.0155, p=0.970 (no signal — later diagnosed as a design
flaw, not a true negative; see Stage 2c below).

**Long prefix (~1212 tokens):** cold-start latency scaled correctly with prefix
length. repeat vs modified d=0.4567, p=0.345 (not significant — same design
flaw, modified suffix diverged by only ~1 cached token out of 1211).

**Stage 2c — corrected partial-cache-hit test (this session):**
Root cause of the earlier null results: insufficient divergence between
"repeat" and "modified" conditions. Redesigned with substantial suffix
divergence (~265/310 vs 299/300 cached tokens) and controlled for scheduler
contention (see Stage 3 gap finding below) via a 1s idle gap.

Four design iterations were needed to get a valid test (documented in commit
history for transparency — v1 self-primed, v2 accidentally equalized both
conditions, v3 lacked the contention control, v4 is the valid result):

- repeat: mean=0.083s, cached_tokens=299/300 (n=10, consistent)
- modified: mean=0.088s, cached_tokens=265/310 (n=10, consistent)
- Cohen's d=-0.7342, Mann-Whitney p=0.0173 (significant)
- Robust to outlier removal: d=-0.7014, p=0.0305

**Conclusion:** Partial cache match DOES produce a statistically significant
timing signal on SGLang, when divergence is substantial and contention is
controlled. The original Stage 2 null results were a design artifact, not
evidence of no signal.

## Stage 3 — Cross-Tenant Timing Leakage

### v1 → v2: confound found and fixed
v1 had attacker probes self-priming the cache across trials, making Condition
A and B indistinguishable. Fixed in v2 via per-trial `/flush_cache`.

### v2 Result — cache-hit field leakage (n=15 per condition)
- Condition A (no victim activity): cached_tokens=0/188, all 15 trials
- Condition B (after victim activity): cached_tokens=181/188, all 15 trials
- **100% deterministic, binary signal.** Attacker access to `meta_info.cached_tokens`
  trivially reveals recent cross-tenant cache activity.

### v2 wall-clock anomaly, and its resolution (this session)
v2 showed B slower than A (d=-8.42, p=3.4e-6) — opposite of naive cache-speedup
expectation. Investigated via an idle-gap sweep (0s/1s/3s/5s) between victim
activity and attacker probe:

| Gap | A mean | B mean | Direction |
|---|---|---|---|
| 0s | 0.124s | 0.144s | B > A (anomaly) |
| 1s | 0.103s | 0.083s | B < A (expected) |
| 3s | 0.099s | 0.082s | B < A (expected) |
| 5s | 0.097s | 0.081s | B < A (expected) |

All non-zero gaps: d≈3.4–4.0, p≈0.0002 (highly significant, consistent direction).

**Conclusion:** The v2 anomaly was caused by request-scheduling contention from
back-to-back requests, not a property of the cache mechanism. With even 1s
separation, latency behaves as a naive cache-hit model predicts. This fully
resolves the previously open question.

## Comparison to vLLM Results
| Experiment | vLLM | SGLang |
|---|---|---|
| Cache-related timing (cold vs warm) | d≈39.7, p≈2.26e-259 | d=0.839 (short prefix) |
| Cross-tenant timing (contention-controlled) | d≈0.831, p<0.00001 | d≈3.4–4.0, p≈0.0002 (gap≥1s) |
| Cache-hit field leakage | Not tested | 100% deterministic (novel to SGLang stage) |
| Partial-match timing | Not cleanly established (Phase 4 negative result) | d=-0.73, p=0.017 (confirmed, contention-controlled) |

Note: vLLM Phase 3/4 methodology should be re-checked for equivalent request-spacing
controls before treating magnitude comparisons as fully apples-to-apples — the
SGLang contention finding suggests request timing/spacing is a variable that
matters and may not have been controlled identically across the two codebases.

## Status / Next Steps
- ✅ Cross-tenant leakage: confirmed via two independent signals (cache-hit field,
  contention-controlled timing)
- ✅ Latency-direction anomaly: resolved (scheduler contention)
- ✅ Partial-match timing signal: confirmed (contention-controlled)
- ⬜ Ablations (prefix length sweep, secret position, repetition count trade-off):
  not started
- ⬜ Information-recovery stage: correctly still deferred — a reliable oracle now
  exists (this stage's findings), so this is unblocked for a future session
- ⬜ Full vLLM methodology audit for request-spacing equivalence: recommended
  before final cross-framework comparison numbers are reported
