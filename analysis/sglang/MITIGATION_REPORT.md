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

6. **Pandas dtype upcasting silently corrupted prompt reconstruction
   (caught via manual inspection of pasted CSV rows in an interactive
   testbed, initially misdiagnosed as a corrupted PIN_TRAILING_MARKER
   character in the real attack data)**: `known_prefix_so_far` is NaN at
   `position=1` for every trial, which forces pandas to read the entire
   column as `float64`. Recovered digit strings like `"0"` or `"4"`
   therefore became floats `0.0` / `4.0`, and naive `str()` conversion
   produced `"0.0"` (3 characters, including a stray `.`) instead of
   `"0"` (1 character). This shifted the guess digit's position within
   the reconstructed prompt for every row at `position >= 2` (5 of 6 PIN
   positions per trial - the large majority of the dataset), and the
   stray `.` was initially mistaken for `PIN_TRAILING_MARKER` during
   manual review. Confirmed via direct inspection that the underlying CSV
   data and the original attack run were correct - the bug was isolated
   to this script's own reconstruction logic. Fixed via explicit
   NaN-aware, float-aware string conversion (`_safe_prefix_str`) before
   prompt reconstruction. All threshold-sweep and detection-latency
   results in this report were regenerated after this fix; see git
   history for the pre-fix numbers if a before/after comparison is
   needed.

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
### Existing Mitigations (Prior Work)

This project's baseline attack (100% deterministic cache-state leakage, d≈3.4-4.0 contention-controlled timing leakage, 100%/N=30 full PIN reconstruction) is a direct reproduction and extension of PROMPTPEEK (Wu et al., "I Know What You Asked: Prompt Leakage via KV-Cache Sharing in Multi-Tenant LLM Serving," NDSS 2025), which specifically targeted SGLang's radix-tree KV cache and Longest-Prefix-Match scheduling. Prior work on defending against this class of attack falls into three broad strategies, summarized below.

1. Full user-level cache isolation. InputSnatch (Zheng et al., 2024), Cache Partitioning (Pang et al., 2024), and "Auditing Prompt Caching in Language Model APIs" (Gu et al., 2025) all propose eliminating prefix sharing across users entirely - either via per-user cache namespaces or a unique per-user salt token prepended to every request. This closes the side channel at its source (no shared prefix state exists to probe) but forfeits prefix-cache performance benefits across all users, not just an attacker. SafeKV's own motivational measurements found per-user isolation costs 2.3-8.9% higher TTFT on a 13B model and 8.3-38.9% higher TTFT on a 70B model, since real-world workloads show substantial legitimate cross-user prefix reuse (SafeKV reports 9-63% inter-user reuse rates across three real chat datasets).

2. Timing obfuscation / constant-time inference. Carlini and Nasr (2024, "Remote Timing Attacks on Efficient Language Model Inference") propose injecting noise so cache hit/miss latency distributions overlap, making them statistically indistinguishable to an attacker. PrefixWall's analysis of this approach identifies two limitations worth noting for this project: it imposes uniform delay penalties on all requests regardless of whether an attack is occurring, and it does not address the root cause (the prefix cache still being shared across security domains) - meaning an attacker with enough samples or an amplification strategy may still recover signal. This is consistent with this project's own baseline finding that timing leakage persisted independent of the cached_tokens telemetry field (d≈3.4-4.0 even without that field, REPORT.md Stage 3), suggesting obfuscation defenses must fully equalize the underlying compute path, not just add noise on top of it.

3. Selective / adaptive isolation. Two recent systems propose isolating only what's necessary rather than everything:

PrefixWall (Pennas et al., IMDEA Software Institute, 2026, implemented on vLLM 0.8.5): tracks per-cache-entry ownership and flags a prefix for isolation only once a different user actually hits it - benign same-user reuse and non-attacked prefixes remain fully shared. Reports up to 70% higher cache reuse and 30% lower latency than full per-user isolation, with per-request overhead of only 0.007ms (0.004ms detector + 0.003ms activator). A dynamic "Activator" component disables protection entirely when the KDE overlap between hit/miss latency distributions exceeds an administrator-set threshold (i.e., when the channel is not practically exploitable under current load/model/hardware conditions) - directly informed by their finding that timing gaps collapse under high request-per-second load due to batching/queuing contention, which parallels this project's own Stage 3 finding that the v2 timing anomaly was resolved by controlling for request-scheduling contention via an idle gap. Stated limitation directly relevant to this project's threat model: PrefixWall's own security proof states it does not protect (a) attacks targeting the very first entry of a prompt (no parent node exists to flag), or (b) an attacker who guesses correctly on the first attempt. This project's PIN-recovery attack begins probing from an empty known_prefix_so_far at position 1 - exactly the case PrefixWall's own paper acknowledges it cannot cover, though PrefixWall's authors argue the risk is low in that specific case because hit/miss distributions still overlap substantially for single-entry prefixes on their tested hardware/models. Whether that holds for this project's setup would need to be checked, not assumed.
SafeKV (Chu et al., University of Connecticut / Peking University, 2025, implemented directly on SGLang - the same serving framework used throughout this project): uses a three-tier hybrid privacy classifier (regex/blacklist rules, a lightweight transformer PII detector, and LLM-based context-aware validation) to decide whether each KV-cache block is safe to share or must stay private to its creator, plus entropy-based runtime monitoring to catch misclassified blocks after the fact. Reports 94-97% defense success rate across six LLM backbones, and 1.36-2.66× throughput improvement over full cache partitioning. However, its own reported per-tier latency numbers are a significant cost: Tier-2 (the general ML-based detector, applied whenever Tier-1 rules don't match) averages 113-125ms per request (P99 up to 172ms), and Tier-3 (LLM-based context validation, used for ambiguous cases) is substantially higher still, scaling with the size of the underlying model. For comparison, this project's own baseline attack probes average ~89ms total (wall_clock_latency mean, from pin_chained_recovery.csv) - meaning SafeKV's Tier-2 detection overhead alone is comparable to or larger than an entire baseline request in this project's setup. SafeKV's semantic classification approach is also not directly applicable to this project's synthetic PIN secrets without adaptation, since PII-pattern detectors are tuned for natural-language identifiers (names, SSNs, emails), not arbitrary structured digit sequences - a real gap between SafeKV's evaluated threat model and this project's.
### Implications for candidate mitigation selection (Part 2b)

Cross-referencing the six original candidates against what prior work found:

Full cache isolation / disabling cross-tenant reuse (candidates 1/3): matches the "full user-level isolation" category above. Strongest security guarantee, but both PrefixWall and SafeKV independently measured substantial performance cost from this approach (8.3-38.9% TTFT increase in SafeKV's own baseline measurements) - useful as an Experiment B/C upper-bound security / worst-case-performance reference point, not a serious candidate for the "proposed mitigation."
Cache salting / tenant-specific keys (candidate 2): functionally equivalent to full isolation from a security standpoint (a unique salt per tenant breaks all cross-tenant prefix alignment, identical in effect to PrefixWall's own "User Cache Isolation" baseline, which they implement by prepending a unique per-user token) - same performance tradeoff applies.
Removing cached_tokens telemetry (candidate 4): this project's own baseline data (REPORT.md Stage 3) already demonstrates this is insufficient alone, since contention-controlled timing leaks independently of that field (d≈3.4-4.0). Prior work's timing- obfuscation category is the correct framing for what would actually be needed here, not simple field removal - and per PrefixWall's own critique, obfuscation without addressing the shared-cache root cause is fragile to amplification.
Rate limiting informed by the Part 1 detector (candidate 5): SafeKV's related-work section explicitly lists rate limiting as a real, currently-deployed complementary defense (cites OpenAI's rate limits), but notes it "must be carefully tuned to avoid degrading service quality for benign users" - directly relevant given this project's own Part 1 finding that the real attacker rate (~0.72-0.77 req/s) is low enough to blend with plausible legitimate automated traffic, meaning naive rate limiting alone would likely be ineffective here without the structural (LCP + mutation-density) signal Part 1 already built.
Selective/adaptive isolation (new candidate, from this search): the strongest fit given this project's constraints. A PrefixWall-style approach (flag-on-cross-user-hit, no semantic classification required) is lower-complexity and lower-latency than SafeKV's ML-based approach, and - critically - SafeKV was built on SGLang specifically, meaning its cache-index design (unified radix tree with public/private tags) is architecturally closer to what this project's SGLang 0.5.17 setup would need than PrefixWall's vLLM-based implementation.

Recommendation for Part 2c: a PrefixWall-style ownership-tracking + selective-isolation approach, implemented via application-level cache key salting once a cross-tenant hit is detected (rather than requiring a modified SGLang cache index, which is a much larger engineering lift given this project's timeline), is the most promising candidate for actual implementation and evaluation - it directly addresses the root cause (shared prefix state), has published performance numbers to compare against, and does not require building a semantic PII classifier that would need adaptation for synthetic PIN-style secrets in the first place. This should be evaluated alongside the existing Part 1 detector as a complementary layer (detection informing rate limiting or heightened isolation sensitivity), consistent with PrefixWall's own Activator concept of conditionally engaging protection based on measured exploitability rather than running it unconditionally.


### Implementation (Part 2c)

Following the recommendation above, cache-salt isolation was implemented at the application layer using SGLang 0.5.17's native per-request `extra_key` field (confirmed via direct source inspection of `GenerateReqInput` in `io_struct.py` and its use in the radix-tree cache-matching key in `radix_cache.py`). `measure.py`'s `send_request` and `shared_client.py`'s `send_to_sglang` were both extended with an optional `cache_salt` parameter, forwarded to SGLang as `extra_key`. `victim_app.py` and `attacker_app.py` tag their requests with `cache_salt="tenant_victim"` and `cache_salt="tenant_attacker"` respectively. `run_pin_chained_recovery_salted.py` imports `send_request` directly from `measure.py` rather than reimplementing the salting logic, calling it with the appropriate per-tenant salt for victim and attacker requests.

Note: the native `/generate` endpoint accepts `extra_key` only, not `cache_salt` — that alias exists solely on the OpenAI-compatible endpoints. An initial patch sent `cache_salt` directly to `/generate`, which was silently dropped by the server with no error, and a smoke test still showed a full cross-tenant cache hit. This was caught by the smoke test itself, not assumed fixed.

A second mitigation, `--disable-radix-cache` (a server-side SGLang launch flag disabling the shared radix-tree cache entirely), was evaluated as a comparison point requiring no client-side changes.

### Security Results (Part 2c)

| Condition | N | Attack accuracy (full PIN match) | cached_tokens observed |
|---|---|---|---|
| Baseline (Part 1, no mitigation) | 30 | 100% | greater than 0 on cross-tenant hits |
| Cache-salt isolation (extra_key) | 30 | 0.00% | 0 on all 1,800 rows |
| --disable-radix-cache | 30 | 0.00% | 0 on all 1,800 rows |

Both mitigations fully eliminated the cache-timing side channel: cached_tokens=0 across all 1,800 logged requests in each condition, and attacker-recovered guesses collapsed to a deterministic "000000" rather than converging on the true PIN or showing random noise — evidence the timing/cache signal was removed outright, not merely degraded.

### Methodology note: mitigated-variant script discarded

An earlier script, `run_pin_chained_recovery_mitigated.py`, and its output `pin_chained_recovery_mitigated.csv`, were found to be broken (incorrect response-field path; salting was never actually applied despite the script's intent) and are excluded from all reported results. This was caught by inspecting `full_match` values (all False/0) and comparing guessed vs. ground-truth PINs directly, not by trusting the file's presence or name.

### Legitimate-Traffic Performance Comparison (Part 2d)

To evaluate whether either mitigation imposes a cost on normal, non-attack
usage, 60 requests simulating one legitimate tenant's overlapping support
traffic (10 distinct prompts x 6 repeats, shuffled order, shared long
system prefix — the hardest case for cache reuse, matching Part 1's
detector validation traffic) were sent under each condition.

| Condition | cache_hit_rate | avg cached_tokens | latency p50 | latency p95 | throughput |
|---|---|---|---|---|---|
| Baseline (unsalted) | 98.3% | 186.7 | 86ms | 111ms | 9.91 req/s |
| Cache-salt (salted) | 98.3% | 186.7 | 82ms | 94ms | 11.38 req/s |
| --disable-radix-cache | 0.0% | 0.0 | 99ms | 109ms | 9.27 req/s |

Cache-salt isolation is effectively free for legitimate same-tenant
traffic: cache-hit rate and average cached tokens are identical to
baseline, since the salt only breaks matches *across* tenants, not a
tenant's own repeated prefix. Latency and throughput differences from
baseline are within normal run-to-run noise.

`--disable-radix-cache`, by contrast, eliminates all prefix-cache reuse
even for the legitimate tenant's own repeated requests (cache_hit_rate
0.0% vs. 98.3% baseline), with a smaller-than-expected latency/throughput
penalty in this setup — likely because `max_new_tokens=1` keeps
per-request generation cost low regardless of prefix-cache state, so the
full cost of losing prefix caching may be understated here relative to
longer-generation workloads. This is noted as a limitation of the
measurement, not a claim that disabling radix caching is free in general.

### Detector Re-Evaluation Under Mitigation (Part 2e)

The Part 1 detector (LCP + mutation-density signals) was re-run against
the cache-salt-mitigated attack traffic (`pin_chained_recovery_salted.csv`)
to confirm it still correctly identifies attack-pattern traffic even
though the mitigation reduces actual PIN extraction to 0%.

Result: P=R=F1=1.000, 30/30 trials flagged (mean 10.0 requests-to-detect).
This confirms the detector operates on request/timing *pattern*
(sequential per-position probing structure), not on the `cached_tokens`
leakage signal itself — so it remains effective as a complementary
detection layer even under a mitigation that fully blocks the underlying
side channel, consistent with this project's Part 1 recommendation that
detection and mitigation be layered rather than treated as alternatives.

### Significance Statistics (Part 2f)

Cohen's d and Mann-Whitney U were computed comparing `cached_tokens`
between baseline (n=1800, mean=186.2, std=3.44) and salted (n=1800,
mean=0.0, std=0.0 — zero variance, every row exactly 0).

d = 76.5, Mann-Whitney U p < 1e-300 (scipy reports p=0, i.e. below
floating-point representable precision).

This effect size is reported as a formal statistical statement of
complete separation between conditions, consistent with — not
independent evidence beyond — the already-deterministic 0/30 vs. 30/30
accuracy result; it is included to satisfy the project's stated rigor
standard, not because the conclusion was in doubt. A secondary check on
wall-clock latency (d=-1.67, p<1e-300) confirms the mitigation does not
require any change to attacker probe timing methodology to remain
measurable — the salted condition is simply undetectable via cache
timing, not slower to probe.


References
Wu et al., "I Know What You Asked: Prompt Leakage via KV-Cache Sharing in Multi-Tenant LLM Serving," NDSS 2025.
Pennas, Papaioannou, Guarnieri, Doudali, "PrefixWall: Mitigating Prefix Caching Side Channels in Shared LLM Systems," arXiv:2603.10726, 2026.
Chu, Lin, Xiang, Shen, Su, Chu, Yang, Zhang, Wu, Zhang, "Selective KV-Cache Sharing to Mitigate Timing Side-Channels in LLM Inference" (SafeKV), arXiv:2508.08438, 2025.
Zheng et al., "InputSnatch: Stealing Input in LLM Services via Timing Side-Channel Attacks," arXiv:2411.18191, 2024.
Carlini and Nasr, "Remote Timing Attacks on Efficient Language Model Inference," 2024.
Pang et al., "Cache Partitioning for Mitigating Timing Side-Channel Attacks in LLM Serving Systems," 2024.
Gu et al., "Auditing Prompt Caching in Language Model APIs," 2025.

