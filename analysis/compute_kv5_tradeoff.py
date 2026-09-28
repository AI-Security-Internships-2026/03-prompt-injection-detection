#!/usr/bin/env python3
"""compute_kv5_tradeoff.py (V3) — joins security (attack success, cache-hit
reuse) with performance (TTFT, latency, throughput) across mitigations and
concurrency levels; produces the Pareto figure from the CSVs.

V3 fix: baseline attack success is COMPUTED from the KV2 raw CSV
(results/sglang/kv2/pin_chained_shared.csv) by applying the original
attacker's argmax-on-cached_tokens reconstruction per trial, then comparing
to ground_truth_pin. tenant_isolated and disabled attack success is computed
from the KV5 security CSVs via per-trial exact-match on position_correct.
"""
import argparse, csv, os
import numpy as np
import pandas as pd

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAVE_MPL = True
except ImportError:
    HAVE_MPL = False

KV2_BASELINE_CSV = "results/sglang/kv2/pin_chained_shared.csv"
KV5_SEC_DIR = "results/kv5_v2/run1"
KV5_SEC_FILES = {
    "tenant_isolated": "security_tenant_isolated.csv",
    "disabled":        "security_disabled.csv",
}


def kv2_reconstruction_rate(path):
    """Apply the original attacker's argmax-on-cached_tokens reconstruction,
    compare to ground_truth_pin, return exact-match rate."""
    df = pd.read_csv(path)
    trials = sorted(df["trial"].unique())
    exact = 0
    for t in trials:
        sub = df[df["trial"] == t]
        reconstructed = []
        for pos in sorted(sub["position"].unique()):
            pos_rows = sub[sub["position"] == pos]
            best = pos_rows.loc[pos_rows["cached_tokens"].idxmax(), "guess_digit"]
            reconstructed.append(str(int(best)))
        inferred = "".join(reconstructed)
        gt = str(int(sub["ground_truth_pin"].iloc[0]))
        if inferred == gt:
            exact += 1
    return exact / len(trials), len(trials)


def kv5_exact_match_rate(path):
    df = pd.read_csv(path)
    if df.empty or "position_correct" not in df.columns:
        return None, None
    pc = df["position_correct"].astype(str).str.lower() == "true"
    per_trial = df.assign(_pc=pc).groupby("trial")["_pc"].all()
    return float(per_trial.mean()), int(len(per_trial))


def get_attack_success(mitigation):
    if mitigation == "shared":
        if not os.path.exists(KV2_BASELINE_CSV):
            return None, None, "missing KV2 baseline"
        rate, n = kv2_reconstruction_rate(KV2_BASELINE_CSV)
        return rate, n, KV2_BASELINE_CSV
    if mitigation in KV5_SEC_FILES:
        p = os.path.join(KV5_SEC_DIR, KV5_SEC_FILES[mitigation])
        if not os.path.exists(p):
            return None, None, f"missing {p}"
        rate, n = kv5_exact_match_rate(p)
        return rate, n, p
    return None, None, "unknown mitigation"


def pct(sorted_vals, p_):
    if not sorted_vals:
        return None
    idx = min(int(len(sorted_vals) * p_ / 100), len(sorted_vals) - 1)
    return sorted_vals[idx]


def read_perf_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    cols = rows[0].keys()
    if "ttft_ms" in cols:
        return {
            "schema": "v2",
            "ttft_ms": [float(r["ttft_ms"]) for r in rows],
            "total_latency_ms": [float(r["total_latency_ms"]) for r in rows],
            "cached": [r.get("cached_tokens_ttft_req") for r in rows],
        }
    elif "latency_ms" in cols:
        return {
            "schema": "legacy",
            "ttft_ms": [float(r["latency_ms"]) for r in rows],
            "total_latency_ms": None,
            "cached": [r.get("cached_tokens") for r in rows],
        }
    return None


def cache_hit_rate(cached_list):
    vals = [c for c in cached_list if c not in (None, "", "None")]
    if not vals:
        return None
    hits = sum(1 for v in vals if float(v) > 0)
    return hits / len(vals)


def collect_perf(base_dir, mitigation, concurrency_levels, run_dirs):
    out = {}
    for c in concurrency_levels:
        ttft_by_repeat, full_by_repeat, thr_by_repeat, hr_by_repeat = [], [], [], []
        n_excluded = 0
        schema_seen = set()
        for rd in run_dirs:
            fname = f"perf_{mitigation}_c{c}.csv"
            path = os.path.join(base_dir, rd, fname) if rd else os.path.join(base_dir, fname)
            if not os.path.exists(path):
                n_excluded += 1; continue
            data = read_perf_csv(path)
            if data is None:
                n_excluded += 1; continue
            schema_seen.add(data["schema"])
            ts = sorted(data["ttft_ms"])
            ttft_by_repeat.append((pct(ts, 50), pct(ts, 95), pct(ts, 99)))
            if data["total_latency_ms"] is not None:
                fs = sorted(data["total_latency_ms"])
                full_by_repeat.append((pct(fs, 50), pct(fs, 95), pct(fs, 99)))
            hr = cache_hit_rate(data["cached"])
            if hr is not None:
                hr_by_repeat.append(hr)
            sp = path.replace(".csv", "_summary.txt")
            if os.path.exists(sp):
                for line in open(sp):
                    if "throughput_req_s" in line:
                        try:
                            thr_by_repeat.append(float(line.split("throughput_req_s=")[1].split()[0]))
                        except (IndexError, ValueError):
                            pass

        def ms(vals):
            if not vals:
                return (None, None)
            a = np.array(vals, dtype=float)
            return (float(a.mean()), float(a.std(ddof=1)) if len(a) > 1 else 0.0)

        out[c] = {
            "schema": sorted(schema_seen),
            "n_valid_repeats": len(ttft_by_repeat),
            "n_excluded_repeats": n_excluded,
            "ttft_p50_ms": ms([x[0] for x in ttft_by_repeat]),
            "ttft_p95_ms": ms([x[1] for x in ttft_by_repeat]),
            "ttft_p99_ms": ms([x[2] for x in ttft_by_repeat]),
            "full_latency_p50_ms": ms([x[0] for x in full_by_repeat]) if full_by_repeat else (None, None),
            "full_latency_p99_ms": ms([x[2] for x in full_by_repeat]) if full_by_repeat else (None, None),
            "throughput_req_s": ms(thr_by_repeat),
            "cache_hit_rate": ms(hr_by_repeat),
        }
    return out


PERF_NAME_MAP = {"shared": "shared", "tenant_isolated": "isolated", "disabled": "disabled"}


def build_table(base_dir, mitigations, concurrencies, run_dirs, out_csv):
    rows = []
    for mit in mitigations:
        pm = PERF_NAME_MAP.get(mit, mit)
        rate, n_trials, src = get_attack_success(mit)
        print(f"  {mit}: attack_success={rate} (n_trials={n_trials}, source={src})")
        perf = collect_perf(base_dir, pm, concurrencies, run_dirs)
        for c, m in perf.items():
            rows.append({
                "mitigation": mit,
                "concurrency": c,
                "attack_success_mean": rate,
                "attack_success_std": 0.0 if rate is not None else None,
                "attack_n_trials": n_trials,
                "attack_source": src,
                "schema": ";".join(m["schema"]),
                "n_valid_perf_repeats": m["n_valid_repeats"],
                "n_excluded_perf_repeats": m["n_excluded_repeats"],
                "ttft_p50_ms_mean": m["ttft_p50_ms"][0], "ttft_p50_ms_std": m["ttft_p50_ms"][1],
                "ttft_p95_ms_mean": m["ttft_p95_ms"][0], "ttft_p95_ms_std": m["ttft_p95_ms"][1],
                "ttft_p99_ms_mean": m["ttft_p99_ms"][0], "ttft_p99_ms_std": m["ttft_p99_ms"][1],
                "full_latency_p50_ms_mean": m["full_latency_p50_ms"][0], "full_latency_p50_ms_std": m["full_latency_p50_ms"][1],
                "full_latency_p99_ms_mean": m["full_latency_p99_ms"][0], "full_latency_p99_ms_std": m["full_latency_p99_ms"][1],
                "throughput_mean": m["throughput_req_s"][0], "throughput_std": m["throughput_req_s"][1],
                "cache_hit_rate_mean": m["cache_hit_rate"][0], "cache_hit_rate_std": m["cache_hit_rate"][1],
            })
    if rows:
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    print(f"Wrote {out_csv} ({len(rows)} rows)")
    return rows


def pareto(rows, out_png):
    if not HAVE_MPL:
        print("matplotlib not available — skipping figure"); return
    fig, ax = plt.subplots(figsize=(7, 5))
    markers = {"shared": "o", "tenant_isolated": "s", "disabled": "^"}
    colors = {"shared": "#c0392b", "tenant_isolated": "#2980b9", "disabled": "#27ae60"}
    plotted = False
    for r in rows:
        x, y = r["ttft_p99_ms_mean"], r["attack_success_mean"]
        if x is None or y is None: continue
        m = r["mitigation"]
        ax.scatter(x, y, marker=markers.get(m, "x"), color=colors.get(m, "gray"),
                   s=90, label=f"{m} (c={r['concurrency']})", edgecolors="black")
        ax.annotate(f"c={r['concurrency']}", (x, y), textcoords="offset points",
                    xytext=(6, 4), fontsize=8)
        plotted = True
    if not plotted:
        print("No rows with both ttft and attack success — figure skipped"); return
    ax.set_xlabel("p99 TTFT (ms)  [lower is better]")
    ax.set_ylabel("Attack success rate  [lower is better]")
    ax.set_title("KV5 Security-Performance Trade-off (Pareto)")
    h, l = ax.get_legend_handles_labels()
    by = dict(zip(l, h))
    ax.legend(by.values(), by.keys(), fontsize=7, loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"Wrote {out_png}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base-dir", required=True)
    p.add_argument("--mitigations", nargs="+", default=["shared", "tenant_isolated", "disabled"])
    p.add_argument("--concurrency-levels", type=int, nargs="+", default=[1, 10, 25])
    p.add_argument("--run-dirs", nargs="+", default=["run1", "run2", "run3"])
    p.add_argument("--out-csv", required=True)
    p.add_argument("--out-png", required=True)
    a = p.parse_args()
    rows = build_table(a.base_dir, a.mitigations, a.concurrency_levels, a.run_dirs, a.out_csv)
    pareto(rows, a.out_png)


if __name__ == "__main__":
    main()
