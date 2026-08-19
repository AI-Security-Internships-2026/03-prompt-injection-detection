# PROMPTPEEK-Style Multi-Tenant KV-Cache Timing Side-Channel Reproduction

Research internship project investigating whether shared prefix/KV-cache
mechanisms in multi-tenant LLM serving frameworks create timing side-channels
that leak information across tenants — inspired by PROMPTPEEK (Wu et al.,
NDSS 2025, SUSTech/ByteDance), "I Know What You Asked: Prompt Leakage via
KV-Cache Sharing in Multi-Tenant LLM Serving."

## Status: Phases 0–4 complete on vLLM. SGLang comparison in progress.

## Background

Original research direction was a TF-IDF + ML prompt-injection detector
(see `prior-work/` if merged). Pivoted to multi-tenant KV-cache timing
side-channels per supervisor direction.

**Important scope note:** PROMPTPEEK's original target system was **SGLang**
(radix-tree KV-cache, Longest Prefix Match scheduling), not vLLM. This
project reproduces the underlying mechanism on **vLLM** (Automatic Prefix
Caching) as an adaptation/transfer study, and is now extending to SGLang
directly for closer comparability with the original paper.

## Environment

- Hardware: NVIDIA DGX Spark, Blackwell GB10 GPU, CUDA 13, ~119GB unified memory
- Model: `deepseek-ai/DeepSeek-R1-Distill-Llama-8B`
- vLLM 0.26.0 (conda env `promptpeek`)
- SGLang (conda env `sglang-exp`), server on port 30000

## Repository structure

docs/threat_model.md Threat model (Phase 0)
deploy/launch_vllm.sh vLLM server launch script
scripts/
smoke_test.py Basic cold vs warm TTFT check (Phase 1)
characterize_timing.py Timing oracle characterization (Phase 2)
analyze_timing.py Phase 2 statistics
analyze_cross_tenant.py Phase 3 statistics
harness/
cross_tenant_test.py Cross-tenant causal-ordering test (Phase 3)
experiments/phase4/
README.md Phase 4 scope and boundaries
harness.py Victim/attacker ground-truth separation
secrets.py 4 entropy-category secret generators
measure.py Calibrated timing + hit/miss classifier
logger.py CSV logging schema
search_strategy.py STUB — see note below
run_ablation.py Full ablation sweep
experiments/sglang/
characterize_timing_sglang.py SGLang match_frac sweep (in progress)
analysis/phase4/
compute_metrics.py
REPORT.md Full Phase 4 findings
results/ All CSVs, plots
logs/ Server logs

## Results summary

### Phase 0 — Threat model
Attacker: co-tenant, API-level access, TTFT-based timing oracle, no
server access. Full doc: `docs/threat_model.md`.

### Phase 1 — Environment verification
vLLM deployed with `--enable-prefix-caching`. Cold vs warm latency
confirmed prefix caching active: **cold 98.8ms → warm 72.9ms** (stdev 0.6ms).

### Phase 2 — Timing oracle characterization
Measured TTFT across prefix-match depth (0%, 25%, 50%, 75%, 100%) with
prompt length held constant (fixing two confounds discovered during
development: self-cache contamination, prompt-length-not-held-constant).

| match_frac | mean TTFT | stdev |
|---|---|---|
| 0.00 | 879.5ms | 28.3ms |
| 0.25 | 652.4ms | 8.6ms |
| 0.50 | 438.1ms | 7.3ms |
| 0.75 | 229.3ms | 5.4ms |
| 1.00 | 77.7ms | 3.7ms |

**Cohen's d = 39.7, t = 280.4, p = 2.26e-259** — extremely strong,
statistically decisive timing oracle.

### Phase 3 — Cross-tenant causal leakage
Before/after victim-cache-population test, verifying the timing shift
is causally tied to the victim's request (not attacker self-caching).

**Paired t = 5.878, p < 0.00001, Cohen's d = 0.831**, 44/50 (88%)
hit-consistent trials. A longer shared-template variant was also tested
and found to perform *worse* (d=0.340) due to cross-trial cache
bleed-through — a documented methodological finding, not used as the
primary result.

### Phase 4 — Information recovery feasibility
Built full victim/attacker separation harness, 4 secret-entropy
categories, calibrated classifier, and ran ablation across 20 secrets
× 4 trial counts (1/3/5/10).

**Key finding:** despite the strong aggregate oracle (Phase 2/3), no
entropy category showed a reliable before→after confidence increase at
practical trial counts. Root cause diagnosed precisely: secret position
within the template matters — secrets at the end of a long shared
template produce no measurable signal (shared-prefix caching swamps the
secret-specific effect); secrets at the start produce a real but small
gap, still below the noise floor for reliable per-secret classification
at 1–10 trials.

**This bounds the practical threat model**: cross-tenant leakage is
real and statistically overwhelming in aggregate, but reliable
single-secret extraction requires either much larger prefix-
differentiating spans or substantially higher trial budgets than tested.
Full data and analysis: `analysis/phase4/REPORT.md`.

### Phase 4, search_strategy.py — explicitly unimplemented
The adaptive candidate-search/extraction algorithm is intentionally left
as an interface stub. This component requires sourcing from the
PROMPTPEEK paper's published methodology directly (with supervisor
authorization), rather than being generated from scratch. See
`experiments/phase4/README.md` for full rationale.

### SGLang comparison — in progress
Extending the Phase 2 methodology to SGLang (the paper's actual target
system) for direct comparability. Initial single-tenant validation
confirmed prefix caching is active (cold ~425ms vs warm ~91ms). Full
match_frac sweep in progress via `experiments/sglang/characterize_timing_sglang.py`.

## Open questions (pending supervisor input)

1. SGLang vs. vLLM as the primary target system for final reporting.
2. Source for the Phase 4 search/extraction algorithm.
3. Correct GitHub repo/location for this work (currently blocked on
    push access to `AI-Security-Internships-2026/03-prompt-injection-detection`).

## Reproduction

```bash
conda activate promptpeek
cd ~/promptpeek-repro
nohup ./deploy/launch_vllm.sh > logs/server_bg.log 2>&1 &
# wait for "Application startup complete." in the log
python scripts/smoke_test.py
python scripts/characterize_timing.py && python scripts/analyze_timing.py
python harness/cross_tenant_test.py && python scripts/analyze_cross_tenant.py
python experiments/phase4/run_ablation.py && python analysis/phase4/compute_metrics.py