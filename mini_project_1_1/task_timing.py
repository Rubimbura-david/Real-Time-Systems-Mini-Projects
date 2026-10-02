"""
Mini Project 1.1: Simulating and Measuring Real-Time Task Timing Behavior
Unit 1 Lab Manual -- Real-Time Systems

Includes all 9 procedure steps + 4 Lab Tasks.
"""

import time
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.ticker import ScalarFormatter

# ---- Global plot style -----------------------------------------------------
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
    "xtick.labelsize":   9,
    "ytick.labelsize":   9,
})


# ---------------------------------------------------------------------------
# Step 1: job function
# ---------------------------------------------------------------------------
def job_function(workload: int) -> float:
    total = 0.0
    for i in range(100):
        total += (i * 0.5) ** 0.5
    for i in range(workload):
        total += (i % 7) * 0.123
        if total > 0:
            total = total ** 0.5
    return total


# ---------------------------------------------------------------------------
# Step 2: isolated execution-time measurement
# ---------------------------------------------------------------------------
def measure_execution_times(n_calls: int = 200, seed: int = 42,
                            workload_range=(2000, 8000)):
    rng = np.random.default_rng(seed)
    workloads = rng.integers(low=workload_range[0],
                             high=workload_range[1],
                             size=n_calls)
    durations = np.empty(n_calls, dtype=float)
    for k in range(n_calls):
        t0 = time.perf_counter()
        job_function(int(workloads[k]))
        t1 = time.perf_counter()
        durations[k] = t1 - t0
    return durations, workloads


def summarize(durations: np.ndarray) -> dict:
    return {
        "mean": float(np.mean(durations)),
        "std":  float(np.std(durations, ddof=1)),
        "min":  float(np.min(durations)),
        "max":  float(np.max(durations)),
        "p95":  float(np.percentile(durations, 95)),
    }


# ---------------------------------------------------------------------------
# Steps 3-4: periodic release loop
# ---------------------------------------------------------------------------
def periodic_run(n_jobs: int = 100,
                 period: float = 0.05,
                 deadline: float = 0.04,
                 seed: int = 7,
                 interference=None):
    """
    interference : optional threading.Event.
        If provided and set, a helper thread performs continuous work
        while the loop runs. This models the Section 1.6 OS-noise sources
        (background CPU load).
    """
    rng = np.random.default_rng(seed)
    records = []

    # ---- optional background interference thread --------------------
    stop_flag = threading.Event()
    def _interference_worker():
        x = 0.0
        while not stop_flag.is_set():
            x += (x * 0.9999 + 1.0) ** 0.5
    interferer = None
    if interference is not None:
        interference.clear()
        interferer = threading.Thread(target=_interference_worker, daemon=True)
        interferer.start()

    try:
        r0 = time.perf_counter()
        next_release = r0

        for k in range(n_jobs):
            sleep_for = next_release - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)

            actual_release = time.perf_counter()
            intended_release = r0 + k * period

            workload = int(rng.integers(low=2000, high=8000))
            job_function(workload)
            completion = time.perf_counter()

            records.append({
                "job_index":         k,
                "intended_release":  intended_release,
                "actual_release":    actual_release,
                "completion":        completion,
                "deadline":          actual_release + deadline,
                "response_time":     completion - actual_release,
                "workload":          workload,
            })

            next_release = r0 + (k + 1) * period
    finally:
        stop_flag.set()
        if interferer is not None:
            interferer.join(timeout=1.0)

    return records


# ---------------------------------------------------------------------------
# Step 5: jitter
# ---------------------------------------------------------------------------
def compute_jitter(records, period):
    release_jitter = np.array([r["actual_release"] - r["intended_release"]
                               for r in records])
    intended_complete = np.array([r["intended_release"] + period
                                  for r in records])
    actual_complete = np.array([r["completion"] for r in records])
    completion_jitter = actual_complete - intended_complete

    def _stats(x):
        return {"std": float(np.std(x, ddof=1)),
                "absmax": float(np.max(np.abs(x)))}

    return {
        "release_jitter":    release_jitter,
        "completion_jitter": completion_jitter,
        "release_stats":     _stats(release_jitter),
        "completion_stats":  _stats(completion_jitter),
    }


# ---------------------------------------------------------------------------
# Step 6: utilities
# ---------------------------------------------------------------------------
def compute_utilities(records, deadline, tau=None):
    HARD_PENALTY = -10.0
    if tau is None:
        tau = deadline / 2.0

    R = np.array([r["response_time"] for r in records])
    hit_mask = R <= deadline
    overshoot = np.maximum(R - deadline, 0.0)

    return {
        "R":            R,
        "hit_mask":     hit_mask,
        "hit_fraction": float(np.mean(hit_mask)),
        "hard":         np.where(hit_mask, 1.0, HARD_PENALTY),
        "firm":         np.where(hit_mask, 1.0, 0.0),
        "soft":         np.where(hit_mask, 1.0, np.exp(-overshoot / tau)),
        "tau":          tau,
        "deadline":     deadline,
    }


# ===========================================================================
# PLOT 1: timing diagram
# ===========================================================================
def plot_timing_diagram(records, period, deadline,
                        n_show: int = 15,
                        outfile: str = "fig1_timing_diagram.png"):
    r0 = records[0]["intended_release"]
    subset = records[:n_show]

    fig, ax = plt.subplots(figsize=(14, 6.2))
    for k in range(n_show):
        ax.axvline(k * period * 1000.0, color="#2ca02c", alpha=0.20,
                   linewidth=0.8, linestyle=":", zorder=1)

    for r in subset:
        k = r["job_index"]
        y = -k
        start_ms = (r["actual_release"] - r0) * 1000.0
        end_ms   = (r["completion"]     - r0) * 1000.0
        width_ms = end_ms - start_ms
        ddl_ms   = (r["deadline"] - r0) * 1000.0
        R_us     = r["response_time"] * 1e6
        ideal_ms = (r["intended_release"] - r0) * 1000.0
        missed   = r["response_time"] > deadline
        bar_color = "#d62728" if missed else "#1f77b4"

        ax.broken_barh([(start_ms, width_ms)], (y - 0.22, 0.44),
                       facecolors=bar_color, edgecolors="black",
                       linewidth=0.6, zorder=3)
        ax.plot([ddl_ms, ddl_ms], [y - 0.35, y + 0.35],
                color="black", linewidth=1.8,
                solid_capstyle="butt", zorder=4)
        ax.plot([ideal_ms, ideal_ms], [y - 0.35, y + 0.35],
                color="#2ca02c", linewidth=1.2, linestyle=":", zorder=2)
        ax.text(start_ms + width_ms / 2, y + 0.30, f"{R_us:.0f}",
                va="bottom", ha="center", fontsize=7.5,
                color="#222222", zorder=5)

    j0 = subset[0]
    jr_start = (j0["intended_release"] - r0) * 1000.0
    jr_act   = (j0["actual_release"]   - r0) * 1000.0
    jr_end   = (j0["completion"]       - r0) * 1000.0
    jr_ddl   = (j0["deadline"]         - r0) * 1000.0

    y_jit = -n_show - 0.35
    y_exec = -n_show - 0.95
    y_d   = -n_show - 1.55

    ax.annotate("", xy=(jr_start, y_jit), xytext=(jr_act, y_jit),
                arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=1.4))
    ax.text((jr_start + jr_act) / 2, y_jit + 0.10,
            f"release jitter  ({(jr_act - jr_start)*1000:.0f} us)",
            ha="center", va="bottom", fontsize=8.5, color="#1a6b1a")

    ax.annotate("", xy=(jr_act, y_exec), xytext=(jr_end, y_exec),
                arrowprops=dict(arrowstyle="<->", color="#1f77b4", lw=1.4))
    ax.text((jr_act + jr_end) / 2, y_exec + 0.10,
            f"execution time  ({(jr_end - jr_act)*1000:.0f} us)",
            ha="center", va="bottom", fontsize=8.5, color="#0d4d80")

    ax.annotate("", xy=(jr_act, y_d), xytext=(jr_ddl, y_d),
                arrowprops=dict(arrowstyle="<->", color="#7a1fa2", lw=1.4))
    ax.text((jr_act + jr_ddl) / 2, y_d + 0.10,
            f"relative deadline  D = {deadline*1000:.0f} ms",
            ha="center", va="bottom", fontsize=8.5, color="#5c1582")

    ax.set_yticks([-k for k in range(n_show)])
    ax.set_yticklabels([f"job {k}" for k in range(n_show)])
    ax.set_ylim(y_d - 1.10, 1.05)
    ax.set_xlabel("time since r0 (ms)")
    ax.set_title(
        f"Timing diagram (fig1_3 style)   |   T = {period*1000:.0f} ms,   "
        f"D = {deadline*1000:.0f} ms   |   first {n_show} jobs", pad=12)
    ax.grid(True, axis="x", alpha=0.22)
    ax.set_axisbelow(True)
    ax.margins(x=0.02, y=0.02)

    legend_items = [
        Patch(facecolor="#1f77b4", edgecolor="black",
              label="job met deadline"),
        Patch(facecolor="#d62728", edgecolor="black",
              label="job missed deadline"),
        Line2D([0], [0], color="black", linewidth=1.8,
               label="assigned deadline"),
        Line2D([0], [0], color="#2ca02c", linewidth=1.2, linestyle=":",
               label="ideal release  r0 + k\u00b7T"),
    ]
    ax.legend(handles=legend_items, loc="upper left",
              bbox_to_anchor=(1.01, 1.0), borderaxespad=0.0, frameon=True)

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


# ===========================================================================
# PLOT 2 / 3: response time + utilities
# ===========================================================================
def plot_response_and_utilities(util, deadline, period,
                                label: str,
                                outfile: str):
    R      = util["R"] * 1e6
    D      = deadline * 1e6
    idx    = np.arange(len(R))
    R_mean = np.mean(R)
    misses = ~util["hit_mask"]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True,
        gridspec_kw={"height_ratios": [1.25, 1], "hspace": 0.12})
    fig.suptitle(
        f"Response time & utility  —  {label}   "
        f"(T = {period*1e3:.0f} ms,  D = {deadline*1e3:.0f} ms,  "
        f"hit fraction = {100*util['hit_fraction']:.1f}%)",
        fontsize=12, y=0.985)

    ax1.fill_between(idx, D, R.max() * 1.6,
                     color="#ffcccc", alpha=0.30, zorder=0)
    ax1.text(len(idx) * 0.02, D * 1.15, "miss zone (R > D)",
             color="#a00000", fontsize=9, va="bottom")
    ax1.plot(idx, R, marker="o", markersize=4.0, linewidth=1.0,
             color="#1f77b4", label="response time R", zorder=3)
    ax1.axhline(D, color="#d62728", linewidth=1.8, linestyle="--",
                label=f"deadline D = {D:.0f} \u00b5s", zorder=4)
    ax1.axhline(R_mean, color="#7f7f7f", linewidth=1.0, linestyle=":",
                label=f"mean R = {R_mean:.0f} \u00b5s", zorder=2)
    if np.any(misses):
        ax1.scatter(idx[misses], R[misses], color="#d62728", s=48,
                    edgecolors="black", linewidths=0.6,
                    zorder=5, label=f"missed ({int(np.sum(misses))})")
    ax1.set_yscale("log")
    ax1.set_ylabel("response time  [\u00b5s, log scale]")
    ax1.set_title("Response time per job", pad=8)
    ax1.grid(True, which="major", alpha=0.35)
    ax1.grid(True, which="minor", alpha=0.15)
    ax1.yaxis.set_major_formatter(ScalarFormatter())
    ax1.legend(loc="upper left", ncol=2, framealpha=0.95)

    ax2.axhline(0, color="black", linewidth=0.7, alpha=0.55)
    ax2.plot(idx, util["hard"], marker="x", markersize=5, linewidth=1.3,
             color="#d62728",
             label="hard  (1 \u2192 hit,  \u221210 \u2192 miss)")
    ax2.plot(idx, util["firm"], marker="s", markersize=4, linewidth=1.3,
             color="#ff7f0e",
             label="firm  (1 \u2192 hit,  0 \u2192 miss)")
    ax2.plot(idx, util["soft"], marker="o", markersize=4, linewidth=1.3,
             color="#2ca02c",
             label=f"soft  (decay \u03c4 = {util['tau']*1e6:.0f} \u00b5s)")
    ax2.set_xlabel("job index")
    ax2.set_ylabel("utility")
    ax2.set_title("Utility under hard / firm / soft deadline classes", pad=8)
    ax2.set_ylim((min(util["hard"]) - 1.2, 1.30) if np.any(misses)
                 else (-0.15, 1.25))
    ax2.grid(True, alpha=0.30)
    ax2.legend(loc="lower right", ncol=1, framealpha=0.95)

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


# ===========================================================================
# LAB TASK PLOTS
# ===========================================================================
def plot_lt1_comparison(base_jit, noise_jit,
                        base_hit, noise_hit,
                        outfile="fig4_lt1_interference.png"):
    """Bar chart comparing baseline vs. with-interference jitter + hit rate."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    categories = ["std dev", "max |jitter|"]
    x = np.arange(len(categories))
    w = 0.35

    base_vals  = [base_jit["release_stats"]["std"] * 1e6,
                  base_jit["release_stats"]["absmax"] * 1e6]
    noise_vals = [noise_jit["release_stats"]["std"] * 1e6,
                  noise_jit["release_stats"]["absmax"] * 1e6]

    ax1.bar(x - w/2, base_vals, w, label="baseline",
            color="#1f77b4", edgecolor="black")
    ax1.bar(x + w/2, noise_vals, w, label="with background noise",
            color="#d62728", edgecolor="black")
    ax1.set_xticks(x); ax1.set_xticklabels(categories)
    ax1.set_ylabel("release jitter (\u00b5s)")
    ax1.set_title("LT1: Release jitter, baseline vs. interference")
    ax1.legend(); ax1.grid(True, axis="y", alpha=0.3)

    bars = ax2.bar(["baseline", "with noise"],
                   [base_hit * 100, noise_hit * 100],
                   color=["#1f77b4", "#d62728"], edgecolor="black")
    for b, v in zip(bars, [base_hit * 100, noise_hit * 100]):
        ax2.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}%",
                 ha="center", fontsize=9)
    ax2.set_ylim(0, 110)
    ax2.set_ylabel("deadline hit fraction (%)")
    ax2.set_title("LT1: Deadline-hit fraction")
    ax2.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


def plot_lt2_wcet(normal_stats, adversarial_stats,
                  outfile="fig5_lt2_wcet.png"):
    labels = ["mean", "p95", "max"]
    normal_v = [normal_stats["mean"]*1e6, normal_stats["p95"]*1e6,
                normal_stats["max"]*1e6]
    adv_v    = [adversarial_stats["mean"]*1e6, adversarial_stats["p95"]*1e6,
                adversarial_stats["max"]*1e6]
    x = np.arange(len(labels)); w = 0.35

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(x - w/2, normal_v, w, label="random workloads",
           color="#1f77b4", edgecolor="black")
    ax.bar(x + w/2, adv_v, w, label="adversarial (max) workload",
           color="#d62728", edgecolor="black")
    for xi, (n, a) in enumerate(zip(normal_v, adv_v)):
        ax.text(xi - w/2, n + 20, f"{n:.0f}", ha="center", fontsize=8.5)
        ax.text(xi + w/2, a + 20, f"{a:.0f}", ha="center", fontsize=8.5)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel("execution time (\u00b5s)")
    ax.set_title("LT2: WCET estimate — random vs. adversarial inputs")
    ax.legend(); ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


def plot_lt3_decay(records, deadline,
                   outfile="fig6_lt3_soft_decay.png"):
    """Overlay soft utility with fast, nominal, and slow decay rates."""
    R = np.array([r["response_time"] for r in records])
    idx = np.arange(len(R))
    overshoot = np.maximum(R - deadline, 0.0)

    taus = {
        "fast  (\u03c4 = D/10)":  deadline / 10.0,
        "nominal  (\u03c4 = D/2)": deadline / 2.0,
        "slow  (\u03c4 = 2D)":     deadline * 2.0,
    }
    colors = ["#d62728", "#ff7f0e", "#2ca02c"]

    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.axhline(1.0, color="gray", linewidth=0.8, linestyle=":")
    for (name, tau), c in zip(taus.items(), colors):
        u = np.where(R <= deadline, 1.0, np.exp(-overshoot / tau))
        ax.plot(idx, u, marker="o", markersize=3.5, linewidth=1.2,
                color=c, label=name)

    ax.set_xlabel("job index")
    ax.set_ylabel("soft utility")
    ax.set_title(f"LT3: soft-deadline utility under different decay rates  "
                 f"(D = {deadline*1e6:.0f} \u00b5s)")
    ax.set_ylim(-0.05, 1.1)
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


def plot_lt4_period_sweep(results,
                          outfile="fig7_lt4_period_sweep.png"):
    """
    results : list of dicts with keys T, rel_std, rel_absmax, hit
    Plots jitter / T as a fraction vs. period.
    """
    Ts         = [r["T"] * 1000 for r in results]                 # ms
    rel_std    = [r["rel_std"] * 100 for r in results]            # %
    rel_absmax = [r["rel_absmax"] * 100 for r in results]
    hits       = [r["hit"] * 100 for r in results]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    ax1.plot(Ts, rel_std, marker="o", linewidth=1.5,
             color="#1f77b4", label="std dev (jitter/T)")
    ax1.plot(Ts, rel_absmax, marker="s", linewidth=1.5,
             color="#d62728", label="max |jitter| / T")
    ax1.set_xlabel("period T (ms)")
    ax1.set_ylabel("jitter as % of period")
    ax1.set_title("LT4: Release jitter as fraction of period")
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    ax2.plot(Ts, hits, marker="o", linewidth=1.5,
             color="#2ca02c", label="deadline hit fraction")
    ax2.set_xlabel("period T (ms)")
    ax2.set_ylabel("hit fraction (%)")
    ax2.set_ylim(0, 105)
    ax2.set_title("LT4: Deadline hit fraction vs. period")
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 66)
    print("Mini Project 1.1 — Real-Time Task Timing Behavior")
    print("=" * 66)

    # ==================================================================
    # STEP 2: isolated measurement
    # ==================================================================
    durations, workloads = measure_execution_times(n_calls=200)
    stats = summarize(durations)
    print("\n=== Step 2: Execution time over 200 isolated calls ===")
    print(f"  mean    : {stats['mean']*1e6:8.2f} us")
    print(f"  std dev : {stats['std']*1e6:8.2f} us")
    print(f"  min     : {stats['min']*1e6:8.2f} us")
    print(f"  max     : {stats['max']*1e6:8.2f} us   <-- measured WCET estimate")
    print(f"  p95     : {stats['p95']*1e6:8.2f} us")

    # ==================================================================
    # STEPS 3-4: baseline periodic loop
    # ==================================================================
    T = 0.05
    D_baseline = 0.8 * T
    records_base = periodic_run(n_jobs=100, period=T,
                                deadline=D_baseline, seed=7)
    rts_base = np.array([r["response_time"] for r in records_base])
    print("\n=== Steps 3-4: Periodic loop, baseline (loose D) ===")
    print(f"  T = {T*1000:.1f} ms, D = {D_baseline*1000:.1f} ms, "
          f"{len(records_base)} jobs")
    print(f"  response-time mean : {np.mean(rts_base)*1e6:8.2f} us")
    print(f"  response-time max  : {np.max(rts_base)*1e6:8.2f} us")

    # ==================================================================
    # STEP 5: jitter
    # ==================================================================
    jit = compute_jitter(records_base, T)
    print("\n=== Step 5: Jitter analysis ===")
    print(f"  Release jitter    std dev = "
          f"{jit['release_stats']['std']*1e6:8.2f} us  |  "
          f"max |j| = {jit['release_stats']['absmax']*1e6:8.2f} us")
    print(f"  Completion jitter std dev = "
          f"{jit['completion_stats']['std']*1e6:8.2f} us  |  "
          f"max |j| = {jit['completion_stats']['absmax']*1e6:8.2f} us")

    # ==================================================================
    # STEP 6: utilities
    # ==================================================================
    util_base = compute_utilities(records_base, D_baseline)
    n_hits = int(np.sum(util_base["hit_mask"]))
    n_jobs = len(records_base)
    print("\n=== Step 6: Deadline classification & utility (baseline) ===")
    print(f"  deadline hits       : {n_hits}/{n_jobs} "
          f"({100*util_base['hit_fraction']:.1f}%)")
    print(f"  soft decay constant : tau = {util_base['tau']*1e6:.1f} us")
    print(f"  hard utility mean   : {np.mean(util_base['hard']):7.3f}")
    print(f"  firm utility mean   : {np.mean(util_base['firm']):7.3f}")
    print(f"  soft utility mean   : {np.mean(util_base['soft']):7.3f}")

    # ==================================================================
    # STEP 7-8: plots
    # ==================================================================
    print("\n=== Step 7-8: Plots ===")
    plot_timing_diagram(records_base, T, D_baseline, n_show=15,
                        outfile="fig1_timing_diagram.png")
    plot_response_and_utilities(util_base, D_baseline, T,
                                label="baseline (loose D)",
                                outfile="fig2_response_utility_baseline.png")

    # ==================================================================
    # STEP 8 (extra): forced-miss demo
    # ==================================================================
    print("\n=== Forced-miss demo (tight D) ===")
    D_tight = float(np.percentile(rts_base, 80))
    print(f"  chosen D = {D_tight*1e6:.0f} us (80th pct of baseline R)")
    records_tight = periodic_run(n_jobs=100, period=T,
                                 deadline=D_tight, seed=7)
    rts_tight = np.array([r["response_time"] for r in records_tight])
    util_tight = compute_utilities(records_tight, D_tight)
    print(f"  hit fraction        : "
          f"{100*util_tight['hit_fraction']:.1f}%")
    print(f"  hard utility mean   : {np.mean(util_tight['hard']):7.3f}")
    print(f"  firm utility mean   : {np.mean(util_tight['firm']):7.3f}")
    print(f"  soft utility mean   : {np.mean(util_tight['soft']):7.3f}")
    plot_response_and_utilities(util_tight, D_tight, T,
                                label="tight D (forced misses)",
                                outfile="fig3_response_utility_tightD.png")

    # ==================================================================
    # LAB TASK 1: background interference
    # ==================================================================
    print("\n" + "=" * 66)
    print("LAB TASK 1: Background interference thread")
    print("=" * 66)
    ev = threading.Event(); ev.set()   # signals "run interferer"
    records_noise = periodic_run(n_jobs=100, period=T,
                                 deadline=D_baseline, seed=7,
                                 interference=ev)
    jit_noise = compute_jitter(records_noise, T)
    util_noise = compute_utilities(records_noise, D_baseline)

    print(f"  baseline   release jitter std = "
          f"{jit['release_stats']['std']*1e6:7.2f} us  |  "
          f"max = {jit['release_stats']['absmax']*1e6:7.2f} us  |  "
          f"hit = {100*util_base['hit_fraction']:.1f}%")
    print(f"  w/ noise   release jitter std = "
          f"{jit_noise['release_stats']['std']*1e6:7.2f} us  |  "
          f"max = {jit_noise['release_stats']['absmax']*1e6:7.2f} us  |  "
          f"hit = {100*util_noise['hit_fraction']:.1f}%")

    plot_lt1_comparison(jit, jit_noise,
                        util_base["hit_fraction"],
                        util_noise["hit_fraction"],
                        outfile="fig4_lt1_interference.png")

    # ==================================================================
    # LAB TASK 2: adversarial input WCET
    # ==================================================================
    print("\n" + "=" * 66)
    print("LAB TASK 2: Adversarial-input WCET")
    print("=" * 66)
    adv_durations, _ = measure_execution_times(n_calls=200, seed=42,
                                               workload_range=(20000, 20001))
    adv_stats = summarize(adv_durations)
    print(f"  ordinary-input   max  = {stats['max']*1e6:8.2f} us")
    print(f"  adversarial-max  max  = {adv_stats['max']*1e6:8.2f} us")
    print(f"  ratio (adv/normal)    = {adv_stats['max']/stats['max']:.2f}x")
    plot_lt2_wcet(stats, adv_stats, outfile="fig5_lt2_wcet.png")

    # ==================================================================
    # LAB TASK 3: soft-decay rate sweep
    # ==================================================================
    print("\n" + "=" * 66)
    print("LAB TASK 3: Soft-deadline decay-rate sweep")
    print("=" * 66)
    # Use the tight-D records so we actually have overshoots to decay
    R_tight = np.array([r["response_time"] for r in records_tight])
    over = np.maximum(R_tight - D_tight, 0.0)
    for label, tau_mult in [("fast (tau=D/10)", 0.1),
                            ("nominal (tau=D/2)", 0.5),
                            ("slow (tau=2D)", 2.0)]:
        tau = D_tight * tau_mult
        u = np.where(R_tight <= D_tight, 1.0, np.exp(-over / tau))
        print(f"  {label:22s}  mean soft utility = {np.mean(u):.4f}")
    plot_lt3_decay(records_tight, D_tight,
                   outfile="fig6_lt3_soft_decay.png")

    # ==================================================================
    # LAB TASK 4: period sweep
    # ==================================================================
    print("\n" + "=" * 66)
    print("LAB TASK 4: Period sweep (D = 0.8*T)")
    print("=" * 66)
    lt4_results = []
    for T_test in [0.025, 0.050, 0.100, 0.200]:
        D_test = 0.8 * T_test
        rec = periodic_run(n_jobs=100, period=T_test,
                           deadline=D_test, seed=7)
        j = compute_jitter(rec, T_test)
        u = compute_utilities(rec, D_test)
        rel_std    = j["release_stats"]["std"] / T_test
        rel_absmax = j["release_stats"]["absmax"] / T_test
        lt4_results.append({
            "T": T_test,
            "rel_std":    rel_std,
            "rel_absmax": rel_absmax,
            "hit":        u["hit_fraction"],
        })
        print(f"  T = {T_test*1000:6.1f} ms  |  "
              f"rel std = {rel_std*100:6.2f}%  |  "
              f"rel max = {rel_absmax*100:6.2f}%  |  "
              f"hit = {100*u['hit_fraction']:5.1f}%")

    plot_lt4_period_sweep(lt4_results,
                          outfile="fig7_lt4_period_sweep.png")

    # ==================================================================
    print("\n" + "=" * 66)
    print("Done. Figures written:")
    for fn in ["fig1_timing_diagram.png",
               "fig2_response_utility_baseline.png",
               "fig3_response_utility_tightD.png",
               "fig4_lt1_interference.png",
               "fig5_lt2_wcet.png",
               "fig6_lt3_soft_decay.png",
               "fig7_lt4_period_sweep.png"]:
        print(f"  {fn}")
    print("=" * 66)

    plt.show()