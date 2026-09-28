# KV5 Reproducibility Instructions

## 1. Known-good commit
Checkout the frozen tag before reproducing any numbers:
```bash
git checkout paper-kv-results-freeze-v1
```
Commit SHA: `68aa2213a752232a2753a55b4d185ea8f71b8028`

## 2. Environment setup
See `results/kv-environment.md` for full hardware spec (NVIDIA GB10, ARM Grace platform,
~122.5GB VRAM, 119GB RAM, Ubuntu 24.04.3 LTS).

Install pinned dependencies into a clean conda env:
```bash
conda create -n sglang-exp python=3.11 -y
conda activate sglang-exp
pip install -r requirements-kv-paper.txt
```
SGLang version: 0.5.19 (pinned in requirements-kv-paper.txt)

## 3. Launch the SGLang server

**Normal mode** (radix cache active — used for `shared` and `tenant-isolated` configs):
```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 \
  --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096
```

**Cache-disabled mode** (used only for the `cache-disabled` config test):
```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 \
  --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096 --disable-radix-cache
```

Wait for the server to report ready, then verify before trusting any results:
```bash
curl -s http://localhost:30010/get_model_info | grep radix_cache_disabled
```
- Normal mode must show `"radix_cache_disabled":false`
- Cache-disabled mode must show `"radix_cache_disabled":true`

**Known pitfall (do not repeat):** an earlier run accidentally left `--disable-radix-cache`
on for hours during what should have been a normal-mode run, silently invalidating that
data (it looked like "no leakage" but was really "no cache running"). Always verify the
flag above before trusting shared/tenant-isolated results.

## 4. Run order for KV5

For each cache mode (`shared`, `tenant-isolated`, `cache-disabled`), with the correct
server variant running:
```bash
cd experiments/sglang
python run_level3.py --cache-mode <mode> --trials 10 --out ../../results/kv5/security_<mode>.csv
python ../kv5_perf_load.py --mode <mode> --concurrency 1  --requests-per-worker 20 --out ../../results/kv5/perf_<mode>_c1.csv
python ../kv5_perf_load.py --mode <mode> --concurrency 10 --requests-per-worker 20 --out ../../results/kv5/perf_<mode>_c10.csv
```
Repeat the full sequence 3 times (independent runs) into `results/kv5/`, `results/kv5/run2/`,
`results/kv5/run3/` — required for KV6's confidence intervals (Section 3.1: ≥3 independent runs
per paper number).

**Note on scope:** this KV5 run used a documented down-selected scope relative to the original
issue spec: SGLang only (vLLM skipped), 2 concurrency levels (1, 10 — not 50), 10 trials per
security test (not 30), ~20 req/worker load tests (not the full 5-min/1000-req spec). This is
recorded here for transparency, not hidden.

## 5. Regenerate all paper numbers, tables, and figures
One script, from the repo root, with the conda env active:
```bash
python analysis/kv6/generate_all_paper_artifacts.py
```
This reads raw CSVs under `results/kv5/` (all 3 runs), computes bootstrap 95% CIs (2000
resamples, seed=42), Welch's t-tests with effect sizes (Cohen's d + bootstrap CI), and
Wilson score CIs for the security exact-match rate. It writes:
- `results/paper_numbers_kv.json` — every number, structured, traceable to raw rows
- `results/kv-paper-table-drafts.md` — markdown tables ready to copy into the manuscript

Deterministic: same input CSVs always produce the same output (fixed seed).

## 6. Manifest / raw data integrity
`results/manifest.json` lists every raw CSV under KV2-KV5 with its SHA-256 hash and size.
Regenerate and diff against the committed version if you suspect any raw file was altered:
```bash
python3 -c "import hashlib; print(hashlib.sha256(open('results/kv5/security_shared.csv','rb').read()).hexdigest())"
```
Compare the printed hash to the corresponding entry in `manifest.json`.

## 7. Expected runtime (on this reference hardware: NVIDIA GB10, ARM Grace)
- Model load per server (re)start: ~2 minutes
- One full KV5 run (all 3 configs, security + perf, 2 server switches): ~15-20 minutes
- 3 independent runs total: ~1-1.5 hours
- `generate_all_paper_artifacts.py`: a few seconds (no GPU needed, pure CPU stats on
  already-collected CSVs)

## 8. Known limitations (documented, not hidden)
- This covers KV5 only. KV2-KV4 raw data is hashed in `manifest.json` but not yet wired into
  `generate_all_paper_artifacts.py` — that integration is still open work.
- Section 4.2's anti-cherry-picking sensitivity check (e.g., "results with/without excluding
  warmup requests") is not yet implemented for KV5 perf numbers.
- Small-sample significance tests (n=6 per group, df~4-6) use a normal approximation for the
  p-value; for a stricter reviewer-facing number, use `scipy.stats.t.sf` with the reported
  exact df instead.
