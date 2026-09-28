# KV — Environment and Dependency Pins

**Generated:** 2026-09-28T13:26:03Z
**Host:** spark-6e5e

## Hardware

- GPU: NVIDIA GB10 (DGX Spark)
- Driver: 580.95.05
- CUDA: 13.0
- CPU: ARM Cortex-X925 / Cortex-A725
- RAM: 119 Gi
- OS: Ubuntu 24.04.3 LTS

## Software pins

```
Python 3.11.16
sglang 0.5.19
torch 2.13.0+cu130
transformers 5.12.1
numpy 2.3.5
pandas 3.0.5
matplotlib 3.11.2
```

## vLLM env (separate venv)

```
vllm 0.27.1
```

## SGLang server launch (shared / tenant-isolated)

```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096
```

## SGLang server launch (cache-disabled)

```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096 --disable-radix-cache
```

## vLLM server launch

```bash
# shared (prefix caching on)
python -m vllm.entrypoints.openai.api_server --model deepseek-ai/DeepSeek-R1-Distill-Llama-8B --port 8001 --enable-prefix-caching --gpu-memory-utilization 0.5 --max-model-len 4096

# disabled (prefix caching off)
python -m vllm.entrypoints.openai.api_server --model deepseek-ai/DeepSeek-R1-Distill-Llama-8B --port 8001 --no-enable-prefix-caching --gpu-memory-utilization 0.5 --max-model-len 4096
```
