"""
run_metadata.py - Live metadata capture for KV1/KV2+ experiment runs.

Use in any runner:
    from experiments.sglang.run_metadata import capture_run_metadata, write_metadata_sidecar
    meta = capture_run_metadata(
        cache_mode=args.cache_mode,
        script_name=__file__,
        run_id=args.run_id,
        attack_params={"n_trials": args.n_trials},
    )
    write_metadata_sidecar(csv_path, meta)
"""
import json
import os
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return "unknown"


def _git_dirty():
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return bool(out)
    except Exception:
        return False


def capture_run_metadata(
    cache_mode,
    script_name,
    run_id=None,
    framework="sglang",
    framework_version="0.5.17",
    model_id="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    server_launch_flags="--mem-fraction-static 0.55 --disable-cuda-graph --context-length 4096",
    victim_tenant_id="tenant_victim",
    attacker_tenant_id="tenant_attacker",
    attack_params=None,
):
    if run_id is None:
        run_id = str(int(time.time()))
    return {
        "run_id": run_id,
        "cache_mode": cache_mode,
        "framework": framework,
        "framework_version": framework_version,
        "model_id": model_id,
        "server_launch_flags": server_launch_flags,
        "victim_tenant_id": victim_tenant_id,
        "attacker_tenant_id": attacker_tenant_id,
        "script_name": os.path.basename(script_name),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "attack_params": attack_params or {},
        "git_sha": _git_sha(),
        "git_dirty": _git_dirty(),
        "inferred_fields": {},
        "note": "Captured live at run time.",
    }


def write_metadata_sidecar(csv_path, metadata):
    csv_path = Path(csv_path)
    sidecar = csv_path.with_suffix(csv_path.suffix + ".metadata.json")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(metadata, indent=2))
    return str(sidecar)
