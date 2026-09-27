# KV3 — Cross-Framework Characterization (Partial)

**Status: IN PROGRESS, not the finished cross-framework finding required by #24.**
See "Open items" at the bottom before citing anything here to a supervisor.

## 1. Root cause: vLLM cache-disable control was broken

`run_level3_vllm.py`'s `--cache-mode` flag only ever labeled CSV rows; it
never reconfigured the server. Every row labeled `cache-disabled` in the
originally delivered vLLM dataset was therefore collected against a
cache-**on** server. This is a code-level finding, confirmed by reading
`run_level3_vllm.py` directly (the flag is written to the CSV but never
passed to the server launch/config path).

This is consistent with what `analysis/cross_framework_comparison.md`
shows for the original dataset: vLLM/DeepSeek digit-reconstruction accuracy
is ~97-100% in **both** "shared" and "disabled" rows -- exactly what you'd
expect if the disabled condition never actually disabled anything.

A real cache-disabled vLLM server was brought up once this week and did
produce genuinely reduced-cache data (see "Open items" -- treat as
provisional, not final, pending a `harness.py` port-targeting re-check).

## 2. SGLang's disable mechanism is confirmed functional

`cache_salt` genuinely disables the radix cache in SGLang. Verified two ways:
- Statistically: reconstruction accuracy collapses toward chance for Qwen
  (p = 4.6e-9).
- Via direct engine telemetry: `cached_tokens` reads exactly 0 when disabled.

## 3. Candidate identification / reconstruction results (all conditions)

Full per-condition table: `analysis/summary_candidate_identification.csv`
(93 rows, generated directly from the raw CSVs by
`analysis/build_comparison_table.py` -- no hand-entered numbers).

Top-line digit-reconstruction table: `analysis/cross_framework_comparison.md`.

Notable results, positive and negative:
- vLLM/DeepSeek: high reconstruction accuracy in both cache modes in the
  original dataset -- now understood to be an artifact of the broken
  `--cache-mode` control (Section 1), not evidence that DeepSeek is
  exploitable under a genuinely matched disabled condition.
- vLLM/Qwen: **0.0% digit-reconstruction accuracy** in both shared and
  disabled rows (1800/1800 wrong in each). This is a genuine negative
  result preserved as-is; it has not been root-caused (could be a real
  model-specific negative finding, or a probe/guess-format mismatch in
  that CSV family -- not yet distinguished). Flagged for follow-up, not
  explained away here.
- SGLang: reconstruction accuracy across both models sits in the ~1-10%
  range, near or below the ~10% chance baseline for single-digit guessing,
  across shared and disabled modes in level3.
- SGLang `position_*_qwen.csv` / `prefix_*_qwen.csv`, and the DeepSeek
  files from the same generation window, are marked `unverified=True` in
  the summary CSV. They were generated before the SGLang
  `--disable-radix-cache` bug was found and have not been reconciled
  against a known-good server config. **Do not cite these as confirmed**
  until reconciled.

## 4. Level 1 leakage detection (kept separate from reconstruction)

`analysis/summary_leakage_detection.csv` reports cross-tenant timing
separation only -- whether an attacker's probe latency differs measurably
depending on whether a victim's secret was cached, **without** claiming
the secret value itself was identified. This is deliberately kept apart
from Section 3.

vLLM cross-tenant rows show a consistent latency gap between
`A_no_victim` and `B_after_victim_*` conditions across all four secret
categories tested, in both cache modes as labeled (shared-mode gap is
larger, consistent with a real cache effect; the disabled-mode gap,
given Section 1, needs re-interpretation once the control is fixed).
SGLang cross-tenant rows show a smaller, noisier gap at much smaller N
(30-90 rows) and include a distinct `isolated` condition not present in
the vLLM data -- treated as its own category, not collapsed into
"shared".

## 5. Why reconstruction succeeds or fails, by framework/condition

- **vLLM shared-cache conditions:** succeeds for DeepSeek because a real,
  functioning KV-cache prefix-sharing mechanism is active; the timing
  differential between correct/incorrect probe candidates is large enough
  to be statistically distinguishable (see cross-tenant latency gaps,
  Section 4).
- **vLLM "disabled" conditions (original dataset):** looks like it
  succeeds, but per Section 1 this is not evidence of disabled-mode
  exploitability -- the server was never actually in disabled mode.
- **vLLM disabled conditions (the one verified this-week run):**
  produced 46.7% per-digit accuracy at reduced scale, the first genuine
  vLLM disabled-mode data point this project has had, but at reduced
  server scale and without the matched full-scale comparison. Not
  included in the top-line table above because it is not part of the
  raw CSV deliverable analyzed by the script; see Open Items #1.
- **SGLang shared and disabled:** both sit near chance for digit
  reconstruction in this dataset. Given `cache_salt` is confirmed
  functional (Section 2) via engine telemetry, the near-chance result in
  *shared* mode as well suggests SGLang's prefix-sharing may not leak the
  same timing signal vLLM's does under this specific digit-probe protocol
  -- this is a plausible framework-level explanation, not yet confirmed
  by a matched, controlled comparison.

## 6. Framework-specific protocol differences

- Cache-disable mechanism differs structurally: vLLM has no equivalent to
  SGLang's `cache_salt`; disabling requires a server-level relaunch flag,
  which is why the broken `--cache-mode` control (a client-side label)
  was able to silently fail for as long as it did. SGLang's `cache_salt`
  is a per-request parameter, verifiable via engine telemetry
  (`cached_tokens`) without a server relaunch.
- vLLM level2/level3 CSVs carry an explicit `model` column with full HF
  model IDs; SGLang CSVs encode the model in the filename instead. The
  analysis script normalizes both to `qwen` / `deepseek`.

## 7. Issue #18 (background-load finding)

**Not replicated. Excluded from the cross-framework claim**, per the
resolution path in #24 item 4. No repeated runs with preserved CSVs exist
for this finding in the current dataset. This should stay excluded until
someone runs the repeated-trial replication.

## Open items (do not represent as resolved)

1. Full-scale matched vLLM shared-vs-disabled comparison, at original
   server configuration -- **still not done, and multiple Sep 23-24 attempts
   to produce it were traced and ruled out.** Provenance-tracing (via
   bash_history, log timestamps, `ss`/`ps` port checks) found that
   `level3_vllm_shared_deepseek_fullscale.csv` and `..._clean.csv` were
   written by a run pointed at `VLLM_PORT=8001`, but no log, process, or
   listening socket on port 8001 was ever found -- their source server is
   unidentified. `..._matched.csv` was written seconds after a port-8002
   "Address already in use" crash, most likely hitting a zombie process
   rather than an intentional launch. Even that window's
   `level3_vllm_disabled_deepseek.csv` lacks the "8002 came up on attempt N"
   success line its own retry-loop script was designed to log. All four are
   excluded in `analysis/build_comparison_table.py` (see `EXCLUDE_EXACT`)
   with the full trace in code comments. **This is the one result that
   would confirm or refute whether the original 100% vLLM/DeepSeek finding
   was cache-driven, and it still requires a fresh, carefully-logged run**
   -- ideally one that writes the actual bound port/PID into the CSV itself
   at request time, not just the launch command's stated `--port` flag.
2. Level-1 2D heatmap (prefix_length x secret_position jointly) -- cannot
   be built from this dataset; the existing sweeps vary each dimension
   independently. Needs a new joint sweep.
3. `run_pin_chained_recovery.py` was never delivered (only its output
   CSVs) -- the SGLang 30/30 baseline it produced cannot be independently
   re-verified from this deliverable.
4. Three provisional vLLM data points (33.3% / 40.6% / 46.7%) from a
   partial disabled-mode run this week are NOT included in the analysis
   above -- `harness.py`'s `VLLM_PORT` handling needs re-checking before
   trusting which server any of them actually hit.
5. Overnight vLLM run this week produced no usable data (engine crash).
6. Supervisor dual sign-off (KV1 + KV2) status not verified anywhere in
   this process.
7. The vLLM/Qwen 0.0% reconstruction result (Section 3) is unexplained --
   could be a genuine negative finding or a data-format issue in that CSV
   family. Needs follow-up before it's used as a claim either way.

**Bottom line:** the code-level root cause of the vLLM control bug is a
solid, citable finding. The broader cross-framework "why does
exploitability differ" question is not yet answered by a properly matched
experiment. Nothing above should be described as a completed
characterization.
