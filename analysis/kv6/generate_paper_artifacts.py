#!/usr/bin/env python3
import hashlib, json, os, random, shutil, subprocess, math, csv as _csv
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev
from datetime import datetime, timezone

SEED = 42
random.seed(SEED)
N_BOOTSTRAP = 2000
ALPHA = 0.05

REPO = Path(__file__).resolve().parents[2]
KV5_V2 = REPO / "results" / "kv5_v2"
KV2_DIR = REPO / "results" / "sglang" / "kv2"
KV4_DIR = REPO / "results" / "kv4" / "detector_v3"
OUT = REPO / "paper-results"
OUT_RAW = OUT / "raw"
MITIGATIONS = ["shared", "isolated", "disabled"]
CONCURRENCIES = [1, 10, 25]
RUNS = ["run1", "run2", "run3"]


def read_summary(path):
    if not path.exists(): return None
    d = {}
    for line in path.read_text().splitlines():
        for tok in line.split():
            if "=" in tok:
                k, v = tok.split("=", 1)
                try: d[k] = float(v)
                except ValueError: d[k] = v
    return d or None


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()


def git(*args):
    try:
        return subprocess.check_output(["git"] + list(args), cwd=REPO, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


def bootstrap_ci(values, n_boot=N_BOOTSTRAP, alpha=ALPHA):
    if not values: return {"point": None, "ci_low": None, "ci_high": None, "n": 0}
    if len(values) == 1:
        p = mean(values)
        return {"point": p, "ci_low": p, "ci_high": p, "n": 1}
    n = len(values)
    boots = [mean([values[random.randrange(n)] for _ in range(n)]) for _ in range(n_boot)]
    boots.sort()
    return {"point": mean(values),
            "ci_low": boots[int((alpha / 2) * n_boot)],
            "ci_high": boots[int((1 - alpha / 2) * n_boot) - 1],
            "n": n, "n_boot": n_boot}


def wilson_ci(k, n, alpha=ALPHA):
    if n == 0: return {"point": None, "ci_low": None, "ci_high": None, "n": 0}
    z = 1.959963984540054
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"point": p, "ci_low": max(0.0, centre - half), "ci_high": min(1.0, centre + half), "n": n, "k": k}


def welch_t(xs, ys):
    if len(xs) < 2 or len(ys) < 2: return None
    mx, my = mean(xs), mean(ys)
    vx, vy = stdev(xs) ** 2, stdev(ys) ** 2
    nx, ny = len(xs), len(ys)
    se = math.sqrt(vx / nx + vy / ny)
    if se == 0: return None
    t = (mx - my) / se
    df = (vx / nx + vy / ny) ** 2 / ((vx / nx) ** 2 / (nx - 1) + (vy / ny) ** 2 / (ny - 1))
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(t) / math.sqrt(2))))
    return {"t": t, "df": df, "p": p}


def cohens_d(xs, ys):
    if len(xs) < 2 or len(ys) < 2: return None
    nx, ny = len(xs), len(ys)
    sx, sy = stdev(xs), stdev(ys)
    pooled = math.sqrt(((nx - 1) * sx * sx + (ny - 1) * sy * sy) / (nx + ny - 2))
    if pooled == 0: return None
    return (mean(xs) - mean(ys)) / pooled


def collect_perf():
    out = {m: {c: {} for c in CONCURRENCIES} for m in MITIGATIONS}
    for m in MITIGATIONS:
        for c in CONCURRENCIES:
            metrics = {}
            for run in RUNS:
                p = KV5_V2 / run / ("perf_" + m + "_c" + str(c) + "_summary.txt")
                d = read_summary(p)
                if d is None: continue
                for k, v in d.items():
                    if isinstance(v, (int, float)):
                        metrics.setdefault(k, []).append(v)
            out[m][c] = metrics
    return out


def kv2_reconstruction(path):
    rows = list(_csv.DictReader(open(path)))
    by_trial = defaultdict(list)
    for r in rows: by_trial[r["trial"]].append(r)
    exact = 0
    for t, trs in by_trial.items():
        inferred = []
        for pos in sorted(set(r["position"] for r in trs), key=int):
            pos_rows = [r for r in trs if r["position"] == pos]
            best = max(pos_rows, key=lambda r: int(r["cached_tokens"] or 0))
            inferred.append(str(int(best["guess_digit"])))
        inferred_pin = "".join(inferred)
        gt = str(int(trs[0]["ground_truth_pin"]))
        if inferred_pin == gt: exact += 1
    return exact, len(by_trial)


def kv5_exact_match(path):
    rows = list(_csv.DictReader(open(path)))
    by_trial = defaultdict(list)
    for r in rows: by_trial[r["trial"]].append(r)
    exact = 0
    for t, trs in by_trial.items():
        if all(str(r.get("position_correct", "")).lower() == "true" for r in trs):
            exact += 1
    return exact, len(by_trial)


def collect_attack_success():
    out = {}
    baseline = KV2_DIR / "pin_chained_shared.csv"
    if baseline.exists():
        k, n = kv2_reconstruction(baseline)
        out["shared"] = {"k": k, "n": n, "source": str(baseline.relative_to(REPO))}
    for mit, fname in [("tenant_isolated", "security_tenant_isolated.csv"),
                       ("disabled", "security_disabled.csv")]:
        path = KV5_V2 / "run1" / fname
        if not path.exists(): path = KV5_V2 / fname
        if path.exists():
            k, n = kv5_exact_match(path)
            out[mit] = {"k": k, "n": n, "source": str(path.relative_to(REPO))}
    return out


def write_paper_numbers(perf, attack):
    out = {
        "freeze_commit_sha": git("rev-parse", "HEAD"),
        "seed": SEED, "bootstrap_resamples": N_BOOTSTRAP, "confidence_level": 0.95,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kv5": {"perf": {}, "attack_success": {}, "significance_tests": []},
    }
    for m in MITIGATIONS:
        out["kv5"]["perf"][m] = {}
        for c in CONCURRENCIES:
            cell = {}
            for k, vals in perf[m][c].items():
                cell[k] = bootstrap_ci(vals)
            out["kv5"]["perf"][m]["c" + str(c)] = cell
    for m, info in attack.items():
        if info["n"] == 0: continue
        ci = wilson_ci(info["k"], info["n"])
        out["kv5"]["attack_success"][m] = {
            "k": info["k"], "n": info["n"], "source": info["source"],
            "rate": ci["point"], "ci_low": ci["ci_low"], "ci_high": ci["ci_high"],
        }
    for c in CONCURRENCIES:
        base = perf["shared"][c].get("ttft_p50_ms", [])
        for mit in ["isolated", "disabled"]:
            other = perf[mit][c].get("ttft_p50_ms", [])
            if len(base) >= 2 and len(other) >= 2:
                w = welch_t(base, other); d = cohens_d(base, other)
                out["kv5"]["significance_tests"].append({
                    "comparison": "shared vs " + mit + " @ c" + str(c),
                    "metric": "ttft_p50_ms",
                    "n_a": len(base), "n_b": len(other),
                    "mean_a": mean(base), "mean_b": mean(other),
                    "welch_t": w["t"] if w else None, "welch_df": w["df"] if w else None,
                    "p_value": w["p"] if w else None, "cohens_d": d,
                })
    with open(OUT / "paper_numbers_kv.json", "w") as f:
        json.dump(out, f, indent=2)
    print("Wrote " + str(OUT / "paper_numbers_kv.json"))
    return out


def write_table_drafts(perf, attack, sig_tests):
    L = ["# KV6 Paper Table Drafts (auto-generated)", "",
         "Freeze commit: `" + git("rev-parse", "HEAD") + "`", "",
         "Generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), ""]
    L += ["## Table 1. Attack success rate (exact-match PIN reconstruction)", "",
          "| Mitigation | Trials | Exact matches | Rate | Wilson 95% CI |",
          "|---|---|---|---|---|"]
    for m, info in attack.items():
        if info["n"] == 0: continue
        ci = wilson_ci(info["k"], info["n"])
        L.append("| " + m + " | " + str(info["n"]) + " | " + str(info["k"]) + " | " +
                 ("%.3f" % ci["point"]) + " | [" + ("%.3f" % ci["ci_low"]) + ", " +
                 ("%.3f" % ci["ci_high"]) + "] |")
    L.append("")
    L += ["## Table 2. TTFT percentiles (ms) - bootstrap 95% CI", "",
          "| Mitigation | Conc. | TTFT p50 [CI] | TTFT p95 [CI] | TTFT p99 [CI] |",
          "|---|---|---|---|---|"]
    for m in MITIGATIONS:
        for c in CONCURRENCIES:
            row = [m, str(c)]
            for metric in ["ttft_p50_ms", "ttft_p95_ms", "ttft_p99_ms"]:
                vals = perf[m][c].get(metric, [])
                if vals:
                    ci = bootstrap_ci(vals)
                    row.append("%.1f [%.1f, %.1f]" % (ci["point"], ci["ci_low"], ci["ci_high"]))
                else:
                    row.append("-")
            L.append("| " + " | ".join(row) + " |")
    L.append("")
    L += ["## Table 3. Cache-hit rate - bootstrap 95% CI", "",
          "| Mitigation | Conc. | Hit rate [CI] |", "|---|---|---|"]
    for m in MITIGATIONS:
        for c in CONCURRENCIES:
            vals = perf[m][c].get("cache_hit_rate", [])
            if vals:
                ci = bootstrap_ci(vals)
                L.append("| " + m + " | " + str(c) + " | " +
                         ("%.3f [%.3f, %.3f]" % (ci["point"], ci["ci_low"], ci["ci_high"])) + " |")
    L.append("")
    L += ["## Table 4. Throughput (req/s) - bootstrap 95% CI", "",
          "| Mitigation | Conc. | Throughput [CI] |", "|---|---|---|"]
    for m in MITIGATIONS:
        for c in CONCURRENCIES:
            vals = perf[m][c].get("throughput_req_s", [])
            if vals:
                ci = bootstrap_ci(vals)
                L.append("| " + m + " | " + str(c) + " | " +
                         ("%.2f [%.2f, %.2f]" % (ci["point"], ci["ci_low"], ci["ci_high"])) + " |")
    L.append("")
    L += ["## Table 5. Significance tests (Welch t) + effect size (Cohen d)", "",
          "| Comparison | Mean A | Mean B | t | df | p | Cohen d |",
          "|---|---|---|---|---|---|---|"]
    for st in sig_tests:
        L.append("| " + st["comparison"] + " | " +
                 ("%.1f" % st["mean_a"]) + " | " + ("%.1f" % st["mean_b"]) + " | " +
                 ("%+.2f" % st["welch_t"]) + " | " + ("%.1f" % st["welch_df"]) + " | " +
                 ("%.4g" % st["p_value"]) + " | " + ("%+.2f" % st["cohens_d"]) + " |")
    L.append("")
    (OUT / "kv-paper-table-drafts.md").write_text("\n".join(L))
    print("Wrote " + str(OUT / "kv-paper-table-drafts.md"))


def write_environment():
    L = ["# Hardware and Software Environment", "",
         "Generated: " + datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "Host: " + os.uname().nodename, "",
         "## Hardware", "",
         "- GPU: NVIDIA GB10 (DGX Spark)", "- Driver: 580.95.05",
         "- CUDA: 13.0", "- CPU: ARM Cortex-X925 / Cortex-A725",
         "- RAM: 119 Gi", "- OS: Ubuntu 24.04.3 LTS", "",
         "## Software pins", "", "```"]
    for mod, cmd in [("Python", "import sys;print(sys.version.split()[0])"),
                     ("sglang", "import sglang;print(sglang.__version__)"),
                     ("torch", "import torch;print(torch.__version__)"),
                     ("transformers", "import transformers;print(transformers.__version__)"),
                     ("numpy", "import numpy;print(numpy.__version__)"),
                     ("pandas", "import pandas;print(pandas.__version__)"),
                     ("matplotlib", "import matplotlib;print(matplotlib.__version__)")]:
        try:
            o = subprocess.check_output(["python3", "-c", cmd], stderr=subprocess.DEVNULL).decode().strip()
            L.append(mod + ": " + o)
        except Exception:
            L.append(mod + ": (not available)")
    L.append("```")
    (OUT / "environment.md").write_text("\n".join(L))
    print("Wrote " + str(OUT / "environment.md"))


def copy_raw():
    copied = []
    def add(src, dst_dir):
        dst_dir.mkdir(parents=True, exist_ok=True)
        d = dst_dir / src.name
        shutil.copy2(src, d)
        copied.append(d)
    for name in ["pin_chained_shared.csv", "pin_chained_isolated.csv", "pin_chained_disabled.csv"]:
        src = KV2_DIR / name
        if src.exists(): add(src, OUT_RAW / "kv2")
    for run in RUNS:
        d = KV5_V2 / run
        if not d.exists(): continue
        dst = OUT_RAW / "kv5_v2" / run
        for pat in ["perf_*.csv", "perf_*_summary.txt", "security_*.csv"]:
            for f in sorted(d.glob(pat)): add(f, dst)
    for name in ["kv5_tradeoff.csv", "kv5_pareto.png"]:
        src = KV5_V2 / name
        if src.exists(): add(src, OUT_RAW / "kv5_v2")
    if KV4_DIR.exists():
        for f in sorted(KV4_DIR.glob("*")):
            if f.is_file(): add(f, OUT_RAW / "kv4")
    print("Copied " + str(len(copied)) + " raw files into " + str(OUT_RAW))
    return copied


def write_manifest(copied):
    files = [{"path": str(p.relative_to(OUT)), "size": p.stat().st_size, "sha256": sha256_file(p)}
             for p in sorted(copied)]
    for name in ["paper_numbers_kv.json", "kv-paper-table-drafts.md", "environment.md", "reproducibility.md"]:
        p = OUT / name
        if p.exists():
            files.append({"path": name, "size": p.stat().st_size, "sha256": sha256_file(p)})
    m = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "git_sha": git("rev-parse", "HEAD"),
         "git_tag": git("describe", "--tags", "--exact-match") or None,
         "file_count": len(files), "files": files}
    with open(OUT / "manifest.json", "w") as f:
        json.dump(m, f, indent=2)
    print("Wrote " + str(OUT / "manifest.json") + " (" + str(len(files)) + " files)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("Collecting perf data...")
    perf = collect_perf()
    print("Collecting attack-success data...")
    attack = collect_attack_success()
    print("Writing paper_numbers_kv.json...")
    numbers = write_paper_numbers(perf, attack)
    print("Writing table drafts...")
    write_table_drafts(perf, attack, numbers["kv5"]["significance_tests"])
    print("Writing environment...")
    write_environment()
    print("Copying raw files...")
    copied = copy_raw()
    print("Writing manifest...")
    write_manifest(copied)
    print("")
    print("DONE. Artifacts in paper-results/")


if __name__ == "__main__":
    main()
