import random, string, sys
sys.path.insert(0, ".")
from experiments.phase4.secrets import SECRET_GENERATORS
from experiments.phase4.harness import victim_populate_cache
from experiments.phase4.measure import calibrate_threshold, classify_with_confidence
from experiments.phase4.logger import init_log, log_row

LOG_PATH = "results/phase4/ablation_results.csv"
TRIAL_COUNTS = [1, 3, 5, 10]
N_SECRETS_PER_CATEGORY = 5

def run():
    init_log(LOG_PATH)
    for category, gen_fn in SECRET_GENERATORS.items():
        for _ in range(N_SECRETS_PER_CATEGORY):
            gt = gen_fn()
            placeholder = "".join(random.choice(string.ascii_lowercase) for _ in range(len(gt.secret)))
            calib = calibrate_threshold(gt.template, placeholder, n_baseline=10)

            for n_trials in TRIAL_COUNTS:
                result_before = classify_with_confidence(gt.template, gt.secret, calib["threshold_ms"], n_trials)
                log_row(LOG_PATH, candidate=gt.secret, trial_batch=n_trials,
                        ttft_mean_ms=result_before["mean_latency_ms"],
                        ttft_stdev_ms=result_before["stdev_latency_ms"],
                        predicted=result_before["prediction"], confidence=result_before["confidence"],
                        ground_truth_match="N/A_before", secret_category=category, tenant="attacker_before")

            victim_populate_cache(gt)

            for n_trials in TRIAL_COUNTS:
                result_after = classify_with_confidence(gt.template, gt.secret, calib["threshold_ms"], n_trials)
                log_row(LOG_PATH, candidate=gt.secret, trial_batch=n_trials,
                        ttft_mean_ms=result_after["mean_latency_ms"],
                        ttft_stdev_ms=result_after["stdev_latency_ms"],
                        predicted=result_after["prediction"], confidence=result_after["confidence"],
                        ground_truth_match=(result_after["prediction"]=="hit"),
                        secret_category=category, tenant="attacker_after")
                print(f"{category:20s} n_trials={n_trials:2d} before/after logged, after_conf={result_after['confidence']:.2f}")

if __name__ == "__main__":
    run()
