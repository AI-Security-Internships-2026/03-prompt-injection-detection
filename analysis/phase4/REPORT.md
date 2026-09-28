# Phase 4 Report — Information Recovery Feasibility

## Objective
Determine whether cross-tenant timing leakage (established in Phase 3,
d=0.831) translates into practical secret-recovery capability.

## Method
Built victim/attacker separation harness, 4 entropy-category secret
generators, calibrated hit/miss classifier with majority voting across
[1,3,5,10] trial counts, tested across 5 secrets per category (20 total).

## Key finding: secret position within template determines signal existence
- Secret-at-end (dominated by long shared prefix): NO measurable timing
  gap (before/after both ~71-74ms) - the shared prefix's caching benefit
  swamps any secret-specific signal.
- Secret-at-start (secret determines prefix divergence point): a real
  but SMALL gap observed in single-example testing (82.3ms -> 72.3ms).

## Ablation result

Across 20 secrets (5 per category) x 4 trial counts (1,3,5,10), mean
classification confidence:

| Category | Trials | Before | After |
|---|---|---|---|
| high_entropy | 1 | 0.00 | 0.00 |
| high_entropy | 3 | 0.00 | 0.07 |
| high_entropy | 5 | 0.04 | 0.16 |
| high_entropy | 10 | 0.00 | 0.10 |
| low_entropy | 1 | 0.20 | 0.40 |
| low_entropy | 3 | 0.00 | 0.00 |
| low_entropy | 5 | 0.00 | 0.00 |
| low_entropy | 10 | 0.04 | 0.02 |
| predictable_prefix | 1 | 0.00 | 0.00 |
| predictable_prefix | 3 | 0.00 | 0.00 |
| predictable_prefix | 5 | 0.04 | 0.04 |
| predictable_prefix | 10 | 0.00 | 0.20 |
| structured | 1 | 0.00 | 0.20 |
| structured | 3 | 0.00 | 0.13 |
| structured | 5 | 0.08 | 0.00 |
| structured | 10 | 0.12 | 0.02 |

No category shows a consistent before->after confidence increase. Several
cells show after < before, inconsistent with any real caching signal.
All values are small and scattered near zero across every condition,
indicating the classifier's decisions are dominated by measurement noise
rather than true cache-state signal at this template scale and trial count.

## Conclusion
Cross-tenant cache-timing leakage is real and statistically overwhelming
in aggregate (Phase 2: d=39.7, p=2.26e-259; Phase 3: d=0.831, p<0.00001),
but does NOT translate into reliable single-secret classification at the
trial counts (1-10) and template scale tested here. No category shows a
consistent before/after confidence increase, including low_entropy - the
theoretically easiest case. Root cause: at this template/prefix scale,
the true hit/miss latency gap is comparable to or smaller than trial-to-
trial measurement noise, even after addressing two confounds discovered
during development (self-cache contamination, prompt-length mismatch,
and secret-position-within-template).

This bounds the practical threat model: PROMPTPEEK-style extraction is
statistically real but requires either (a) much larger prefix-
differentiating content per probe, or (b) substantially more repeated
trials than tested here (10), to overcome the noise floor for short
embedded secrets. Both scaling requirements have direct cost implications
for a real attacker (more queries = more time, more detectable traffic),
making this a genuine bound on attack feasibility rather than an
implementation gap.

## Limitations
- No adaptive search/extraction algorithm was implemented (out of scope,
  see experiments/phase4/README.md)
- Single hardware/model configuration (DGX Spark, DeepSeek-R1-Distill-
  Llama-8B, vLLM 0.26.0)
- Threshold calibration approach may not be optimal
