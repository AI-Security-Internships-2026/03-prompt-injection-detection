=== Hardware/environment ===
## Hardware
name, driver_version, memory.total [MiB]
NVIDIA GB10, 580.95.05, [N/A]

CPU: Cortex-X925
Cortex-A725
RAM: 119Gi
OS: "Ubuntu 24.04.3 LTS"

## SGLang server launch commands (exact, copy-pasteable)

### Normal (shared / tenant-isolated tests, radix cache ACTIVE)
```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096
```

### Cache-disabled config test
```bash
python -m sglang.launch_server --model-path Qwen/Qwen2.5-7B-Instruct --port 30010 --mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096 --disable-radix-cache
```

## SGLang package version
0.5.19

Note: nvidia-smi reports GPU memory as N/A on this ARM (GB10/Grace) platform;
this is a known driver-reporting quirk, not a missing GPU. Actual VRAM confirmed
via server logs during KV5 runs: "Reported total GPU memory per device (MiB): [122570]"
(~122.5 GB), consistent with --mem-fraction-static 0.55 configuration used throughout.
