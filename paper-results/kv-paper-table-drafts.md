# KV6 Paper Table Drafts (auto-generated)

Freeze commit: `0f538bbfe27d675f6b9999210f5ef8e350fcb8b0`

Generated: 2026-09-28T17:23:39Z

## Table 1. Attack success rate (exact-match PIN reconstruction)

| Mitigation | Trials | Exact matches | Rate | Wilson 95% CI |
|---|---|---|---|---|
| shared | 30 | 28 | 0.933 | [0.787, 0.982] |
| tenant_isolated | 10 | 0 | 0.000 | [0.000, 0.278] |
| disabled | 10 | 0 | 0.000 | [0.000, 0.278] |

## Table 2. TTFT percentiles (ms) - bootstrap 95% CI

| Mitigation | Conc. | TTFT p50 [CI] | TTFT p95 [CI] | TTFT p99 [CI] |
|---|---|---|---|---|
| shared | 1 | 163.0 [162.4, 163.7] | 166.8 [165.9, 167.8] | 166.8 [165.9, 167.8] |
| shared | 10 | 135.3 [134.7, 135.7] | 151.5 [145.3, 163.4] | 182.6 [176.5, 188.7] |
| shared | 25 | 140.2 [138.9, 141.1] | 161.8 [157.6, 164.5] | 249.5 [245.2, 252.3] |
| isolated | 1 | 162.9 [162.6, 163.1] | 166.2 [165.2, 168.2] | 166.2 [165.2, 168.2] |
| isolated | 10 | 134.9 [133.8, 136.2] | 146.5 [143.1, 148.3] | 183.2 [179.3, 189.6] |
| isolated | 25 | 138.9 [137.1, 140.3] | 174.9 [157.6, 188.9] | 246.9 [240.0, 253.2] |
| disabled | 1 | 149.8 [149.2, 150.1] | 152.9 [152.6, 153.2] | 152.9 [152.6, 153.2] |
| disabled | 10 | 141.5 [140.7, 142.3] | 154.8 [151.6, 156.9] | 174.6 [169.2, 180.6] |
| disabled | 25 | 151.6 [151.2, 151.9] | 170.6 [169.1, 172.6] | 241.9 [235.9, 245.8] |

## Table 3. Cache-hit rate - bootstrap 95% CI

| Mitigation | Conc. | Hit rate [CI] |
|---|---|---|
| shared | 1 | 0.950 [0.850, 1.000] |
| shared | 10 | 1.000 [1.000, 1.000] |
| shared | 25 | 1.000 [1.000, 1.000] |
| isolated | 1 | 0.950 [0.850, 1.000] |
| isolated | 10 | 0.955 [0.865, 1.000] |
| isolated | 25 | 0.970 [0.910, 1.000] |
| disabled | 1 | 0.000 [0.000, 0.000] |
| disabled | 10 | 0.000 [0.000, 0.000] |
| disabled | 25 | 0.000 [0.000, 0.000] |

## Table 4. Throughput (req/s) - bootstrap 95% CI

| Mitigation | Conc. | Throughput [CI] |
|---|---|---|
| shared | 1 | 0.36 [0.36, 0.36] |
| shared | 10 | 4.28 [4.28, 4.29] |
| shared | 25 | 10.38 [10.38, 10.38] |
| isolated | 1 | 0.36 [0.36, 0.36] |
| isolated | 10 | 4.30 [4.29, 4.30] |
| isolated | 25 | 10.38 [10.32, 10.44] |
| disabled | 1 | 0.36 [0.36, 0.36] |
| disabled | 10 | 4.26 [4.26, 4.26] |
| disabled | 25 | 10.29 [10.29, 10.30] |

## Table 5. Significance tests (Welch t) + effect size (Cohen d)

| Comparison | Mean A | Mean B | t | df | p | Cohen d |
|---|---|---|---|---|---|---|
| shared vs isolated @ c1 | 163.0 | 162.9 | +0.34 | 2.5 | 0.7373 | +0.27 |
| shared vs disabled @ c1 | 163.0 | 149.8 | +27.10 | 3.8 | 0 | +22.12 |
| shared vs isolated @ c10 | 135.3 | 134.9 | +0.52 | 2.8 | 0.6003 | +0.43 |
| shared vs disabled @ c10 | 135.3 | 141.5 | -11.46 | 3.6 | 0 | -9.36 |
| shared vs isolated @ c25 | 140.2 | 138.9 | +1.13 | 3.6 | 0.2585 | +0.92 |
| shared vs disabled @ c25 | 140.2 | 151.6 | -16.93 | 2.4 | 0 | -13.82 |
