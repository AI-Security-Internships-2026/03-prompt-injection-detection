"""run_detector.py — KV4 Section 4 detector eval. Sliding-window LCP-ratio +
Hamming-mutation-density classifier over any CSV with prompt+timestamp
columns (attack: adaptive_attacker.py output; legitimate: generate_legitimate_workloads.py
output). Non-overlapping windows (stride=window_size)."""
import argparse, itertools
import pandas as pd
import numpy as np

WINDOW_SIZE = 10

def lcp_len(s1, s2):
    n = min(len(s1), len(s2))
    i = 0
    while i < n and s1[i] == s2[i]:
        i += 1
    return i

def window_features(prompts):
    lcp_ratios, mut_flags = [], []
    for i in range(len(prompts) - 1):
        p1, p2 = str(prompts[i]), str(prompts[i+1])
        l = lcp_len(p1, p2)
        m = max(len(p1), len(p2))
        if m > 0:
            lcp_ratios.append(l / m)
        diff = abs(len(p1) - len(p2)) + sum(a != b for a, b in zip(p1, p2))
        mut_flags.append(1 if 1 <= diff <= 8 else 0)
    return (float(np.mean(lcp_ratios)) if lcp_ratios else 0.0,
            float(np.mean(mut_flags)) if mut_flags else 0.0)

def classify(mean_lcp, mut_density, lcp_thresh, mut_thresh):
    return mean_lcp >= lcp_thresh and mut_density > mut_thresh

def score_file(path, is_attack, lcp_thresh, mut_thresh):
    df = pd.read_csv(path)
    prompts = df["prompt"].astype(str).tolist()
    flags = []
    for i in range(0, len(prompts) - WINDOW_SIZE + 1, WINDOW_SIZE):
        window = prompts[i:i+WINDOW_SIZE]
        lcp, mut = window_features(window)
        flags.append(classify(lcp, mut, lcp_thresh, mut_thresh))
    return flags

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--attack-csvs", nargs="+", required=True)
    p.add_argument("--legit-csvs", nargs="+", required=True)
    p.add_argument("--lcp-thresh", type=float, default=0.9)
    p.add_argument("--mut-thresh", type=float, default=0.0)
    p.add_argument("--sweep", action="store_true", help="sweep thresholds instead of using fixed values")
    p.add_argument("--out", required=True)
    a = p.parse_args()

    thresholds = [(l, m) for l in [0.7,0.8,0.9,0.95] for m in [0.0,0.1,0.3]] if a.sweep else [(a.lcp_thresh, a.mut_thresh)]

    with open(a.out, "w") as f:
        for lcp_t, mut_t in thresholds:
            tp = fp = tn = fn = 0
            for c in a.attack_csvs:
                flags = score_file(c, True, lcp_t, mut_t)
                tp += sum(flags); fn += len(flags) - sum(flags)
            for c in a.legit_csvs:
                flags = score_file(c, False, lcp_t, mut_t)
                fp += sum(flags); tn += len(flags) - sum(flags)
            prec = tp / (tp + fp) if (tp + fp) else float('nan')
            rec = tp / (tp + fn) if (tp + fn) else float('nan')
            f1 = 2*prec*rec/(prec+rec) if prec and rec and (prec+rec) else float('nan')
            fpr = fp / (fp + tn) if (fp + tn) else float('nan')
            f.write(f"lcp_thresh={lcp_t} mut_thresh={mut_t} | TP={tp} FP={fp} TN={tn} FN={fn} "
                    f"precision={prec:.3f} recall={rec:.3f} f1={f1:.3f} fpr={fpr:.3f}\n")
    print(f"Wrote {a.out}")

if __name__ == "__main__":
    main()
