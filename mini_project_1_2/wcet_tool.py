"""
Mini Project 1.2 -- WCET estimation and confidence tool.

Ties together:
  - target_functions      : the 4 functions under measurement
  - input_strategies      : random + adversarial input per function
  - harness               : generic timed measurement with warmup
  - stats_module          : summary statistics + outlier flag + margin

Produces per target:
  - one histogram (random vs adversarial overlaid)
    with measured max and margined WCET marked
  - a row in a combined comparison table
Produces once:
  - a combined bar chart of measured max vs margined WCET per target
  - a printed comparison table for the report
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from target_functions import (
    target_early_exit,
    target_data_loop,
    target_nested_expensive,
    target_nested_conditions,
)
from input_strategies import STRATEGIES
from harness import run_campaign
from stats_module import compute_stats, flag_outlier, margined_wcet


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
N_CALLS       = 500
N_WARMUP      = 50
BASE_SEED     = 5000
MARGIN_PCT    = 30.0        # ~70% utilization budget (Section 1.7)

TARGETS = {
    "target_early_exit":        target_early_exit,
    "target_data_loop":         target_data_loop,
    "target_nested_expensive":  target_nested_expensive,
    "target_nested_conditions": target_nested_conditions,
}


# ---------------------------------------------------------------------------
# Global plot style
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.dpi":        110,
    "savefig.dpi":       150,
    "font.family":       "DejaVu Sans",
    "font.size":         10,
    "axes.titlesize":    12,
    "axes.titleweight":  "bold",
    "axes.labelsize":    10.5,
    "axes.labelweight":  "medium",
    "axes.grid":         True,
    "grid.alpha":        0.30,
    "grid.linewidth":    0.6,
    "legend.framealpha": 0.95,
    "legend.fontsize":   9,
})


# ---------------------------------------------------------------------------
# Per-target histogram
# ---------------------------------------------------------------------------
def plot_histogram(target_name: str,
                   random_dur: np.ndarray,
                   adversarial_dur: np.ndarray,
                   random_stats: dict,
                   adversarial_stats: dict,
                   margin_pct: float,
                   outfile: str):
    """
    Histogram of execution times for one target.
    Overlays random (blue) and adversarial (red) distributions.
    Vertical lines mark measured max of each strategy and the
    margined WCET (based on the adversarial max).
    """
    fig, ax = plt.subplots(figsize=(10, 5))

    # Use the union range so both histograms share bins
    combined = np.concatenate([random_dur, adversarial_dur])
    lo_us = combined.min() * 1e6
    hi_us = combined.max() * 1e6
    bins = np.linspace(lo_us, hi_us, 40)

    ax.hist(random_dur * 1e6, bins=bins,
            color="#1f77b4", alpha=0.60,
            edgecolor="black", linewidth=0.4,
            label=f"random  (n={random_stats['n']})")
    ax.hist(adversarial_dur * 1e6, bins=bins,
            color="#d62728", alpha=0.55,
            edgecolor="black", linewidth=0.4,
            label=f"adversarial  (n={adversarial_stats['n']})")

    # Measured max lines
    ax.axvline(random_stats["max"] * 1e6,
               color="#1f77b4", linewidth=1.6, linestyle="--",
               label=f"random max = {random_stats['max']*1e6:.0f} us")
    ax.axvline(adversarial_stats["max"] * 1e6,
               color="#d62728", linewidth=1.6, linestyle="--",
               label=f"adversarial max = {adversarial_stats['max']*1e6:.0f} us")

    # Margined estimate from adversarial max
    margined = margined_wcet(adversarial_stats, margin_pct)
    ax.axvline(margined * 1e6,
               color="#2ca02c", linewidth=2.0, linestyle="-",
               label=f"margined WCET = {margined*1e6:.0f} us  (+{margin_pct:.0f}%)")

    ax.set_xlabel("execution time (us)")
    ax.set_ylabel("count")
    ax.set_title(f"Execution-time distribution -- {target_name}")
    ax.legend(loc="upper right", fontsize=8.5)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


# ---------------------------------------------------------------------------
# Combined comparison bar chart
# ---------------------------------------------------------------------------
def plot_comparison_bar(table, margin_pct, outfile):
    """
    Bar chart: for each target, three bars
       - random max
       - adversarial max
       - margined WCET (adversarial max * (1+margin))
    """
    names   = [r["target"] for r in table]
    rmax    = [r["random_max_us"]      for r in table]
    amax    = [r["adversarial_max_us"] for r in table]
    marg    = [r["margined_us"]        for r in table]

    x = np.arange(len(names))
    w = 0.28

    fig, ax = plt.subplots(figsize=(12, 6))
    b1 = ax.bar(x - w, rmax, w, label="random max",
                color="#1f77b4", edgecolor="black")
    b2 = ax.bar(x,     amax, w, label="adversarial max",
                color="#d62728", edgecolor="black")
    b3 = ax.bar(x + w, marg, w,
                label=f"margined WCET (adversarial max + {margin_pct:.0f}%)",
                color="#2ca02c", edgecolor="black")

    # Value labels
    for bars in (b1, b2, b3):
        for b in bars:
            h = b.get_height()
            ax.text(b.get_x() + b.get_width() / 2,
                    h * 1.02 if h > 0 else 0.5,
                    f"{h:.0f}",
                    ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.set_ylabel("execution time (us)")
    ax.set_yscale("log")
    ax.set_title("WCET estimates per target -- random vs adversarial vs margined")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, which="both", axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 78)
    print("Mini Project 1.2 -- Measurement-Based WCET Estimation Tool")
    print(f"  n_calls={N_CALLS} per strategy, warmup={N_WARMUP}, "
          f"margin={MARGIN_PCT:.0f}%")
    print("=" * 78)

    table = []

    for name, fn in TARGETS.items():
        print(f"\n--- {name} ---")

        # ---- run both strategies ------------------------------------
        res_rand = run_campaign(fn, STRATEGIES[name]["random"],
                                n_calls=N_CALLS, n_warmup=N_WARMUP,
                                base_seed=BASE_SEED)
        res_adv  = run_campaign(fn, STRATEGIES[name]["adversarial"],
                                n_calls=N_CALLS, n_warmup=N_WARMUP,
                                base_seed=BASE_SEED)

        d_rand = res_rand["durations"]
        d_adv  = res_adv["durations"]

        s_rand = compute_stats(d_rand)
        s_adv  = compute_stats(d_adv)

        flag_rand = flag_outlier(s_rand)
        flag_adv  = flag_outlier(s_adv)

        margined = margined_wcet(s_adv, MARGIN_PCT)

        # ---- print per-target summary -------------------------------
        print(f"  random      : mean={s_rand['mean']*1e6:8.1f} "
              f"| p95={s_rand['p95']*1e6:8.1f} "
              f"| max={s_rand['max']*1e6:8.1f} us"
              + ("   [OUTLIER]" if flag_rand["flagged"] else ""))
        print(f"  adversarial : mean={s_adv['mean']*1e6:8.1f} "
              f"| p95={s_adv['p95']*1e6:8.1f} "
              f"| max={s_adv['max']*1e6:8.1f} us"
              + ("   [OUTLIER]" if flag_adv["flagged"] else ""))
        print(f"  margined WCET (adv max + {MARGIN_PCT:.0f}%) = "
              f"{margined*1e6:.1f} us")
        if flag_adv["flagged"]:
            print(f"  NOTE: {flag_adv['explanation']}")

        # ---- histogram ---------------------------------------------
        hist_file = f"hist_{name}.png"
        plot_histogram(name, d_rand, d_adv, s_rand, s_adv,
                       MARGIN_PCT, hist_file)

        # ---- record table row --------------------------------------
        table.append({
            "target":               name,
            "random_mean_us":       s_rand["mean"] * 1e6,
            "random_max_us":        s_rand["max"]  * 1e6,
            "adversarial_mean_us":  s_adv["mean"] * 1e6,
            "adversarial_max_us":   s_adv["max"]  * 1e6,
            "margined_us":          margined       * 1e6,
            "outlier_adv":          flag_adv["flagged"],
            "adv_over_rand_max":    (s_adv["max"] / s_rand["max"]
                                     if s_rand["max"] > 0 else float("inf")),
        })

    # ---- combined comparison chart -------------------------------
    print("\n=== Combined comparison ===")
    plot_comparison_bar(table, MARGIN_PCT, "wcet_comparison.png")

    # ---- printed comparison table --------------------------------
    print("\n" + "=" * 110)
    print("Comparison table")
    print("=" * 110)
    header = (f"{'target':26s} | "
              f"{'rand mean':>10s} | "
              f"{'rand max':>10s} | "
              f"{'adv mean':>10s} | "
              f"{'adv max':>10s} | "
              f"{'adv/rand':>9s} | "
              f"{'margined':>10s}")
    print(header)
    print("-" * len(header))
    for r in table:
        print(f"{r['target']:26s} | "
              f"{r['random_mean_us']:10.1f} | "
              f"{r['random_max_us']:10.1f} | "
              f"{r['adversarial_mean_us']:10.1f} | "
              f"{r['adversarial_max_us']:10.1f} | "
              f"{r['adv_over_rand_max']:9.2f} | "
              f"{r['margined_us']:10.1f}")

    print("\n" + "=" * 78)
    print("Done. Files written:")
    print("  hist_target_early_exit.png")
    print("  hist_target_data_loop.png")
    print("  hist_target_nested_expensive.png")
    print("  hist_target_nested_conditions.png")
    print("  wcet_comparison.png")
    print("=" * 78)