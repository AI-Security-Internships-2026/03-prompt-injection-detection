

# KV Research Questions (Frozen — KV1)

**Authors:** Ehsan Ullah Jamshaid
**Last Updated:** 2026-09-09
**Status:** DRAFT for supervisor sign-off. Assumes the threat model and success levels in `docs/kv-threat-model.md`.

Each RQ below carries: final wording, a testable hypothesis, and its current evidentiary status (existing Week-9/11 pilot data vs. requires new KV3–KV5 experiment, gated on sign-off).

---

## RQ1 — Leakage Conditions

**Wording.** Under what configurations and workloads does shared KV/prefix caching create a measurable cross-tenant side channel (Level 1, presence detection)?

**Hypothesis.** H1: With default (unmitigated) shared-cache configuration and a ≥1s idle gap between victim and attacker requests (to remove scheduling-contention confounds), cross-tenant cache reuse is detectable above chance via at least one of (a) explicit cache-telemetry fields where exposed by the framework, or (b) request latency, in both SGLang and vLLM.

**Status.** Partially supported by existing Week-9/11 SGLang data (`cached_tokens`: 0/188 vs 181/188 deterministic; timing d≈3.4–4.0). vLLM Phase 2 timing-oracle result (d≈39.7) is existing pilot evidence for the timing arm only. Not yet frozen as final-paper evidence per the KV1 gate — requires KV2 reproducibility pass before re-citing as final.

---

## RQ2 — Practical Exploitability

**Wording.** Under what conditions can the side channel progress from Level 1 (presence detection) to Level 2 (candidate identification) or Level 4 (full multi-step information reconstruction)?

**Hypothesis.** H2: Given a query budget proportional to candidate-set size (Level 2) or secret length × alphabet size (Level 4), and a framework whose cache-matching is deterministic and token/prefix-granular, an attacker chaining on its own prior guesses achieves reconstruction accuracy significantly above the corresponding chance baseline (1/k for Level 2; 1/alphabet^length for Level 4).

**Status.** Existing SGLang pilot data supports H2 at Level 2 (100% across 4 entropy categories, N=30 each) and Level 4 (100% full 6-digit PIN, N=30, chance ≈ 1e-6). These are historical results and are **not** treated as final paper evidence until KV2 reproducibility + supervisor sign-off (per the Constraints section of this issue).

---

## RQ3 — Cross-Framework Behavior

**Wording.** How do SGLang and vLLM differ in leakage observability (which signals are exposed), exploitability (whether Level 2/4 is reachable and at what query cost), and failure modes, under aligned experimental conditions (same model, same secret structure, same idle-gap protocol)?

**Hypothesis.** H3: The two frameworks expose different explicit telemetry (SGLang: `cached_tokens` in response metadata; vLLM: no equivalent field in the tested version, timing-only) but both remain exploitable via timing under aligned conditions, with different magnitude/noise characteristics (different Cohen's d, different query-budget-to-accuracy curve).

**Status.** Not yet frozen — vLLM Phase 0–4 and SGLang tracks were run as separate efforts with related but not identical protocols. KV3 (gated) must align the two protocols (same idle-gap, same secret structure, same repetitions) before any cross-framework claim is made in the paper. This is the primary reason RQ3 cannot be answered from existing data alone.

---

## RQ4 — Robustness and Detectability

**Wording.** How robust are attack patterns under realistic noise/adaptation (e.g. background traffic, jitter, an attacker who varies pacing), and can malicious probing be detected without unacceptable false positives on legitimate traffic?

**Hypothesis.**

**H4a (robustness):** Attack reliability does **not** degrade gradually with competing load but drops sharply upon the introduction of *any* background tenant activity, remaining largely stable from 2 to 8 concurrent tenants (threshold degradation pattern, not gradual). The specific threshold and reliability floor require empirical characterization under realistic GPU contention with a background load generator instrumented for occupancy.

**H4b (detectability):** A lightweight detector based on inter-request prefix-match ratio and mutation density separates attack traffic from legitimate same-tenant traffic with high precision/recall and low false-positive rate, and continues to do so under the RQ5 mitigation (since it does not depend on the mitigated signal).

**Status.**

**H4a** is partially supported by our preliminary load-test data (Studies 1–4) showing threshold degradation:

- **Study 1 (preliminary):** Ambient ($d=1.126$, SD=0.269) vs. Loaded ($d=0.213$, SD=0.096); Welch's $t=7.147$, $p=0.00083$

- **Study 2 (load-level):**
  - 0 workers: $d=0.779$ (SD=0.124)
  - 2 workers: $d=0.211$ (SD=0.198)
  - 4 workers: $d=0.140$ (SD=0.225)
  - 8 workers: $d=0.082$ (SD=0.209)
  - 0 vs. 2: $t=8.412$, $p<0.00001$
  - 2 vs. 4: $t=0.820$, $p=0.421$
  - 4 vs. 8: $t=0.652$, $p=0.521$
  - Fraction of runs with $d<0$ (reversed signal) climbs with load: 0/12 → 2/12 → 4/12 → 6/12

- **Reproducibility caveat:** The 0-worker (ambient) baseline is **not** independently reproducible under uncontrolled shared-GPU conditions. Independent re-run by the second author produced materially different $d=0.237$ (SD=0.071) vs. primary $d=0.779$ (Welch $t=13.10$, $p<0.00001$). Root cause: unrelated VLLM engine process (~84GB resident memory, SM utilization 17–87%) active during 0-worker trials. The 2/4/8-worker comparisons are unaffected since added synthetic load dominates uncontrolled background. A clean re-measurement requires exclusive GPU allocation or per-trial utilization logging as a covariate — this is a **KV4 (gated)** experiment.

- **Study 3 (request size disentanglement):**
  - 1 worker/16 tok: $d=0.057$ (SD=0.711)
  - 1 worker/128 tok: $d=0.085$ (SD=0.121)
  - 2 workers/4 tok: $d=0.109$ (SD=0.073)
  - The 1-worker/small-request configuration shows 6–10× the variance of others, suggesting request concurrency depth or timing pattern governs reliability instability.

- **Study 4 (occupancy correlation):**
  - Pearson correlation across all 20 trials: $r=-0.366$
  - Independent replication: $r=-0.276$
  - Pooled ($n=40$): $r=-0.302$
  - Weak-to-moderate negative correlation — too small to explain reliability differences.
  - Multiple configurations at near-identical occupancy (0.97–1.00) show dramatically different reliability (e.g., 1-worker/16-tok SD=0.75 vs. 2-worker/4-tok SD=0.02–0.06), indicating occupancy fraction metric cannot distinguish the interference regimes that actually drive attack reliability.

**H4b** is supported by existing SGLang pilot data (P/R/F1 = 1.000, FPR = 0.000 against 3 legitimate-traffic baselines; same profile under cache-salt mitigation).

**Operational definitions for H4a:**
- Background load generator: `background_load.py` / `background_load_v3.py` — configurable number of independent synthetic worker processes issuing requests to the shared SGLang backend at a configurable maximum token length.
- Occupancy: fraction of attacker probe wall-clock duration that overlapped with at least one logged background-worker request interval, computed from independently logged start/end timestamps (not from `nvidia-smi` utilization percentage).

---

## RQ5 — Mitigation Trade-Off

**Wording.** How effectively do tenant isolation/salting, cache disabling, and detector-based mitigation reduce attack success, and what latency/throughput/cache-efficiency costs do they impose, relative to each other and to published selective-isolation defenses (PrefixWall, SafeKV)?

**Hypothesis.** H5: Native per-tenant cache-salt isolation reduces Level 4 attack accuracy to at or near the chance baseline while preserving legitimate same-tenant cache-hit rate and latency indistinguishable from the unmitigated baseline; full cache-disabling achieves the same security reduction but at the cost of eliminating all same-tenant reuse (0% hit rate) rather than only cross-tenant reuse.

**Status.** Supported by existing SGLang pilot data (salted: 0% Level-4 accuracy, N=30, `cached_tokens`=0 on all 1,800 rows, d=76.5 vs. baseline; legitimate-traffic hit rate 98.3% in both salted and unsalted conditions; disable-radix: 0% hit rate). Not yet extended to vLLM (KV5, gated) or benchmarked head-to-head against PrefixWall/SafeKV's own reported costs beyond the qualitative table already in the paper draft — a quantitative reproduction of either published defense is out of scope for Paper 1 unless the supervisor adds it.

---

## Removed / Not Proposed

No RQ was removed at this pass — all five track directly onto sections already present in the current paper draft (`main.tex`, §"Research Questions"). RQ4 was significantly updated to incorporate our background-load findings from Studies 1–4, the reproducibility caveat, request-size disentanglement, and occupancy correlation limitations. If the supervisor wants any RQ narrowed or cut, we will record the reason here before KV2 starts.

---

## Definition-of-Done Checklist (This Document)

- [x] Final RQ wording (RQ1–RQ5)
- [x] Testable hypothesis per RQ where applicable
- [x] No RQ retained that current or feasible experiments cannot answer — RQ3/RQ4a explicitly flagged as requiring new (gated) experiments, not just re-analysis of existing data
- [x] RQ4 updated to reflect threshold degradation pattern (not gradual), reproducibility caveat, request-size findings, and occupancy correlation limitations from Studies 1–4