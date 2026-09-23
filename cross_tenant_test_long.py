"""
cross_tenant_test_long.py — Calculate Cohen's d from LONG template CSV.
Path: results/cross_tenant_verification.csv
Expected d ≈ 0.3400
"""

import pandas as pd
import numpy as np
import os

# Path to the long CSV
CSV_PATH = "results/cross_tenant_verification.csv"

def compute_d_from_csv(csv_path):
    """Compute Cohen's d from a CSV file."""
    
    # Check if file exists
    if not os.path.exists(csv_path):
        print(f"❌ File not found: {csv_path}")
        return None
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    # Check if required columns exist
    required_cols = ['before_ms', 'after_ms']
    for col in required_cols:
        if col not in df.columns:
            print(f"❌ Column '{col}' not found in CSV. Available columns: {list(df.columns)}")
            return None
    
    # Calculate difference
    diff = df['before_ms'] - df['after_ms']
    
    # Calculate Cohen's d (paired)
    d = diff.mean() / diff.std(ddof=1)
    
    # Calculate hit-consistent rate
    hit_consistent = (df['after_ms'] < df['before_ms']).sum()
    total = len(df)
    
    return {
        'd': d,
        'hit_consistent': hit_consistent,
        'total': total,
        'hit_rate': hit_consistent / total * 100,
        'before_mean': df['before_ms'].mean(),
        'after_mean': df['after_ms'].mean(),
        'diff_mean': diff.mean(),
        'diff_std': diff.std(ddof=1),
        'n': total,
        'file': csv_path,
    }

def main():
    print("=" * 60)
    print("LONG TEMPLATE — d VALUE CALCULATION")
    print("=" * 60)
    
    result = compute_d_from_csv(CSV_PATH)
    
    if result:
        print(f"\n✅ File: {result['file']}")
        print(f"   Template: LONG (overwritten variant)")
        print(f"   n = {result['n']}")
        print(f"   Before mean: {result['before_mean']:.1f} ms")
        print(f"   After mean:  {result['after_mean']:.1f} ms")
        print(f"   Difference mean: {result['diff_mean']:.1f} ms")
        print(f"   Difference std:  {result['diff_std']:.1f} ms")
        print(f"   Cohen's d (paired): {result['d']:.4f}")
        print(f"   Hit-consistent: {result['hit_consistent']}/{result['total']} ({result['hit_rate']:.1f}%)")
        print("\n" + "=" * 60)
        print(f"✅ VERIFIED: Long template d = {result['d']:.4f}")
        print("=" * 60)
    else:
        print("\n❌ Failed to compute d value")

if __name__ == "__main__":
    main()
