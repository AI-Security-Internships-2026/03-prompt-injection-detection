#!/bin/bash
MODEL="deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
BLOCK_SIZE=16

python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL" \
  --enable-prefix-caching \
  --block-size $BLOCK_SIZE \
  --host 0.0.0.0 \
  --port 8000 \
  --gpu-memory-utilization 0.85 \
  --no-enable-log-requests \
  2>&1 | tee logs/vllm_server_$(date +%Y%m%d_%H%M%S).log
