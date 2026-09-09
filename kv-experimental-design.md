
# KV Experimental Design (Frozen — KV1)

**Authors:** Ehsan Ullah Jamshaid
**Last Updated:** 2026-09-09
**Status:** DRAFT for supervisor sign-off. Depends on `docs/kv-threat-model.md` and `docs/kv-research-questions.md`.

---

## 1. Operational Definition of "Practical Exploitability"

We do not use "exploitable" qualitatively anywhere in the paper. Every claim of exploitability must cite which of the following metrics were measured and at which of the four attack-success levels (Level 1–4, per the threat model doc):

| Metric | Applies to level(s) | Notes |
|---|---|---|
| Attack success rate | 1–4 | Binary detection accuracy (L1); top-1 accuracy (L2); per-position and full-secret exact-match accuracy (L3/L4) |
| Candidate-identification accuracy / rank | 2 | Report full confusion behavior when accuracy < 100%, not just top-1 |
| Full-secret reconstruction success | 4 | Exact match against ground truth, computed post hoc — never used to steer probing |
| Number of attacker queries | 1–4 | Report as a distribution (mean/median, not just a single number) across trials |
| Time-to-inference / recovery | 1–4 | Wall-clock, reported separately from query count since per-query latency varies by condition |
| Candidate-space size | 2 | k for candidate ID; report per entropy category as already done for L2 |
| Amount of attacker prior knowledge | 1–4 | State explicitly per experiment: exact candidate set (L2) vs. structure-only, e.g. "6 numeric digits" (L4) |
| Robustness to timing noise/contention | 1, 4 | Required for RQ4/H4a — measured via background load generator (Studies 1–4), with occupancy instrumentation |
| Victim/attacker separation assumptions | all | Restate the threat-model non-goals per experiment; flag any experiment that relaxes them |
| False-positive/false-negative rate | detection only | Required whenever a detector is evaluated (RQ4/H4b); report against ≥3 legitimate-traffic baselines, not one |

**Level assignment rule.** A result may only be reported at the highest level for which its metric set is complete (e.g. a candidate-ID result cannot be described as "reconstruction" even at 100% accuracy, because the candidate set was attacker-known). This rule is what keeps L1/L2/L4 from blurring together in the write-up, which was a specific reviewer concern.

**Operational definitions for background-load experiments (RQ4/H4a):**

| Metric | Definition |
|---|---|
| Attack reliability (primary) | Paired Cohen's $d$ for the cross-tenant timing signal (Section 5.2 of paper) |
| Occupancy fraction | For each attacker probe interval, the fraction of its wall-clock duration that overlapped with at least one logged background-worker request interval, averaged across all probes in a run. Computed from independently logged start/end timestamps, not from `nvidia-smi` utilization percentage. |
| Threshold degradation | Reliability does not degrade gradually with tenant count but drops sharply upon introduction of *any* competing load, remaining largely stable thereafter. Statistically: Welch's $t$-test shows significant difference 0 vs. 2 workers ($p<0.00001$); no significant difference 2 vs. 4 ($p=0.421$) or 4 vs. 8 ($p=0.521$). |
| Baseline instability | The 0-worker (ambient) condition is not a stable reference point on a shared GPU; any single ambient measurement should be treated as one draw from a variable distribution, not a fixed ground truth. Independent replication produced materially different $d$ values ($d=0.779$ vs. $d=0.237$) due to uncontrolled background GPU activity. |
| Request-size effect | 1-worker/small-request configuration shows 6–10× the variance of other configurations ($d=0.057$, SD=0.711 vs. $d=0.085$, SD=0.121 for 1-worker/large-request), suggesting request concurrency depth or timing pattern governs reliability instability. |
| Occupancy correlation | Pearson $r \approx -0.3$ between measured occupancy and paired $d$ — weak-to-moderate negative correlation; saturates near 1.0 for nearly all non-zero load configurations, indicating it does not capture the mechanism driving instability. |

---

## 2. Novelty and Related-Work Freeze

**Already established by prior work (not our contribution):**
- Cross-tenant KV/prefix-cache reuse as a timing/telemetry side channel in shared LLM serving generally, and specifically on SGLang's radix-tree cache — PROMPTPEEK / "I know what you asked" (NDSS'25) is the direct predecessor this project reproduces and extends.
- Timing-based side channels on shared inference infra more broadly — InputSnatch; Carlini et al. on remote timing attacks on efficient LLM inference.
- Cache partitioning / selective isolation as a mitigation family, with published cost numbers — PrefixWall (selective per-prefix isolation, reports excluding first-entry-of-prompt attacks — directly relevant since our PIN position 1 is exactly that case) and SafeKV (3-tier ML privacy classifier, TTFT overhead 2.3–38.9% depending on model size).
- KV-cache *content* reconstruction (a different threat model from cross-tenant reuse detection): "Shadow in the Cache" (Luo et al., arXiv:2508.09442) proposes inversion/collision/injection attacks that recover prompt content directly from KV tensors, defended by an obfuscation scheme (KV-Cloak) — **this is a stronger attacker model (tensor-level access) than ours (API-only) and should be cited as related-but-distinct, not as prior art we are reproducing.**

**Gap in prior work identified by our background-load experiments:**
- KVGov (Addagada et al., arXiv:2608.09225) evaluates attack success rate against PROMPTPEEK using a **discrete-event simulation** with fixed hit/miss latencies rather than measurements under real GPU contention, and explicitly identifies field validation with real concurrent tenants as future work. Real deployments exhibit variable latency from GPU scheduling and memory-bandwidth contention that its simulation does not model.
- SafeKV (Chu et al.) evaluates only the *performance cost* of its own isolation mechanism under load, not whether an unmitigated attack's reliability changes as background tenant count increases.
- **To our knowledge, no prior work measures attack reliability itself as a function of concurrent, realistic background GPU load; we address this directly in our background-load studies (Studies 1–4).**

**What this project reproduces vs. contributes:**
- *Reproduces:* the core PROMPTPEEK-style cross-tenant leakage signal on SGLang (Level 1), now with a from-scratch two-process implementation rather than reuse of the original artifact.
- *Extends beyond PROMPTPEEK:* Level 2/4 (candidate ID and full sequential reconstruction of a structured secret via chained probing — not just presence detection); a non-ML detector evaluated against multiple legitimate-traffic baselines; a mitigation evaluation using SGLang's *native* `extra_key` field (not a research-only patch) with independently-recomputed legitimate-traffic cost figures; a like-for-like comparison table against PrefixWall/SafeKV's own reported costs; **and (pending KV4 sign-off) evaluation of attack reliability under realistic concurrent background GPU load with threshold degradation findings (Studies 1–4)**.

**Novel contribution claim (draft wording, for supervisor edit):** 
"A practical-exploitability characterization — not merely a leakage-only demonstration — of cross-tenant KV-cache side channels, spanning presence detection through full structured-secret reconstruction, paired with a lightweight detector and a native, load-bearing mitigation. We further characterize attack reliability under realistic concurrent background GPU load, identifying a threshold (not gradual) degradation pattern that neither prior defense evaluates under real hardware contention, and document the instability of the 'idle' baseline as a direct result of uncontrolled background activity on shared GPUs. We additionally disentangle tenant count from per-request size and find that request concurrency depth or timing pattern, not raw occupancy, governs reliability instability."

**Claims requiring cross-framework evidence before they can appear in the paper:** anything using the word "framework-independent," "general," or "across serving backends" — currently zero such claims are licensed by existing data; both vLLM and SGLang results exist but were not collected under aligned conditions (see RQ3 status).

**Do not claim novelty for the base leakage-detection result alone (Level 1)** — that is PROMPTPEEK's contribution, being reproduced, not invented.

---

## 3. RQ-to-Experiment Matrix

**Cache modes** (both frameworks, where the framework supports the mode):
- **shared-cache** — default, single namespace.
- **tenant-isolated** — SGLang `extra_key` salting; vLLM equivalent to be confirmed as part of KV2 (if vLLM lacks a native per-request salt field, this becomes a documented framework-capability difference, itself an RQ3 finding, not a gap to paper over).
- **cache-disabled** — SGLang `--disable-radix-cache`; vLLM equivalent launch flag to be confirmed in KV2.

**Background load instrumentation (for RQ4a):**
- Background load generator: `background_load.py` / `background_load_v3.py` — configurable number of independent synthetic worker processes issuing requests to the shared SGLang backend at a configurable maximum token length.
- Occupancy instrumentation: `compute_occupancy.py` — computes, for each attacker probe interval, the fraction of its wall-clock duration that overlapped with at least one logged background-worker request interval, averaged across all probes in a run. Yields per-run occupancy fraction in [0,1], computed from independently logged start/end timestamps.

| RQ | Framework(s) | Cache mode(s) | Attack/traffic condition | Secret / candidate space | Independent var(s) | Dependent metric(s) | Positive control | Negative control | Reps | Raw format | Analysis |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RQ1 | SGLang, vLLM | shared-cache | Idle-gap probe (≥1s) vs. back-to-back (contention confound) | N/A (presence only) | idle-gap duration | binary detection accuracy, latency Δ | back-to-back-only run (expected contention artifact) | probe with no prior victim activity | ≥15/condition (existing) → confirm N in KV2 | per-request CSV | two-sample t-test / Mann-Whitney, Cohen's d |
| RQ2 | SGLang (KV2/3), vLLM (KV3) | shared-cache | Candidate-ID probe (closed set) + sequential chained probe (open alphabet per position) | 4 entropy categories (L2); 6-digit numeric PIN (L4) | candidate-set size / secret length | top-1 accuracy, full-match accuracy, query count | random-guess baseline (1/k, 1/10^6) | probe against empty cache (post-flush) | N=30/category (existing SGLang) — must repeat under KV2 reproducibility before citing as final | per-request + per-trial CSV | binomial CI, exact match rate |
| RQ3 | SGLang & vLLM (aligned protocol, KV3) | shared-cache | Identical idle-gap + chained-probe protocol on both frameworks | 6-digit numeric PIN, same generator | framework | telemetry field availability (bool), latency d, L2/L4 accuracy, query budget to reach target accuracy | — (comparative, no single control) | same-framework repeat run (protocol stability check) | N=30/framework minimum | paired per-request CSVs | cross-framework comparison table, effect-size comparison |
| RQ4a | SGLang (KV4, gated) | shared-cache | Chained probe + background load generator (configurable worker count, token length) — Studies 1-4 protocol | 6-digit PIN | worker count (0,2,4,8), per-request token size (4,16,128 tok) | paired Cohen's d, occupancy fraction, accuracy-vs-worker-count curve, fraction of runs with d<0 | zero-background replication of existing L4 result | noise-only, no attack | Study 1: n=5/condition; Study 2: n=12/load level; Study 3: n=12/config; Study 4: n=4/condition | per-request + per-run CSV | Welch's t-test between load levels (0 vs 2: p<0.00001; 2 vs 4: p>0.4; 4 vs 8: p>0.5); Pearson correlation occupancy vs d; variance comparison across request-size configs |
| RQ4b | SGLang (existing + KV3/4 replication) | shared-cache, tenant-isolated | Attack traffic vs. 3 legitimate-traffic baselines | N/A (detector doesn't see secret) | detector thresholds (τ_lcp, τ_mut) | Precision/Recall/F1/FPR, detection latency (queries) | attack traffic (expected: flagged) | pure legitimate traffic, 3 distinct baselines | 30 attack trials + baseline sets (existing) | per-window CSV | threshold sweep, no cherry-picked single point |
| RQ5 | SGLang (existing) + vLLM (KV5, gated) | shared-cache, tenant-isolated, cache-disabled | Chained-probe attack; separately, legitimate same-tenant repeated-prefix traffic | 6-digit PIN (security); 10 shared-prefix prompts ×6 reps (performance) | mitigation mode | L4 accuracy, cache-hit rate, p50/p95 latency, throughput | shared-cache baseline (expected: vulnerable, full performance) | cache-disabled (expected: safe, zero same-tenant reuse) | N=30 security / N=60 performance (existing SGLang) | per-request + per-condition CSV | Cohen's d, Mann-Whitney; explicit note of any percentile-interpolation-convention sensitivity (cf. existing p95 discrepancy note in `main.tex` §Performance) |

**Gate reminder embedded in this matrix:** rows tagged "(KV3/KV4/KV5, gated)" and any vLLM-column cell not already backed by an existing Phase 0–4 CSV require the supervisor's `SIGN-OFF: KV1 approved` comment on issue #22 before execution. Rows backed by "(existing)" data may be *reproduced* under KV2 but the historical numbers are not final-paper evidence until that reproduction is done.

**Reproducibility caveat for RQ4a:** The 0-worker (ambient) baseline was not independently reproducible under uncontrolled shared-GPU conditions. An independent re-run by the second author produced a materially different 0-worker baseline ($d=0.237$, SD$=0.071$, vs. $d=0.779$ reported in the primary run; Welch $t=13.10$, $p<0.00001$). Root-cause investigation found an unrelated GPU process (a separate VLLM engine instance, ~84GB resident memory) active on the shared machine during the 0-worker trials, with SM utilization fluctuating between 17–87% throughout — i.e., the "0 synthetic workers" condition did not correspond to an actually idle GPU during that re-run. This does not affect the 2/4/8-worker comparisons, since added synthetic load there measurably dominates this kind of uncontrolled background signal, but it means the specific $d=0.779$ baseline value should be treated as provisional until re-measured under verified-idle GPU conditions (exclusive allocation or per-trial utilization logging; see Limitations section). The 2, 4, and 8-worker levels replicated closely (all $p>0.25$).

---

## Definition-of-Done Checklist (This Document)

- [x] Practical exploitability defined with quantitative criteria, no qualitative "exploitable" (§1)
- [x] Novelty claim distinguishable from prior work; each claim mapped to ≥1 planned/existing experiment (§2)
- [x] RQ-to-experiment matrix frozen, covering all 5 RQs, all three cache modes, both frameworks, positive+negative controls, and background-load studies (Studies 1-4) (§3)
- [x] No planned experiment depends on an ambiguous historical result — every "existing" cell is explicitly marked as requiring KV2 reproduction before being cited as final
- [x] Background load instrumentation and operational definitions added (§1 and §3)
- [x] Reproducibility caveat for 0-worker baseline documented (§3)
- [x] Request-size disentanglement and occupancy correlation limitations documented (§1 and §3)