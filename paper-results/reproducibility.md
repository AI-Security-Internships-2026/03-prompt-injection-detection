# KV6 Reproducibility Instructions

## One-command artifact regeneration

    cd ~/promptpeek-repro
    python3 analysis/kv6/generate_paper_artifacts.py

Reads all raw CSVs from results/kv5_v2/, results/sglang/kv2/, and
results/kv4/detector_v3/; writes everything into paper-results/.

## Server launch - SGLang (Qwen2.5-7B-Instruct)

Shared / tenant-isolated mode:

    python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096

Cache-disabled mode (adds --disable-radix-cache):

    python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096 --disable-radix-cache

## Server launch - vLLM (DeepSeek-R1-Distill-Llama-8B)

Requires activating .venv-rana:

    source ~/promptpeek-repro/.venv-rana/bin/activate

Shared mode (--enable-prefix-caching):

    python -m vllm.entrypoints.openai.api_server --model deepseek-ai/DeepSeek-R1-Distill-Llama-8B --port 8001 --enable-prefix-caching --gpu-memory-utilization 0.5 --max-model-len 4096

Disabled mode (--no-enable-prefix-caching):

    python -m vllm.entrypoints.openai.api_server --model deepseek-ai/DeepSeek-R1-Distill-Llama-8B --port 8001 --no-enable-prefix-caching --gpu-memory-utilization 0.5 --max-model-len 4096

## KV5 perf sweep

    bash ~/run_kv5_master.sh

Runs 3 mitigations x 3 concurrency levels x 3 repeats and writes 27
perf CSVs + summaries + 3 security CSVs to results/kv5_v2/.

## Determinism and seeds

- Bootstrap: SEED=42, N_BOOTSTRAP=2000 (percentile method)
- All numbers in paper_numbers_kv.json recomputed from raw CSVs on every run
- No manual numbers anywhere in paper-results/

## Known asymmetry in sample size

- shared attack success: 30 trials (KV2 baseline)
- tenant_isolated / disabled attack success: 10 trials each (KV5 mitigations)
- Documented in Table 1's wider Wilson CI for the mitigated conditions
