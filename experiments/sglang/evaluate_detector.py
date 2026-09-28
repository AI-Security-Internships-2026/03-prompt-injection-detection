import pandas as pd
import numpy as np
import os
import difflib

def calculate_lcp(s1, s2):
    """Calculate length of Longest Common Prefix (LCP) between two strings."""
    match = difflib.SequenceMatcher(None, s1, s2).find_longest_match(0, len(s1), 0, len(s2))
    return match.size if match.a == 0 and match.b == 0 else 0

def detect_probe_signature(df_window, rate_threshold=5, lcp_threshold=0.9):
    """
    Apply D(W) mathematical model to a window of requests.
    Returns True if classified as an attack, False otherwise.
    """
    if len(df_window) < 2:
        return False
        
    time_span = df_window['timestamp'].max() - df_window['timestamp'].min()
    rate = len(df_window) / time_span if time_span > 0 else len(df_window)
    
    if rate < rate_threshold:
        return False
        
    lcp_ratios = []
    mutation_flags = []
    prompts = df_window['prompt'].tolist()
    
    for i in range(len(prompts) - 1):
        p1, p2 = str(prompts[i]), str(prompts[i+1])
        lcp_len = calculate_lcp(p1, p2)
        max_len = max(len(p1), len(p2))
        if max_len > 0:
            lcp_ratios.append(lcp_len / max_len)
            
        suffix_diff = max_len - lcp_len
        # The attacker changes 1 digit at the end, so difference is very small
        mutation_flags.append(1 if 1 <= suffix_diff <= 5 else 0) 
        
    mean_lcp = np.mean(lcp_ratios) if lcp_ratios else 0
    mutation_density = np.mean(mutation_flags) if mutation_flags else 0
    
    # Composite threshold
    if mean_lcp >= lcp_threshold and mutation_density > 0.8:
        return True
    return False

def run_evaluation():
    attack_file = "results/sglang/pin_chained_recovery.csv"
    if not os.path.exists(attack_file):
        print(f"Error: {attack_file} not found.")
        return
        
    df_attack = pd.read_csv(attack_file)
    
    # SAFELY reconstruct the prompt string by forcing string types
    prefix = df_attack['known_prefix_so_far'].fillna('').astype(str).replace('nan', '')
    guess = df_attack['guess_digit'].fillna('').astype(str).replace('nan', '')
    df_attack['prompt'] = prefix + guess
    
    # Simulate attacker burst rate (10 req/sec)
    df_attack['timestamp'] = np.arange(len(df_attack)) * 0.1 
    df_attack['label'] = 1
    
    # Generate Synthetic Normal Traffic
    normal_prompts = [
        "What is the weather today?", "Summarize this financial report.",
        "Translate 'hello' to French.", "Write a Python script for sorting.",
        "Explain quantum computing.", "How do I bake a chocolate cake?",
        "What is the capital of Japan?", "Debug this React component."
    ] * 25 # 200 normal requests
    
    df_normal = pd.DataFrame({
        'prompt': normal_prompts,
        'timestamp': np.arange(len(normal_prompts)) * 2.5, # Normal user rate (1 req / 2.5 sec)
        'label': 0
    })
    
    window_size = 10
    y_true = []
    y_pred = []
    
    print("Evaluating Attack Traffic Windows...")
    for i in range(len(df_attack) - window_size):
        window = df_attack.iloc[i:i+window_size]
        is_attack = detect_probe_signature(window)
        y_true.append(1)
        y_pred.append(1 if is_attack else 0)
        
    print("Evaluating Normal Traffic Windows...")
    for i in range(len(df_normal) - window_size):
        window = df_normal.iloc[i:i+window_size]
        is_attack = detect_probe_signature(window)
        y_true.append(0)
        y_pred.append(1 if is_attack else 0)
        
    # Calculate Metrics
    tp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 1)
    tn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 0)
    fp = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 0 and yp == 1)
    fn = sum(1 for yt, yp in zip(y_true, y_pred) if yt == 1 and yp == 0)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    print("\n=== DETECTION BASELINE RESULTS ===")
    print(f"True Positives (Attack windows caught): {tp}")
    print(f"False Positives (Normal windows flagged): {fp}")
    print(f"True Negatives (Normal windows ignored): {tn}")
    print(f"False Negatives (Attack windows missed): {fn}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print("==================================\n")

if __name__ == "__main__":
    run_evaluation()
