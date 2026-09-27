#!/usr/bin/env python3
"""
KV3 cross-framework comparison table builder.

Reads the raw CSVs delivered under results/sglang/kv2/ and results/phase4/kv3/
and produces:
  - analysis/summary_candidate_identification.csv   (per-digit / per-candidate reconstruction accuracy)
  - analysis/summary_leakage_detection.csv           (Level 1: cross-tenant timing separation, no secret value guessed)
  - analysis/cross_framework_comparison.md           (human-readable table for the report)

This script does NOT fill in numbers by hand -- every value in the output
comes from aggregating the CSV rows below. Files known to be compromised or
unverified per results/kv3_readme.md are excluded, not silently included.

KNOWN EXCLUSIONS (see tmp/kv3_readme.md):
  - results/sglang/kv2/level3_shared_qwen.csv
        -> bugged run (--disable-radix-cache was active despite "shared" label).
           Use level3_shared_qwen_v2.csv instead.
  - results/sglang/kv2/position_*_qwen.csv, prefix_*_qwen.csv
        -> generated before the SGLang caching bug was found/fixed; not
           reconciled against a known-good server config. Included here but
           flagged UNVERIFIED in the output, not silently trusted.
  - DeepSeek SGLang position_*/prefix_* files
        -> same generation window as the bug; also flagged UNVERIFIED
           (readme states this was "never explicitly rechecked").

Nothing here fabricates or replicates the still-missing full-scale matched
vLLM comparison, the joint prefix x position sweep, or the issue #18
background-load replication -- those experiments do not exist in the raw
data and this script cannot manufacture them.
"""
import csv
import glob
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SGLANG_DIR = os.path.join(ROOT, "results", "sglang", "kv2")
VLLM_DIR = os.path.join(ROOT, "results", "phase4", "kv3")
VLLM_V2_DIR = os.path.join(ROOT, "results", "phase4", "kv3_v2")
OUT_DIR = os.path.join(ROOT, "analysis")

EXCLUDE_EXACT = {
    os.path.normpath(os.path.join(SGLANG_DIR, "level3_shared_qwen.csv")),  # bugged, use _v2

    # kv3_v2 vLLM "matched"/"fullscale"/"clean" attempts (Sep 23-24 window):
    # provenance-traced via bash_history + log timestamps + port checks and
    # found to have NO verified successful server launch behind them.
    #   - fullscale.csv / clean.csv: written by a run pointed at VLLM_PORT=8001,
    #     but no log, process, or listening socket on 8001 was ever found
    #     (confirmed via `ss -tlnp | grep 8001` and `ps aux | grep 8001`, both empty).
    #   - matched.csv: written seconds after a port-8002 "Address already in
    #     use" crash; most likely hit a zombie process, not an intentional
    #     shared-cache launch.
    #   - this window's disabled_deepseek.csv: retry-loop script was designed
    #     to log "8002 came up on attempt N" on success; that line never
    #     appears in any log (confirmed via grep), so even this file's server
    #     config is unconfirmed.
    # Excluded until a fresh run exists with a verified startup log tied to
    # the actual serving port. See docs/kv3-cross-framework-report.md, Open Items.
    os.path.normpath(os.path.join(VLLM_V2_DIR, "level3_vllm_shared_deepseek_fullscale.csv")),
    os.path.normpath(os.path.join(VLLM_V2_DIR, "level3_vllm_shared_deepseek_clean.csv")),
    os.path.normpath(os.path.join(VLLM_V2_DIR, "level3_vllm_shared_deepseek_matched.csv")),
    os.path.normpath(os.path.join(VLLM_V2_DIR, "level3_vllm_disabled_deepseek.csv")),
}

def is_unverified(path):
    """Flag files whose producing server config could not be confirmed."""
    base = os.path.basename(path)
    if (SGLANG_DIR in path) and (base.startswith("position_") or base.startswith("prefix_")):
        return True
    # vLLM "disabled" files in the original kv3/ dataset: the report
    # (docs/kv3-cross-framework-report.md, Section 1) established that
    # run_level3_vllm.py's --cache-mode flag only labeled CSV rows; it never
    # reconfigured the server. So every "disabled" row in this dataset was
    # actually collected against a cache-ON server. Flag as UNVERIFIED so the
    # comparison table does not present these as genuine disabled-mode results.
    if (VLLM_DIR in path) and "disabled" in base:
        return True
    # Anything left in kv3_v2 that isn't in EXCLUDE_EXACT hasn't been
    # individually provenance-traced the way the four excluded files were --
    # flag it rather than assume it's fine by omission.
    if VLLM_V2_DIR in path:
        return True
    return False


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def frac_true(rows, col):
    vals = [r[col] for r in rows if r.get(col) not in (None, "")]
    if not vals:
        return None
    truthy = sum(1 for v in vals if v.strip().lower() == "true")
    return truthy / len(vals), len(vals)


def model_of(path, rows):
    base = os.path.basename(path)
    if "qwen" in base.lower():
        return "qwen"
    if "deepseek" in base.lower():
        return "deepseek"
    # vLLM level2/level3 files carry a model column
    if rows and "model" in rows[0]:
        m = rows[0]["model"]
        if "deepseek" in m.lower():
            return "deepseek"
        if "qwen" in m.lower():
            return "qwen"
    return "unknown"


def mode_of(rows, path):
    if rows and "cache_mode" in rows[0]:
        cm = rows[0]["cache_mode"]
        return "disabled" if "disab" in cm else "shared"
    base = os.path.basename(path)
    if "disabled" in base:
        return "disabled"
    if "isolated" in base:
        return "isolated"  # third condition, distinct from shared/disabled -- do not collapse into "shared"
    return "shared"


# ---------------------------------------------------------------------------
# Candidate identification / reconstruction: level3_*, position_*, prefix_*, level2_*
# Accuracy column differs by family: position_correct | condition==correct | guess_correct
# ---------------------------------------------------------------------------
def accuracy_column_and_value(rows):
    if not rows:
        return None
    cols = rows[0].keys()
    if "position_correct" in cols:
        return frac_true(rows, "position_correct")
    if "guess_correct" in cols:
        return frac_true(rows, "guess_correct")
    if "condition" in cols:
        vals = [r["condition"] for r in rows]
        correct = sum(1 for v in vals if v.strip().lower() == "correct")
        return correct / len(vals), len(vals)
    return None


def sweep_dimension(basename):
    if basename.startswith("position_"):
        parts = basename.split("_")
        return "secret_position", parts[1]
    if basename.startswith("prefix_"):
        parts = basename.split("_")
        return "prefix_length", parts[1]
    if basename.startswith("level3_"):
        return "digit_reconstruction", "n/a"
    if basename.startswith("level2_"):
        parts = basename.replace("level2_vllm_", "").split("_")
        mode = parts[0]
        category = "_".join(parts[1:-1])
        return "secret_structure", category
    return "other", "n/a"


def collect_candidate_id(paths):
    out = []
    for p in sorted(paths):
        base = os.path.basename(p)
        if os.path.normpath(p) in EXCLUDE_EXACT:
            continue
        rows = read_csv(p)
        acc = accuracy_column_and_value(rows)
        if acc is None:
            continue
        acc_val, n = acc
        framework = "sglang" if SGLANG_DIR in p else "vllm"
        dim, dim_val = sweep_dimension(base)
        out.append({
            "framework": framework,
            "model": model_of(p, rows),
            "cache_mode": mode_of(rows, p),
            "sweep_dimension": dim,
            "sweep_value": dim_val,
            "n_rows": n,
            "accuracy": round(acc_val, 4),
            "unverified": is_unverified(p),
            "source_file": os.path.relpath(p, ROOT),
        })
    return out


# ---------------------------------------------------------------------------
# Level 1 leakage detection: cross_tenant_* files.
# These measure whether attacker timing distinguishes "victim secret was
# cached" from "no victim secret cached" -- NOT whether the secret value
# itself was identified. Kept structurally separate from candidate ID above.
# ---------------------------------------------------------------------------
def collect_leakage_detection(paths):
    out = []
    for p in sorted(paths):
        base = os.path.basename(p)
        if "_gt" in base:  # ground-truth companion files, not signal files
            continue
        rows = read_csv(p)
        if not rows or "condition" not in rows[0] or "wall_clock_latency" not in rows[0] and "wall_clock_latency_ms" not in rows[0]:
            continue
        lat_col = "wall_clock_latency_ms" if "wall_clock_latency_ms" in rows[0] else "wall_clock_latency"
        by_cond = defaultdict(list)
        for r in rows:
            try:
                by_cond[r["condition"]].append(float(r[lat_col]))
            except (ValueError, KeyError):
                continue
        if len(by_cond) < 2:
            continue
        means = {c: sum(v) / len(v) for c, v in by_cond.items() if v}
        framework = "sglang" if SGLANG_DIR in p else "vllm"
        out.append({
            "framework": framework,
            "cache_mode": mode_of(rows, p),
            "conditions": ";".join(f"{c}={m:.3f}" for c, m in means.items()),
            "n_rows": len(rows),
            "source_file": os.path.relpath(p, ROOT),
        })
    return out


def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    sglang_paths = glob.glob(os.path.join(SGLANG_DIR, "*.csv"))
    vllm_paths = glob.glob(os.path.join(VLLM_DIR, "*.csv"))
    vllm_v2_paths = glob.glob(os.path.join(VLLM_V2_DIR, "*.csv")) if os.path.isdir(VLLM_V2_DIR) else []

    cand = collect_candidate_id(sglang_paths + vllm_paths + vllm_v2_paths)
    leak = collect_leakage_detection(
        [p for p in sglang_paths if "cross_tenant" in os.path.basename(p)]
        + [p for p in vllm_paths if "cross_tenant" in os.path.basename(p)]
    )

    write_csv(
        os.path.join(OUT_DIR, "summary_candidate_identification.csv"),
        cand,
        ["framework", "model", "cache_mode", "sweep_dimension", "sweep_value",
         "n_rows", "accuracy", "unverified", "source_file"],
    )
    write_csv(
        os.path.join(OUT_DIR, "summary_leakage_detection.csv"),
        leak,
        ["framework", "cache_mode", "conditions", "n_rows", "source_file"],
    )

    # Cross-framework top-line table: digit_reconstruction rows only, by
    # framework x model x cache_mode. This is the closest existing analogue
    # to an "equivalent protocol" comparison -- it is NOT the full-scale
    # matched comparison the open issue still requires.
    lines = [
        "# KV3 Cross-Framework Comparison (generated by analysis/build_comparison_table.py)",
        "",
        "**Scope note:** this table covers the digit-reconstruction (Level 3) sweep only,",
        "generated directly from the raw CSVs. It is NOT the full-scale matched",
        "shared-vs-disabled comparison at original server scale -- that experiment",
        "has not been run (see docs/kv3-cross-framework-report.md).",
        "",
        "| Framework | Model | Cache Mode | Per-digit Accuracy | N | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for r in cand:
        if r["sweep_dimension"] != "digit_reconstruction":
            continue
        note = "UNVERIFIED (pre-bugfix run)" if r["unverified"] else ""
        lines.append(
            f"| {r['framework']} | {r['model']} | {r['cache_mode']} | "
            f"{r['accuracy']*100:.1f}% | {r['n_rows']} | {note} |"
        )
    with open(os.path.join(OUT_DIR, "cross_framework_comparison.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Wrote {len(cand)} candidate-identification rows")
    print(f"Wrote {len(leak)} leakage-detection rows")
    print("See analysis/cross_framework_comparison.md for the top-line table.")


if __name__ == "__main__":
    main()
