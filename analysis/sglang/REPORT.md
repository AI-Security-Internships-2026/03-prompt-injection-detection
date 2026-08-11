# SGLang Cross-Tenant KV/Prefix-Cache Experiment — Session Report

**Date:** 2026-08-11
**Model:** deepseek-ai/DeepSeek-R1-Distill-Llama-8B
**SGLang version:** 0.5.17
**Hardware:** NVIDIA GB10 (DGX Spark), CUDA 13.0, sm_121

## Research Question
Can a controlled multi-tenant SGLang deployment produce measurable cross-tenant
information leakage through shared prefix-cache behavior, and how does this
compare to prior vLLM findings (Phase 2 d≈39.7, Phase 3 d≈0.831)?

## Stage 1 — Installation
Clean pip install in isolated conda env (`sglang-exp`), no source-build
failures. One minor non-blocking pip-check warning (`nvidia-cusparselt-cu13`
platform tag). CUDA kernels JIT-compiled on first run (~3-4 min), cached
thereafter.

## Stage 2 — Single-Tenant Validation

**Short prefix (~78 tokens):**
- fresh_warm vs repeat: Cohen's d=0.8394, p=0.0062 (significant)
- repeat vs modified: Cohen's d=-0.0155, p=0.970 (no signal)

**Long prefix (~1212 tokens):**
- Cold-start latency scaled correctly with prefix length (0.425s vs 0.236s)
- repeat vs modified: Cohen's d=0.4567, p=0.345 (not significant; modified
  suffix only diverged by ~1 cached token out of 1211 - insufficient
  divergence, confounds this specific test)

**Conclusion:** Cold-vs-warm cache state produces a clear, significant timing
signal. Degree-of-partial-match has NOT yet produced a resolvable signal in
either prompt length tested — this requires a better-designed ablation
(larger, controlled suffix divergence) in a future session.

## Stage 3 — Cross-Tenant Timing Leakage

### Design note: confound found and fixed
Initial version (v1) had attacker probes self-priming the shared cache across
repeated trials within Condition A, making Condition A and B indistinguishable
(both saturated near-full cache hit). Fixed in v2 by flushing the cache
(`/flush_cache`) before every individual trial, isolating each measurement.

### Result (v2, flush-isolated, n=15 per condition)

**Cache-hit leakage (via `meta_info.cached_tokens`):**
- Condition A (no victim activity): cached_tokens = 0/188, all 15 trials
- Condition B (after victim activity): cached_tokens = 181/188, all 15 trials
- **100% separable, deterministic signal.** An attacker with access to this
  field can trivially detect that another tenant recently used an
  overlapping prefix.

**Wall-clock latency:**
- A: mean=0.09637s, std=0.00420s
- B: mean=0.14278s, std=0.00657s
- Cohen's d = -8.4198, Mann-Whitney p = 3.39e-6 (highly significant)

### Open question — direction anomaly
Latency is HIGHER in Condition B (post-victim, high cache hit) than Condition A
(cold), which is the opposite of a naive cache-speedup model. The effect size
is large and fully consistent across all 15 trials, so this is not noise.
Leading hypothesis (NOT YET VERIFIED): back-to-back request scheduling/queueing
overhead when the victim's request and attacker's probe hit the server in close
succession, possibly dominating over prefill-compute savings from caching.
This needs isolation (e.g., inserting a controlled idle gap between victim and
attacker requests) before drawing conclusions about the mechanism.

## Comparison to vLLM Results
| Experiment | vLLM | SGLang |
|---|---|---|
| Phase 2 (cache-related timing) | d≈39.7, p≈2.26e-259 | d=0.839 (short prefix, fresh vs repeat) |
| Phase 3 (cross-tenant timing) | d≈0.831, p<0.00001 | d=-8.42, p=3.39e-6 (direction differs - see above) |
| Cache-hit field leakage | Not tested in vLLM Phase 2/3/4 | 100% deterministic (novel to this stage) |

Direct magnitude comparison between vLLM Phase 3 and SGLang cross-tenant d
should be treated cautiously — different measurement design (SGLang v2 is
flush-isolated per-trial; vLLM Phase 3 methodology should be re-checked for
equivalent isolation before treating these as comparable numbers).

## Status / Next Steps
- Ablations (prefix length, secret position, repetition count): not started
- Information-recovery stage: not started (correctly deferred - no reliable
  oracle characterized yet per Section 14 requirement)
- Priority for next session: (1) isolate the latency-direction anomaly,
  (2) redesign modified-prefix test with larger controlled divergence,
  (3) begin ablations only after (1) and (2) are resolved
