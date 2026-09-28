import csv, os, time

FIELDS = ["candidate", "trial_batch", "ttft_mean_ms", "ttft_stdev_ms",
          "predicted", "confidence", "ground_truth_match", "tenant",
          "timestamp", "secret_category"]

def init_log(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()

def log_row(path, **kwargs):
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        row = {k: kwargs.get(k, "") for k in FIELDS}
        row["timestamp"] = time.time()
        w.writerow(row)
