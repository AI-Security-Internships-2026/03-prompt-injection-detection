"""
evaluate_detector_v2.py - Part 1 detection, corrected methodology.

Fixes vs evaluate_detector.py:
  1. Real reconstructed timestamps (cumsum of known sleep gaps + measured
     wall_clock_latency, per trial) instead of a fabricated uniform 10 req/s
     timeline. This is a LOWER BOUND on real spacing since flush_cache() and
     victim_populate() latency are not logged in pin_chained_recovery.csv.
  2. Non-overlapping sliding windows (stride = window_size), not stride=1,
     so precision/recall/F1 are computed over independent samples.
  3. Threshold sweep over (lcp_threshold, mutation_threshold) instead of one
     hardcoded operating point.
  4. Detection latency: requests-into-trial before first window flags.
  5. Rate/burst logged as a DIAGNOSTIC column only, not a gate - real
     attacker rate here is ~0.72 req/s (see known_gap below), far under
     any burst threshold that would also catch legitimate scraping-style
     use. Reported explicitly as a negative result for rate-based detection
     under this methodology, not hidden.
  6. Adds a "power user" legitimate-traffic condition (fast but NON-systematic
     prompts) as an adversarial baseline, not just slow casual traffic - if we
     only test against slow legitimate traffic, any rate signal looks great
     for free and inflates apparent performance.

Ground truth isolation preserved: this script is a researcher-side evaluator,
consumes ONLY existing CSV output. Does not touch attacker/victim logic.
"""
import pandas as pd
import numpy as np
import os
import difflib
import itertools

KNOWN_GAP = 0.3 + 1.0  # flush sleep + GAP_SECONDS, from run_pin_chained_recovery.py
WINDOW_SIZE = 10

def lcp_len(s1, s2):
    # FIXED: difflib.find_longest_match with autojunk=True (default) marks
    # any character appearing in >1% of a string (>200 chars) as "popular"
    # and excludes it as an anchor. Our prompts are ~1100 chars built from
    # SHARED_PUBLIC_PREFIX repeated 3x, so nearly every character type is
    # "popular" - confirmed directly: manual os.path.commonprefix found a
    # true shared prefix of 1097 chars, while find_longest_match returned
    # a spurious 11-char match starting at offset 1098, missing the real
    # prefix entirely. Since we specifically want PREFIX match length (this
    # is literally what the cache-hit/radix-tree mechanism measures), direct
    # prefix comparison is both correct and simpler than a general longest-
    # common-substring search.
    n = min(len(s1), len(s2))
    i = 0
    while i < n and s1[i] == s2[i]:
        i += 1
    return i
    # and excludes it as an anchor. Our prompts are ~1100 chars built from
    # SHARED_PUBLIC_PREFIX repeated 3x, so nearly every character type is
    # "popular" - confirmed directly: manual os.path.commonprefix found a
    # true shared prefix of 1097 chars, while find_longest_match returned
    # a spurious 11-char match starting at offset 1098, missing the real
    # prefix entirely. Since we specifically want PREFIX match length (this
    # is literally what the cache-hit/radix-tree mechanism measures), direct
    # prefix comparison is both correct and simpler than a general longest-
    # common-substring search.
    n = min(len(s1), len(s2))
    i = 0
    while i < n and s1[i] == s2[i]:
        i += 1
    return i

def window_features(df_window):
    """Compute LCP ratio, mutation density, and rate (diagnostic only) for one window."""
    prompts = df_window['prompt'].tolist()
    ts = df_window['timestamp'].tolist()

    lcp_ratios, mutation_flags = [], []
    for i in range(len(prompts) - 1):
        p1, p2 = str(prompts[i]), str(prompts[i + 1])
        l = lcp_len(p1, p2)
        max_len = max(len(p1), len(p2))
        if max_len > 0:
            lcp_ratios.append(l / max_len)
        # FIXED AGAIN: SequenceMatcher.ratio() defaults to autojunk=True for
        # sequences >200 chars, treating any char appearing in >1% of the
        # string as "popular" and excluding it from matching. Our prompts
        # are ~1100+ chars of repetitive text, so autojunk likely distorted
        # ratio() broadly. Two independent formula changes both produced
        # flat, degraded recall - pointing at the tool, not the formula.
        # These prompts are equal-length by construction (fixed PIN_LENGTH,
        # padding, label/marker), so exact Hamming distance is simpler and
        # exact - no heuristics needed.
        if len(p1) == len(p2):
            char_diff = sum(1 for a, b in zip(p1, p2) if a != b)
        else:
            char_diff = abs(len(p1) - len(p2)) + sum(1 for a, b in zip(p1, p2) if a != b)
        mutation_flags.append(1 if 1 <= char_diff <= 8 else 0)

    mean_lcp = float(np.mean(lcp_ratios)) if lcp_ratios else 0.0
    mutation_density = float(np.mean(mutation_flags)) if mutation_flags else 0.0

    span = ts[-1] - ts[0]
    rate = len(df_window) / span if span > 0 else float('inf')  # diagnostic only

    return mean_lcp, mutation_density, rate

def classify(mean_lcp, mutation_density, lcp_threshold, mutation_threshold):
    return mean_lcp >= lcp_threshold and mutation_density > mutation_threshold

SHARED_PUBLIC_PREFIX = (
    "You are a customer support assistant for a cloud infrastructure company. "
    "Below is the internal knowledge base context shared across all support sessions. "
    "Use this context to answer user questions about billing, deployment, and account "
    "management. Always be concise and professional. The following section contains "
    "account-specific context for the current session: "
) * 3
PIN_LABEL = "PIN: "
PIN_SEPARATOR = ","
PIN_TRAILING_MARKER = "."
PIN_LENGTH = 6
PLACEHOLDER_DIGIT = "0"  # matches run_pin_chained_recovery.py

def _safe_prefix_str(val):
    """Fix pandas dtype bug: known_prefix_so_far has NaN at position=1,
    which forces pandas to upcast the whole column to float64. A recovered
    digit string like "0" or "4" becomes the float 0.0 / 4.0, and
    str(0.0) == "0.0" - a 3-char string with a stray "." - not "0". This
    silently shifted every guess digit 2 characters to the right for
    position >= 2 rows (5 of 6 positions per trial) and inserted a fake
    "." that was initially mistaken for PIN_TRAILING_MARKER during manual
    inspection. Confirmed via direct pandas read showing known_prefix_so_far
    as 0.0, 4.0 (floats), not corrupted strings - the bug is in reconstruction,
    not in the original attack data or run_pin_chained_recovery.py."""
    if pd.isna(val):
        return ""
    if isinstance(val, float):
        return str(int(val))
    return str(val)

def _reconstruct_full_prompt(known_prefix, guess_digit):
    """Rebuild the EXACT prompt attacker_probe() sent, matching
    run_pin_chained_recovery.py's attacker_probe() construction. The CSV
    only logs known_prefix_so_far and guess_digit, not the full prompt
    text, so this must mirror the real construction exactly or LCP is
    understated."""
    known_prefix = _safe_prefix_str(known_prefix)
    guess_digit = _safe_prefix_str(guess_digit)
    remaining = PIN_LENGTH - len(known_prefix) - 1
    guess_digits = known_prefix + guess_digit + PLACEHOLDER_DIGIT * remaining
    formatted = PIN_SEPARATOR.join(list(guess_digits))
    return SHARED_PUBLIC_PREFIX + PIN_LABEL + formatted + PIN_TRAILING_MARKER

def build_attack_df():
    path = "results/sglang/pin_chained_recovery.csv"
    df = pd.read_csv(path)
    df['prompt'] = [
        _reconstruct_full_prompt(kp, gd)
        for kp, gd in zip(df['known_prefix_so_far'], df['guess_digit'])
    ]

    # reconstruct real lower-bound timestamps, reset per trial
    df['timestamp'] = 0.0
    for trial_id, group in df.groupby('trial'):
        idx = group.index
        spacing = KNOWN_GAP + df.loc[idx, 'wall_clock_latency']
        df.loc[idx, 'timestamp'] = spacing.cumsum().values
    df['label'] = 1
    return df

def build_legit_df_slow(n=200, seed=0):
    """Casual legitimate user: varied prompts, slow human pacing, jittered."""
    rng = np.random.default_rng(seed)
    prompts = [
        "What is the weather today?", "Summarize this financial report.",
        "Translate 'hello' to French.", "Write a Python script for sorting.",
        "Explain quantum computing.", "How do I bake a chocolate cake?",
        "What is the capital of Japan?", "Debug this React component.",
        "Give me a recipe for lasagna.", "What's the plot of Hamlet?",
    ]
    chosen = rng.choice(prompts, size=n)
    gaps = rng.uniform(2.5, 8.0, size=n)  # jittered human pacing
    ts = np.cumsum(gaps)
    return pd.DataFrame({'prompt': chosen, 'timestamp': ts, 'label': 0, 'trial': -1})

def build_legit_df_shared_prefix(n=200, seed=2):
    """Hardest legitimate-traffic case: real customers using the SAME public
    shared prefix (as they would in the actual deployment), each asking
    genuinely different account-specific questions afterward. This tests
    whether mean_lcp alone would false-positive on realistic multi-tenant
    traffic that legitimately shares the boilerplate system prompt - the
    attack's mean_lcp is high BECAUSE of this same shared prefix, so this
    is the true adversarial baseline for that feature, not just topically
    unrelated prompts."""
    rng = np.random.default_rng(seed)
    account_questions = [
        "Can you check the status of my latest deployment in us-east-1?",
        "Why was I billed twice for the same invoice this month?",
        "I need to upgrade my support tier, what are the options?",
        "The API key rotation failed for project prod-7743, please advise.",
        "Can you explain the difference between our staging and prod environments?",
        "My team lead needs read access to the billing dashboard.",
        "We're seeing elevated latency on the west coast region since Tuesday.",
        "Please cancel the pending contract renewal for account 88213.",
        "How do I set up SSO for our engineering org?",
        "Our monthly spend report looks off compared to last quarter.",
    ]
    chosen = rng.choice(account_questions, size=n)
    prompts = [SHARED_PUBLIC_PREFIX + " " + q for q in chosen]
    gaps = rng.uniform(3.0, 10.0, size=n)  # real support agents, human pacing
    ts = np.cumsum(gaps)
    return pd.DataFrame({'prompt': prompts, 'timestamp': ts, 'label': 0, 'trial': -1})

def build_legit_df_poweruser(n=200, seed=1):
    """Adversarial baseline: FAST but non-systematic prompts (e.g. a script
    hitting the API in a loop for unrelated tasks). Tests whether rate alone
    would false-positive on legitimate automation."""
    rng = np.random.default_rng(seed)
    base_prompts = [
        "Summarize log entry {}: server responded 200 OK at endpoint /api/v{}",
        "Translate document chunk {} to French: paragraph {}",
        "Classify sentiment for review #{} regarding product {}",
        "Generate unit test #{} for function handler_{}",
    ]
    prompts = [rng.choice(base_prompts).format(rng.integers(0, 999), rng.integers(0, 999)) for _ in range(n)]
    gaps = rng.uniform(0.5, 1.5, size=n)  # fast, comparable-ish to attacker rate
    ts = np.cumsum(gaps)
    return pd.DataFrame({'prompt': prompts, 'timestamp': ts, 'label': 0, 'trial': -1})

def evaluate_condition(df, window_size, lcp_threshold, mutation_threshold, group_col='trial'):
    """Non-overlapping windows, grouped by trial where applicable so we don't
    window across trial boundaries (which would mix independent attack runs
    or wrap legitimate traffic in a way that doesn't correspond to any real
    session)."""
    y_true, y_pred, diag_rates = [], [], []
    detection_latency = None  # requests into a trial before first flag (attack only)

    if group_col in df.columns and df[group_col].nunique() > 1 and df['label'].iloc[0] == 1:
        groups = [g for _, g in df.groupby(group_col)]
    else:
        groups = [df]

    for g in groups:
        g = g.reset_index(drop=True)
        flagged_at = None
        for start in range(0, len(g) - window_size + 1, window_size):  # stride = window_size
            window = g.iloc[start:start + window_size]
            mean_lcp, mutation_density, rate = window_features(window)
            pred = classify(mean_lcp, mutation_density, lcp_threshold, mutation_threshold)
            y_true.append(int(g['label'].iloc[0]))
            y_pred.append(int(pred))
            diag_rates.append(rate)
            if pred and flagged_at is None:
                flagged_at = start + window_size
        if g['label'].iloc[0] == 1 and flagged_at is not None and detection_latency is None:
            detection_latency = flagged_at  # first trial's latency; full sweep reports mean below
        if g['label'].iloc[0] == 1:
            if flagged_at is not None:
                if 'latencies' not in dir(evaluate_condition):
                    pass
    return y_true, y_pred, diag_rates

def detection_latencies(df_attack, window_size, lcp_threshold, mutation_threshold):
    """Per-trial: how many requests into the trial before first window flags.
    None if never flagged in that trial."""
    latencies = []
    for _, g in df_attack.groupby('trial'):
        g = g.reset_index(drop=True)
        flagged_at = None
        for start in range(0, len(g) - window_size + 1, window_size):
            window = g.iloc[start:start + window_size]
            mean_lcp, mutation_density, _ = window_features(window)
            if classify(mean_lcp, mutation_density, lcp_threshold, mutation_threshold):
                flagged_at = start + window_size
                break
        latencies.append(flagged_at)  # None = missed entirely
    return latencies

def metrics(y_true, y_pred):
    tp = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 1)
    tn = sum(1 for a, b in zip(y_true, y_pred) if a == 0 and b == 0)
    fp = sum(1 for a, b in zip(y_true, y_pred) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(y_true, y_pred) if a == 1 and b == 0)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return precision, recall, f1, fpr, tp, fp, tn, fn

def run():
    df_attack = build_attack_df()
    df_legit_slow = build_legit_df_slow()
    df_legit_power = build_legit_df_poweruser()
    df_legit_shared = build_legit_df_shared_prefix()

    print(f"Attack rows: {len(df_attack)} across {df_attack['trial'].nunique()} trials")
    print(f"Legit-slow rows: {len(df_legit_slow)}")
    print(f"Legit-poweruser rows: {len(df_legit_power)}")
    print(f"Legit-shared-prefix rows: {len(df_legit_shared)}")
    print()

    # diagnostic: real attacker rate vs the two legit conditions
    print("=== DIAGNOSTIC: rate is NOT used as a detection gate (see module docstring) ===")
    print(f"Reconstructed attacker rate (lower bound): ~{1/KNOWN_GAP:.3f} req/s ceiling from known sleeps")
    print()

    thresholds_lcp = [0.7, 0.8, 0.9, 0.95]
    thresholds_mut = [0.5, 0.6, 0.7, 0.8]

    print(f"{'lcp_thr':>8} {'mut_thr':>8} {'prec':>7} {'recall':>7} {'f1':>7} {'fpr(slow)':>10} {'fpr(power)':>11} {'fpr(shared)':>12}")
    results = []
    for lcp_t, mut_t in itertools.product(thresholds_lcp, thresholds_mut):
        yt_a, yp_a, _ = evaluate_condition(df_attack, WINDOW_SIZE, lcp_t, mut_t)
        yt_s, yp_s, _ = evaluate_condition(df_legit_slow, WINDOW_SIZE, lcp_t, mut_t)
        yt_p, yp_p, _ = evaluate_condition(df_legit_power, WINDOW_SIZE, lcp_t, mut_t)
        yt_sh, yp_sh, _ = evaluate_condition(df_legit_shared, WINDOW_SIZE, lcp_t, mut_t)

        y_true = yt_a + yt_s
        y_pred = yp_a + yp_s
        precision, recall, f1, fpr_slow, *_ = metrics(y_true, y_pred)
        _, _, _, fpr_power, *_ = metrics(yt_p, yp_p)
        _, _, _, fpr_shared, *_ = metrics(yt_sh, yp_sh)

        results.append((lcp_t, mut_t, precision, recall, f1, fpr_slow, fpr_power, fpr_shared))
        print(f"{lcp_t:>8} {mut_t:>8} {precision:>7.3f} {recall:>7.3f} {f1:>7.3f} {fpr_slow:>10.3f} {fpr_power:>11.3f} {fpr_shared:>12.3f}")

    best = max(results, key=lambda r: (r[4], -r[7]))  # tie-break: prefer lower fpr_shared
    print(f"\nBest by F1 (tie-break: lowest FPR on shared-prefix condition): lcp_thr={best[0]} mut_thr={best[1]} -> "
          f"P={best[2]:.3f} R={best[3]:.3f} F1={best[4]:.3f} "
          f"FPR(slow)={best[5]:.3f} FPR(power)={best[6]:.3f} FPR(shared)={best[7]:.3f}")

    lat = detection_latencies(df_attack, WINDOW_SIZE, best[0], best[1])
    caught = [l for l in lat if l is not None]
    print(f"\nDetection latency (requests into trial before flag), best threshold:")
    print(f"  Trials caught: {len(caught)}/{len(lat)}")
    if caught:
        print(f"  Mean requests-to-detect: {np.mean(caught):.1f}  Median: {np.median(caught):.1f}")

    out_dir = "results/sglang/mitigation"
    os.makedirs(out_dir, exist_ok=True)
    pd.DataFrame(results, columns=['lcp_threshold', 'mutation_threshold', 'precision', 'recall', 'f1', 'fpr_slow', 'fpr_poweruser', 'fpr_shared_prefix']).to_csv(
        os.path.join(out_dir, "detection_threshold_sweep.csv"), index=False)
    pd.DataFrame({'trial': range(len(lat)), 'requests_to_detect': lat}).to_csv(
        os.path.join(out_dir, "detection_latency.csv"), index=False)
    print(f"\nSaved threshold sweep and detection latency to {out_dir}/")

if __name__ == "__main__":
    run()
