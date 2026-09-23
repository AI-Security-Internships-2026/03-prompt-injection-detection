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

## Level 2 — Candidate Identification (COMPLETE)

Tested whether an attacker can identify which of 4 victim-selected
synthetic candidates was used, via cache-observation oracle alone,
across all four Section 13 entropy categories. Isolated-probe
methodology: each probe gets its own flush -> victim_populate -> gap
-> single probe cycle, eliminating cross-probe cache contamination
(see note below).

| Category            | N trials | Accuracy | 95% Wilson CI      | p-value (vs 25% chance) |
|----------------------|----------|----------|---------------------|--------------------------|
| Low-entropy          | 30       | 100%     | [88.65%, 100.00%]   | 8.67e-19                 |
| Predictable-prefix   | 30       | 100%     | [88.65%, 100.00%]   | 8.67e-19                 |
| Structured (PIN)     | 30       | 100%     | [88.65%, 100.00%]   | 8.67e-19                 |
| High-entropy (UUID)  | 30       | 100%     | [88.65%, 100.00%]   | 8.67e-19                 |

All confusion matrices fully diagonal (zero misclassifications), all
120-row raw data in results/sglang/candidate_recovery_*_isolated.csv.

### Methodological notes

1. **Cross-probe contamination (caught and fixed).** The first
   predictable-prefix run (non-isolated, `run_candidate_recovery_prefix.py`)
   showed order-dependent `cached_tokens` drift among non-matching probes
   (179/180/181 instead of flat), traced to attacker probes populating
   cache for each other within a trial. Fixed by giving each probe its
   own flush/victim/gap cycle. Result direction did not change, but the
   isolated version is the methodologically sound one and is what is
   reported above.

2. **Tokenization is not length-invariant.** The high-entropy (UUID-like)
   candidates were all 36 characters but tokenized to different
   `prompt_tokens` counts (206, 208, 209) depending on exact hex content.
   Token-count assumptions should not be made from character length alone
   in future experiment design (relevant for Level 3 per-position work).

3. **Signal magnitude varies by category.** Predictable-prefix and PIN
   categories showed a +1 cached_tokens separation between match/non-match.
   UUID category showed a full prompt_tokens-1 separation (much larger
   gap). This suggests separation magnitude scales with how much of the
   candidate is genuinely unique post-divergence, not just candidate-set
   size.

### Conclusion

Cache-state observations reliably distinguish which of 4 same-entropy-
category candidates a victim tenant used, across all tested categories,
with isolated-probe methodology ruling out the ordering confound.  This
confirms Level 2 of the research progression. It does not yet establish
whether components of a single high-entropy secret (not drawn from a
small closed candidate set) can be inferred — that is Level 3.
