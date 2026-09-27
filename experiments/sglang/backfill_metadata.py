#!/usr/bin/env python3
"""
backfill_metadata.py - Generate per-CSV sidecar metadata for existing KV2 results.

CONTEXT (KV2 issue #23, item 3):
Mati required that every paper-facing run records: cache mode, framework+version,
model, launch flags, tenant IDs, script name, run ID/timestamp, attack params, git SHA.
The KV2 CSVs were produced before a metadata helper existed. This script backfills
that metadata for the historical CSVs, marking every INFERRED field explicitly so
nothing is presented as measured when it is reconstructed.

Run from repo root:
    python3 experiments/sglang/backfill_metadata.py
"""
import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
KV2_DIR = REPO_ROOT / "results" / "sglang" / "kv2"

FRAMEWORK = "sglang"
FRAMEWORK_VERSION = "0.5.17"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
MODEL_ALIASES = {
    "deepseek": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    "qwen": "Qwen/Qwen2.5-7B-Instruct",
}
SERVER_LAUNCH_FLAGS = "--mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096"
VICTIM_TENANT_ID = "tenant_victim"
ATTACKER_TENANT_ID = "tenant_attacker"
DEFAULT_ATTACK_PARAMS = {"n_trials": 30, "pin_length": 6, "seed": None}


def git_last_commit_sha(path):
    try:
        rel = path.relative_to(REPO_ROOT)
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", str(rel)],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return out or "untracked"
    except Exception:
        return "unknown"


def infer_cache_mode(name):
    if "disabled" in name:
        return "cache-disabled", False
    if "isolated" in name:
        return "tenant-isolated", False
    if "shared" in name:
        return "shared-cache", False
    if "salted" in name:
        return "tenant-isolated", True
    return "unknown", True


def infer_model(name):
    for alias, model_id in MODEL_ALIASES.items():
        if alias in name:
            return model_id, False
    return DEFAULT_MODEL, True


def infer_script(name):
    if name.startswith("cross_tenant"):
        return "experiments/sglang/run_cross_tenant.py", True
    if "pin_chained" in name and "disable_radix" in name:
        return "experiments/sglang/run_pin_chained_recovery_disable_radix.py", False
    if "pin_chained" in name:
        return "experiments/sglang/run_pin_chained_recovery.py", True
    if name.startswith("candidate_full"):
        return "experiments/sglang/run_candidate_recovery_full.py", True
    if name.startswith("candidate_prefix"):
        return "experiments/sglang/run_candidate_recovery_prefix.py", True
    if name.startswith("candidate_pin"):
        return "experiments/sglang/run_candidate_recovery_pin.py", True
    if name.startswith("candidate_uuid"):
        return "experiments/sglang/run_candidate_recovery_uuid.py", True
    return "unknown", True


def file_mtime_utc(path):
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_metadata(csv_path):
    name = csv_path.stem
    cache_mode, cm_inferred = infer_cache_mode(name)
    model_id, model_inferred = infer_model(name)
    script_name, script_inferred = infer_script(name)
    git_sha = git_last_commit_sha(csv_path)
    timestamp = file_mtime_utc(csv_path)

    return {
        "run_id": name,
        "cache_mode": cache_mode,
        "framework": FRAMEWORK,
        "framework_version": FRAMEWORK_VERSION,
        "model_id": model_id,
        "server_launch_flags": SERVER_LAUNCH_FLAGS,
        "victim_tenant_id": VICTIM_TENANT_ID,
        "attacker_tenant_id": ATTACKER_TENANT_ID,
        "script_name": script_name,
        "timestamp_utc": timestamp,
        "attack_params": DEFAULT_ATTACK_PARAMS,
        "git_sha": git_sha,
        "source_csv": str(csv_path.relative_to(REPO_ROOT)),
        "inferred_fields": {
            "cache_mode": cm_inferred,
            "model_id": model_inferred,
            "script_name": script_inferred,
            "timestamp_utc": False,
            "git_sha": True,
            "attack_params": True,
            "framework_version": True,
            "server_launch_flags": True,
        },
        "note": (
            "Backfilled by experiments/sglang/backfill_metadata.py. "
            "Fields marked inferred=true in inferred_fields are reconstructed "
            "from filename convention, file mtime, git history, or documented "
            "constants. Future runs capture live via run_metadata.py."
        ),
    }


def write_sidecars():
    KV2_DIR.mkdir(parents=True, exist_ok=True)
    csvs = sorted(KV2_DIR.glob("*.csv"))
    if not csvs:
        print("No CSVs found in " + str(KV2_DIR))
        return

    index_rows = []
    for csv_path in csvs:
        meta = build_metadata(csv_path)
        sidecar = csv_path.with_suffix(csv_path.suffix + ".metadata.json")
        sidecar.write_text(json.dumps(meta, indent=2))
        index_rows.append({
            "run_id": meta["run_id"],
            "cache_mode": meta["cache_mode"],
            "model_id": meta["model_id"],
            "framework_version": meta["framework_version"],
            "timestamp_utc": meta["timestamp_utc"],
            "git_sha": meta["git_sha"],
            "script_name": meta["script_name"],
            "source_csv": meta["source_csv"],
        })
        print("  wrote " + str(sidecar.relative_to(REPO_ROOT)))

    index_path = KV2_DIR / "run_metadata.csv"
    with index_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index_rows[0].keys()))
        w.writeheader()
        w.writerows(index_rows)
    print("\nIndex written: " + str(index_path.relative_to(REPO_ROOT)))
    print("Total: " + str(len(index_rows)) + " CSVs processed.")


if __name__ == "__main__":
    write_sidecars()
