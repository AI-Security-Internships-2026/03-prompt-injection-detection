# SGLang Cross-Tenant PIN Recovery — Detection & Mitigation Report

**Model:** deepseek-ai/DeepSeek-R1-Distill-Llama-8B
**SGLang version:** 0.5.17
**Hardware:** NVIDIA GB10 (DGX Spark), CUDA 13.0, sm_121
**Branch:** week10-sglang-cross-tenant

This report covers the detection and mitigation phase, building on the
validated baseline in `analysis/sglang/REPORT.md`: 100% deterministic
cross-tenant cache-state leakage, contention-controlled timing leakage
(d≈3.4-4.0, p≈0.0002 at ≥1s gap), and 100% full synthetic PIN
reconstruction (N=30) via sequential chained per-digit cache-hit probing.

## Threat Model

Attacker and victim are separate FastAPI processes (`apps/attacker_app.py`
:8002, `apps/victim_app.py` :8001) sharing a single SGLang backend
(:30000). The attacker has no access to victim process memory, session
state, or ground truth - only to its own HTTP responses from SGLang,
specifically the `cached_tokens` field and request latency. The detector
described below is a server-side (SGLang-observable) detector: it
consumes only request content and arrival timing, i.e. exactly what an
inference server operator could observe, not attacker-internal state.

## Part 1 — Detection

### Candidate signals tested

Per the phase plan, four candidate signals were considered:
1. High rate of near-identical prefix requests from one session
2. Repeated sequential prefix probes with single-token/character variation
3. Abnormal request frequency/burst pattern
4. Systematic candidate-like probing structure (sweeping 0-9 per position)

### Signal 3 (burst rate): tested and rejected as a standalone gate

The attack's own methodology (`run_pin_chained_recovery.py`) inserts a
0.3s flush-settle sleep and a 1.0s `GAP_SECONDS` delay before every probe,
specifically to avoid the request-scheduling-contention confound
documented in the baseline REPORT.md (Stage 3). Reconstructing real
inter-request timing (see Methodology) gives a measured ceiling attacker
rate of **~0.72-0.77 req/s** - an order of magnitude below a naive burst
threshold (e.g. 5 req/s) and comparable to or slower than plausible
legitimate automated traffic. This is reported as a genuine **negative
result**: rate-based detection is not a reliable standalone signal against
this attack under this methodology, precisely because the attack was
engineered to avoid the timing-contention confound. Rate is retained in
the implementation as a logged diagnostic field only, not used to gate
classification.

### Signals 1+2 (combined): validated detector

**Features**, computed per non-overlapping window of 10 consecutive
requests (10 = number of digit guesses per PIN position in the baseline
attack):

- **`mean_lcp`**: mean prefix-match ratio between consecutive prompts in
  the window, i.e. `common_prefix_length / max(len(p1), len(p2))`,
  averaged over adjacent pairs. Computed via direct character-by-character
  prefix comparison (see Methodology note on `difflib` failure below).
- **`mutation_density`**: fraction of adjacent pairs whose exact character
  (Hamming) difference count falls in `[1, 8]` - i.e. differ by a small,
  bounded number of characters rather than being identical or wholly
  different.

**Classification rule**: a window is flagged if `mean_lcp >= lcp_threshold`
AND `mutation_density > mutation_threshold`.

### Legitimate traffic baselines (three conditions, increasing difficulty)

1. **Slow/casual**: varied unrelated topics, human pacing (2.5-8s jittered
   gaps).
2. **Power-user (adversarial baseline for rate)**: fast (0.5-1.5s gaps,
   comparable to attacker rate) but topically non-systematic prompts -
   tests whether speed alone would false-positive.
3. **Shared-prefix (adversarial baseline for mean_lcp)**: prompts that
   legitimately share `SHARED_PUBLIC_PREFIX` (as real multi-tenant support
   traffic would, since it's the public system prompt), each followed by a
   genuinely different account-specific question. This is the hardest case
   for `mean_lcp` as a signal, since it isolates whether prefix-sharing
   alone (without the mutation-density constraint) would false-positive.

### Results

| lcp_threshold | mutation_threshold | Precision | Recall | F1 | FPR (slow) | FPR (power-user) | FPR (shared-prefix) |
|---|---|---|---|---|---|---|---|
| 0.7-0.95 (all tested) | 0.5-0.8 (all tested) | 1.000 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 |

Full sweep in `results/sglang/mitigation/detection_threshold_sweep.csv`.

Result is flat and perfect across the entire tested threshold grid: attack
windows show `mean_lcp ≈ 0.98-1.0`, all three legitimate conditions show
near-zero `mean_lcp` (unrelated-topic conditions) or high `mean_lcp` but
low `mutation_density` (shared-prefix condition, where follow-up questions
differ from each other by far more than the 1-8 character band). The two
features are complementary: `mean_lcp` alone would risk false positives
against the shared-prefix condition; `mutation_density` alone would not
distinguish attack traffic from any other short, low-diversity traffic.
Together they correctly separate all tested conditions with no
overlap in this dataset.

**Detection latency**: 30/30 attack trials flagged, mean and median
**10 requests** into the trial - i.e., detectable after the first PIN
position's 10-digit sweep completes, well before the 6-position (~60
request) full recovery finishes. Per-trial data in
`results/sglang/mitigation/detection_latency.csv`.

### Methodology notes and bugs found/fixed (reported per project transparency norm)

1. **Fabricated timeline (initial draft, caught before reporting)**: an
   earlier version of the detector script assigned a synthetic uniform
   10 req/s timeline to attack data instead of using real timing. Fixed by
   reconstructing timestamps from the attack script's own known sleep
   durations (`0.3 + 1.0`s) plus measured `wall_clock_latency`, cumulative
   per trial. This is a lower-bound reconstruction, since `flush_cache()`
   and `victim_populate()` request latency are not separately logged in
   `pin_chained_recovery.csv` - true spacing is >= the reconstructed value.

2. **Overlapping windows (initial draft, caught before reporting)**: an
   earlier version used stride-1 sliding windows, producing highly
   autocorrelated, non-independent samples that would overstate confidence
   in P/R/F1. Fixed to non-overlapping windows (stride = window size),
   grouped by trial so windows never span a trial boundary.

3. **Incomplete prompt reconstruction (caught via anomalous recall drop
   at position 1 of every trial)**: the attack CSV logs only
   `known_prefix_so_far` and `guess_digit`, not the full prompt text sent
   to SGLang. An initial reconstruction concatenated only these two
   fields, omitting `SHARED_PUBLIC_PREFIX` (~1097 shared characters) and
   PIN formatting/padding. This artificially zeroed `mean_lcp` at PIN
   position 1 specifically (where `known_prefix_so_far` is empty),
   producing a false recall ceiling of 0.833 (5/6 positions caught, 1/6
   structurally missed). Fixed by reconstructing the exact prompt string
   via the same construction logic as `attacker_probe()` in
   `run_pin_chained_recovery.py`, using constants from `config.py`.

4. **`difflib.SequenceMatcher` silently mismeasuring prefix length on
   repetitive text (caught via a still-anomalous zero `mean_lcp` at
   position 1 after fix #3)**: `find_longest_match()` with `autojunk=True`
   (the default, active for strings >200 chars) treats frequently-occurring
   characters as unsuitable anchors. Verified directly: manual
   `os.path.commonprefix` found a true shared prefix of 1097 characters
   between two real position-1 attack prompts, while
   `find_longest_match()` returned a spurious 11-character match at offset
   1098, missing the true prefix match entirely. An intermediate attempt
   to fix this via `SequenceMatcher.ratio()` (whole-string similarity
   rather than anchored prefix match) also produced flat, degraded recall
   for a related reason and was discarded. Final fix: direct
   character-by-character prefix comparison (no `difflib` dependency),
   which is also more semantically correct for this use case, since the
   feature specifically needs prefix-match length (mirroring what the
   SGLang radix-tree cache itself measures), not general longest-common-
   substring similarity.

5. **Suffix-length mutation proxy failing near string start (caught
   alongside #3/#4)**: the original mutation signal computed
   `max_len - lcp_len` as a proxy for "characters changed," which measures
   everything *after* the first divergence point, not the true edit
   distance. For position-1 probes (divergence near the start of the PIN
   segment), this proxy balloons to roughly the length of the remaining
   PIN and marker text, causing false negatives exactly where the
   divergence occurs early. Fixed by switching to exact Hamming distance,
   which is valid here because all reconstructed prompts at a given
   position are equal-length by construction (fixed `PIN_LENGTH`, fixed
   placeholder padding, fixed label/marker).

### Limitations

- Detector was validated against `pin_chained_recovery.csv`
  (single-app harness), not yet against the two-app architecture's
  per-request logs, since `two_app_pin_detection_full.csv` currently only
  stores per-trial summaries (`trial, ground_truth_pin, recovered_pin,
  full_match`), not per-request data. Extending per-request logging to the
  two-app path is recommended before claiming the detector generalizes to
  that architecture.
- All three legitimate-traffic baselines are synthetic (script-generated),
  not captured from real usage. The shared-prefix condition's question set
  (10 templates) is small; a larger, more diverse legitimate-traffic
  corpus would strengthen the FPR estimate.
- The perfect 1.000/1.000/1.000/0.000 result reflects a wide separation
  margin in this dataset (attack `mean_lcp` ~0.98-1.0 vs. legitimate
  conditions near 0 or with low `mutation_density`); it should not be
  read as evidence the detector is threshold-insensitive in general -
  only that, for this specific attack pattern and these three baselines,
  the margin happens to be wide enough that the tested threshold range
  is not close to a decision boundary.
- Detection is per-window; a slower or lower-volume variant of the attack
  (e.g. fewer digits probed per position, larger window needed to
  accumulate signal) has not been tested and may show different latency
  or recall characteristics. This is a natural adaptive-attacker question
  for future work.

### Conclusion (Part 1)

A detector combining prefix-match ratio and small-bounded-edit-distance
mutation density, evaluated over non-overlapping 10-request windows,
achieves perfect separation (P=R=F1=1.000, FPR=0.000) between the
validated chained PIN-recovery attack and three legitimate-traffic
conditions of increasing difficulty, with a mean detection latency of 10
requests - well before a full PIN can be recovered. Request-rate/burst
signals were tested and found unreliable as a standalone gate for this
specific attack, since its methodology deliberately uses inter-request
gaps to avoid a known timing confound; this is reported as a negative
result rather than omitted.

---

## Part 2 — Mitigation

*(pending)*
