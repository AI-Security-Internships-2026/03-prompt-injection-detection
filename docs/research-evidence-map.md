# Research Evidence Map

This M0 note links major existing research claims and artifacts to the code, raw data, analysis, and preserved snapshot used to locate them. It is a provenance map, not a statement that every historical result is submission-ready.

## Status key

- `VERIFIED` — relevant code/data/analysis artifact is present at the preserved snapshot.
- `VERIFIED-HISTORICAL` — evidence exists, but the final paper should rerun it from the stabilized/configuration-explicit code.
- `LEGACY BASELINE` — retained as baseline/preliminary evidence, not a standalone publication contribution.
- `NEEDS-RERUN` — final paper-facing result should be regenerated before manuscript freeze.
- `NEGATIVE RESULT` — preserved research finding; it should remain visible rather than being discarded.
- `MISLABELED` — historical artifact whose displayed system identity does not match its actual prediction source.

---

## Journal 1 — KV-Cache Security

| Evidence / claim | Experiment / code | Raw data / result | Analysis | Preserved snapshot | Status |
|---|---|---|---|---|---|
| vLLM timing and cross-tenant feasibility | `experiments/phase4/*`, `scripts/characterize_timing.py`, related timing/cross-tenant scripts | `results/timing_characterization.csv`, `results/cross_tenant_verification*.csv`, `results/phase4/*` | `analysis/phase4/REPORT.md` | `m0-kv-sglang-week11` | `VERIFIED`; practical secret recovery is a `NEGATIVE RESULT` under the tested Phase-4 setup |
| SGLang cross-tenant cache leakage | `experiments/sglang/run_cross_tenant.py`, `run_cross_tenant_gap.py` | `results/sglang/cross_tenant_*.csv` | `analysis/sglang/REPORT.md` | `m0-kv-sglang-week11` | `VERIFIED-HISTORICAL` |
| SGLang candidate identification | `experiments/sglang/run_candidate_recovery_*.py` | `results/sglang/candidate_recovery_*.csv` | `analysis/sglang/compute_metrics_candidates_*.py`, `analysis/sglang/REPORT.md` | `m0-kv-sglang-week11` | `VERIFIED-HISTORICAL`; script naming/docstring cleanup is needed before final freeze |
| Chained PIN reconstruction | `experiments/sglang/run_pin_chained_recovery.py`, `run_two_app_pin_detection_full.py`, `apps/*` | `results/sglang/pin_chained_recovery.csv`, `results/sglang/two_app_pin_detection_full.csv` | `analysis/sglang/REPORT.md` and analysis scripts | `m0-kv-sglang-week11` | `VERIFIED-HISTORICAL`; preserved two-app result contains 30/30 full matches, but current apps require a shared-mode rerun |
| Tenant isolation / salting | `experiments/sglang/run_pin_chained_recovery_salted.py`, `verify_salting_live.py` | `results/sglang/pin_chained_recovery_salted.csv` | `analysis/sglang/compute_metrics_mitigation.py`, `MITIGATION_REPORT.md` | `m0-kv-sglang-week11` | `VERIFIED-HISTORICAL` |
| Cache-disabled control | `experiments/sglang/run_pin_chained_recovery_disable_radix.py` | `results/sglang/pin_chained_recovery_disable_radix.csv` | mitigation analysis/report | `m0-kv-sglang-week11` | `VERIFIED` |
| Probe-pattern detector | `experiments/sglang/evaluate_detector_v2.py`, `evaluate_detector_v2_mitigated.py` | `results/sglang/mitigation/detection_*.csv` | `analysis/sglang/MITIGATION_REPORT.md` | `m0-kv-sglang-week11` | `VERIFIED`; claims must remain limited to the tested traffic/workloads |
| Legitimate-traffic / cache-performance comparison | `experiments/sglang/run_legit_traffic.py` | `results/sglang/mitigation/perf_baseline.csv`, `perf_salted.csv`, `perf_disable_radix.csv` | `analysis/sglang/MITIGATION_REPORT.md` | `m0-kv-sglang-week11` | `VERIFIED-HISTORICAL` |

### Current KV-cache reproducibility caveat

The preserved `apps/victim_app.py` and `apps/attacker_app.py` currently hard-code distinct tenant salts (`tenant_victim` and `tenant_attacker`). Historical shared/unsalted leakage and recovery results therefore cannot be reproduced from the current two-app state without changing configuration. The KV track must later expose explicit `shared-cache`, `tenant-isolated`, and `cache-disabled` modes from the same codebase and rerun final paper-facing experiments.

---

## Journal 2 — HardenedGuard / Prompt-Injection Canonicalization

| Evidence / claim | Code / experiment | Data / result | Preserved snapshot | Status |
|---|---|---|---|---|
| Bounded, guard-agnostic canonicalization layer | `src/canonicalize.py` | Final robustness evidence must be regenerated under the journal protocol | `m0-hardenedguard-rana` | Code `VERIFIED`; results `NEEDS-RERUN` |
| HardenedGuard composition (canonicalization + rules + semantic guard + cross-turn context) | `src/hardened_guard.py` | Final paper-facing ablation/evaluation is not yet frozen | `m0-hardenedguard-rana` | Code `VERIFIED`; results `NEEDS-RERUN` |
| Cross-turn conversation-history analysis | `src/multiturn.py` | Existing tests/evaluations are historical | `m0-hardenedguard-rana` | Code `VERIFIED`; this is **not KV-cache inspection** |
| TF-IDF + Logistic Regression baseline | `src/ml_detector.py`, `src/guardrail_comparison.py` | `experiments/results/guardrail_comparison_synthetic.json`, ML prediction/result files | `m0-week9-evaluation` | `LEGACY BASELINE` / `VERIFIED` |
| PIGuard baseline predictions | `piguard_predict.py` | `experiments/results/piguard_eval_dataset_v2.csv`, `piguard_deepset.csv` | `m0-week9-evaluation` | `VERIFIED` baseline |
| Historical McNemar comparison labeled as HardenedGuard | historical McNemar output | `experiments/results/mcnemar_PIGuard_raw_vs_HardenedGuard__Ours_.json` | `m0-week9-evaluation` | `MISLABELED`; prediction source B is `ml_detector_eval_predictions_deepset.csv`; **do not cite as HardenedGuard evidence** |

### Journal-2 scope note

The earlier TF-IDF/Logistic Regression work is retained as baseline/preliminary evidence for HardenedGuard. It is not treated as a third journal publication.

The multi-turn component operates on conversation text/history. It must be described as cross-turn conversation-context detection or conversation-history analysis, not as a KV-cache detector.

---

## Preserved M0 snapshots

| Snapshot | Tag | Commit |
|---|---|---|
| HardenedGuard / RANA | `m0-hardenedguard-rana` | `da2e5fab13e6e8224c9de085c2633df1847944e6` |
| Week-9 evaluation | `m0-week9-evaluation` | `cfa163ced1769171b999d8ad0fce2de74142481c` |
| KV-cache / SGLang Week-11 | `m0-kv-sglang-week11` | `d20d0d1c6408917c3e4594d5f58f416a7728be3f` |

Related M0 notes:

- `docs/m0-snapshot-register.md`
- `docs/m0-known-evidence-risks.md`

## M0 interpretation

- Existing research artifacts are preserved and traceable.
- Historical evidence is not automatically final paper evidence.
- Final journal experiments must be rerun from stabilized, explicit configurations before manuscript numbers are frozen.
- Negative findings are preserved as research evidence.
- The repository is proceeding with exactly two journal tracks: KV-cache security and HardenedGuard / prompt-injection canonicalization.
