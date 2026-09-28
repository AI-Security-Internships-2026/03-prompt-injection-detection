#!/bin/bash
# KV5 master sweep. Runs in tmux; ~2h. Produces results/kv5_v2/ and regenerates
# combined table + Pareto figure. Never kills other users' processes.
set -u
cd ~/promptpeek-repro
source ~/miniforge3/etc/profile.d/conda.sh
conda activate sglang-exp

TS=$(date +%Y%m%d_%H%M%S)
LOG=logs/kv5_master_${TS}.log
mkdir -p logs results/kv5_v2
exec > >(tee -a "$LOG") 2>&1

MODEL=Qwen/Qwen2.5-7B-Instruct
URL=http://localhost:30010/generate
PORT=30010
OUT=results/kv5_v2

echo "=================================================="
echo "KV5 MASTER SWEEP — $(date)"
echo "Log: $LOG"
echo "Output: $OUT"
echo "=================================================="

wait_port() {
    local tries=${1:-40}
    for i in $(seq 1 $tries); do
        curl -s "http://localhost:${PORT}/get_model_info" > /dev/null 2>&1 && return 0
        sleep 5
    done
    return 1
}

launch_sglang() {
    local mode=$1
    local extra=$2
    echo "=== Launching SGLang (mode=$mode) $(date) ==="
    python -m sglang.launch_server \
        --model-path "$MODEL" \
        --port $PORT \
        --mem-fraction-static 0.55 \
        --disable-cuda-graph \
        --context-length 4096 \
        $extra \
        > "logs/sglang_kv5_${mode}_${TS}.log" 2>&1 &
    local pid=$!
    if ! wait_port 40; then
        echo "ERROR: SGLang did not come up (mode=$mode, pid=$pid)"
        return 1
    fi
    echo "  sglang up (mode=$mode, pid=$pid)"
    SGLANG_PID=$pid
}

kill_sglang() {
    if [ -n "${SGLANG_PID:-}" ]; then
        echo "=== Killing SGLang PID $SGLANG_PID $(date) ==="
        kill $SGLANG_PID 2>/dev/null
        wait $SGLANG_PID 2>/dev/null
        unset SGLANG_PID
        sleep 8
    fi
}

run_perf_sweep() {
    local mode=$1
    local tenant_flag=$2
    for conc in 1 10 25; do
        for repeat in run1 run2 run3; do
            local out="$OUT/$repeat/perf_${mode}_c${conc}.csv"
            echo "--- perf mode=$mode conc=$conc repeat=$repeat $(date) ---"
            python experiments/kv5_perf_load.py \
                --url "$URL" \
                --mode "$mode" \
                --concurrency $conc \
                --requests-per-worker 20 \
                $tenant_flag \
                --out "$out" 2>&1 | tail -5
        done
    done
}

# ---- shared (no salt, cache on) ----
launch_sglang "shared" ""
run_perf_sweep "shared" ""
kill_sglang

# ---- tenant-isolated (per-thread salt, cache on) ----
launch_sglang "isolated" ""
run_perf_sweep "isolated" "--tenant-isolated"
kill_sglang

# ---- cache-disabled ----
launch_sglang "disabled" "--disable-radix-cache"
run_perf_sweep "disabled" ""
kill_sglang

# ---- regenerate combined table + Pareto ----
echo "=== Regenerating combined table + Pareto $(date) ==="
if [ -f analysis/compute_kv5_tradeoff.py ]; then
    python3 analysis/compute_kv5_tradeoff.py \
        --base-dir "$OUT" \
        --run-dirs "" run2 run3 \
        --concurrency-levels 1 10 25 \
        --out-csv "$OUT/kv5_tradeoff.csv" \
        --out-png "$OUT/kv5_pareto.png"
else
    echo "WARNING: analysis/compute_kv5_tradeoff.py not found — combined table/figure not generated"
fi

echo "=================================================="
echo "KV5 MASTER SWEEP DONE — $(date)"
echo "=================================================="
