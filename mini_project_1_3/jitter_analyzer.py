"""
Mini Project 1.3 -- Real-Time Jitter Analyzer Under Simulated System Noise.

Simulates a periodic task loop, injects three independently controllable
disturbances (background CPU load, random extra delays, execution-time
variability), and measures how each affects release jitter and
completion jitter independently of the deadline-hit fraction.

Demonstrates Section 1.3's claim: excess jitter is harmful even when
every deadline is met. Each disturbance maps to a Section 1.6 source:

    - background CPU load     -> general OS interference
    - random extra delay      -> interrupt / DMA stall
    - execution-time variance -> cache / pipeline effects
"""

import time
import threading
import numpy as np
import matplotlib.pyplot as plt


# ===========================================================================
# Global plot style
# ===========================================================================
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


# ===========================================================================
# Job body -- variable workload so it can be driven by Disturbance 3
# ===========================================================================
def job_body(workload: int) -> float:
    """A deterministic busy loop whose duration scales with `workload`."""
    total = 0.0
    for i in range(workload):
        total += (i % 7) * 0.123
        if total > 0:
            total = total ** 0.5
    return total


# ===========================================================================
# Disturbance 1: background CPU-load thread
# ===========================================================================
class BackgroundLoad:
    """
    A daemon thread that runs continuous arithmetic work at approximately
    the requested intensity (fraction of a single core).

    intensity in [0.0, 1.0]: 0.0 -> idle (no work), 1.0 -> ~full core.

    The GIL means a pure-Python busy thread cannot literally consume
    100% of a core on a multi-core machine, but it does occupy the
    interpreter's attention and competes with the timed loop for GIL
    ownership -- a real analogy to OS-level background interference.
    """
    def __init__(self, intensity: float = 0.5):
        self.intensity = max(0.0, min(1.0, intensity))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True)

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=1.0)

    def _worker(self):
        # Duty-cycle: burn for `intensity` fraction of a 10 ms window,
        # sleep for the rest.
        window = 0.010
        burn  = window * self.intensity
        idle  = window - burn
        x = 0.0
        while not self._stop.is_set():
            t_end = time.perf_counter() + burn
            while time.perf_counter() < t_end:
                x += (x * 0.9999 + 1.0) ** 0.5   # cheap arithmetic
            if idle > 0:
                time.sleep(idle)


# ===========================================================================
# Periodic loop with all three disturbances available
# ===========================================================================
def periodic_loop(n_jobs: int,
                  period: float,
                  deadline: float,
                  background_intensity: float = 0.0,
                  extra_delay_prob: float = 0.0,
                  extra_delay_ms: float = 0.0,
                  exec_variability: float = 0.0,
                  base_workload: int = 4000,
                  seed: int = 1) -> dict:
    """
    Run a periodic task loop with optional disturbances.

    Parameters
    ----------
    n_jobs : int
    period : float                period T (s)
    deadline : float              relative deadline D (s)
    background_intensity : float  Disturbance 1 intensity [0,1]
    extra_delay_prob : float      Disturbance 2 Bernoulli probability
    extra_delay_ms : float        Disturbance 2 delay magnitude (ms)
    exec_variability : float      Disturbance 3 std-dev as fraction of
                                  base workload (0.0 = fixed workload)
    base_workload : int           nominal job body loop count
    seed : int

    Returns
    -------
    dict with arrays: intended_release, actual_release, completion,
    response_time, hit_mask.
    """
    rng = np.random.default_rng(seed)

    # ---- start disturbance 1 if requested ---------------------------
    bg = None
    if background_intensity > 0:
        bg = BackgroundLoad(background_intensity)
        bg.start()

    try:
        intended_release = np.empty(n_jobs)
        actual_release   = np.empty(n_jobs)
        completion       = np.empty(n_jobs)

        r0 = time.perf_counter()
        next_release = r0

        for k in range(n_jobs):
            # -------- drift-free wait to ideal release ---------------
            sleep_for = next_release - time.perf_counter()
            if sleep_for > 0:
                time.sleep(sleep_for)

            # -------- disturbance 2: random pre-release delay -------
            if extra_delay_prob > 0 and rng.random() < extra_delay_prob:
                time.sleep(extra_delay_ms / 1000.0)

            intended_release[k] = r0 + k * period
            actual_release[k]   = time.perf_counter()

            # -------- disturbance 3: exec-time variability -----------
            if exec_variability > 0:
                workload = int(max(1, rng.normal(
                    loc=base_workload,
                    scale=base_workload * exec_variability)))
            else:
                workload = base_workload

            job_body(workload)
            completion[k] = time.perf_counter()

            next_release = r0 + (k + 1) * period
    finally:
        if bg is not None:
            bg.stop()

    response_time = completion - actual_release
    hit_mask = response_time <= deadline

    return {
        "intended_release": intended_release,
        "actual_release":   actual_release,
        "completion":       completion,
        "response_time":    response_time,
        "hit_mask":         hit_mask,
    }


# ===========================================================================
# Jitter computation
# ===========================================================================
def compute_jitter(result: dict, period: float) -> dict:
    """
    Release jitter     = actual_release - intended_release
    Completion jitter  = actual_completion - intended_completion
                         where intended_completion = intended_release + T
    """
    rel_jit = result["actual_release"] - result["intended_release"]
    comp_jit = result["completion"] - (result["intended_release"] + period)

    return {
        "release_jitter":    rel_jit,
        "completion_jitter": comp_jit,
        "release_std":       float(np.std(rel_jit, ddof=1)),
        "release_absmax":    float(np.max(np.abs(rel_jit))),
        "completion_std":    float(np.std(comp_jit, ddof=1)),
        "completion_absmax": float(np.max(np.abs(comp_jit))),
    }


def run_experiment(n_jobs=200, period=0.05, deadline=0.040, **disturbances):
    """Convenience: run the loop, compute jitter, return a summary dict."""
    result = periodic_loop(n_jobs=n_jobs, period=period, deadline=deadline,
                           **disturbances)
    jit = compute_jitter(result, period)
    return {
        "result": result,
        "jitter": jit,
        "hit_fraction": float(np.mean(result["hit_mask"])),
        "n_jobs":       n_jobs,
    }


# ===========================================================================
# Sweeps
# ===========================================================================
def sweep_background(n_jobs=200, period=0.05, deadline=0.040):
    """Sweep disturbance 1 intensity."""
    settings = [0.0, 0.25, 0.5, 0.75, 1.0]
    rows = []
    for intensity in settings:
        exp = run_experiment(n_jobs=n_jobs, period=period, deadline=deadline,
                             background_intensity=intensity, seed=1)
        rows.append({
            "intensity":        intensity,
            "release_std":      exp["jitter"]["release_std"],
            "release_absmax":   exp["jitter"]["release_absmax"],
            "completion_std":   exp["jitter"]["completion_std"],
            "completion_absmax":exp["jitter"]["completion_absmax"],
            "hit_fraction":     exp["hit_fraction"],
        })
    return rows


def sweep_extra_delay(n_jobs=200, period=0.05, deadline=0.040):
    """Sweep disturbance 2 probability x magnitude."""
    settings = [(0.0,   0.0),    # control
                (0.10,  1.0),
                (0.10, 10.0),
                (0.30,  1.0),
                (0.30, 10.0),
                (0.50, 10.0)]
    rows = []
    for prob, mag in settings:
        exp = run_experiment(n_jobs=n_jobs, period=period, deadline=deadline,
                             extra_delay_prob=prob, extra_delay_ms=mag,
                             seed=1)
        rows.append({
            "prob":             prob,
            "magnitude_ms":     mag,
            "release_std":      exp["jitter"]["release_std"],
            "release_absmax":   exp["jitter"]["release_absmax"],
            "completion_std":   exp["jitter"]["completion_std"],
            "completion_absmax":exp["jitter"]["completion_absmax"],
            "hit_fraction":     exp["hit_fraction"],
        })
    return rows


def sweep_exec_variability(n_jobs=200, period=0.05, deadline=0.040):
    """Sweep disturbance 3 variability (fraction of base workload)."""
    settings = [0.0, 0.1, 0.25, 0.5, 1.0]
    rows = []
    for v in settings:
        exp = run_experiment(n_jobs=n_jobs, period=period, deadline=deadline,
                             exec_variability=v, seed=1)
        rows.append({
            "variability":      v,
            "release_std":      exp["jitter"]["release_std"],
            "release_absmax":   exp["jitter"]["release_absmax"],
            "completion_std":   exp["jitter"]["completion_std"],
            "completion_absmax":exp["jitter"]["completion_absmax"],
            "hit_fraction":     exp["hit_fraction"],
        })
    return rows


# ===========================================================================
# Plots
# ===========================================================================
def _sweep_plot(xs, rel_std, rel_max, comp_std, comp_max, hits,
                xlabel, title, outfile):
    """Two-panel sweep plot: jitter (left) and hit rate (right)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))

    xs_us = xs
    ax1.plot(xs_us, np.array(rel_std)  * 1e6, marker="o",
             label="release jitter std",   color="#1f77b4")
    ax1.plot(xs_us, np.array(rel_max)  * 1e6, marker="s",
             label="release jitter max",   color="#1f77b4", linestyle="--")
    ax1.plot(xs_us, np.array(comp_std) * 1e6, marker="^",
             label="completion jitter std",color="#d62728")
    ax1.plot(xs_us, np.array(comp_max) * 1e6, marker="v",
             label="completion jitter max",color="#d62728", linestyle="--")
    ax1.set_xlabel(xlabel)
    ax1.set_ylabel("jitter (us)")
    ax1.set_title(f"{title} -- jitter")
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8.5)

    hits_pct = np.array(hits) * 100.0
    ax2.plot(xs_us, hits_pct, marker="o", color="#2ca02c", linewidth=1.6)
    ax2.set_xlabel(xlabel)
    ax2.set_ylabel("deadline hit fraction (%)")
    ax2.set_ylim(0, 105)
    ax2.set_title(f"{title} -- hit fraction")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


def plot_background_sweep(rows, outfile="fig1_background_sweep.png"):
    xs = [r["intensity"] for r in rows]
    _sweep_plot(xs,
                [r["release_std"]      for r in rows],
                [r["release_absmax"]   for r in rows],
                [r["completion_std"]   for r in rows],
                [r["completion_absmax"]for r in rows],
                [r["hit_fraction"]     for r in rows],
                xlabel="background thread intensity (fraction of a core)",
                title="Disturbance 1: background CPU load",
                outfile=outfile)


def plot_extra_delay_sweep(rows, outfile="fig2_extra_delay_sweep.png"):
    xs = [r["prob"] * r["magnitude_ms"] for r in rows]   # combined severity
    _sweep_plot(xs,
                [r["release_std"]      for r in rows],
                [r["release_absmax"]   for r in rows],
                [r["completion_std"]   for r in rows],
                [r["completion_absmax"]for r in rows],
                [r["hit_fraction"]     for r in rows],
                xlabel="prob x magnitude (ms)",
                title="Disturbance 2: random extra delay",
                outfile=outfile)


def plot_exec_variability_sweep(rows, outfile="fig3_exec_variability_sweep.png"):
    xs = [r["variability"] for r in rows]
    _sweep_plot(xs,
                [r["release_std"]      for r in rows],
                [r["release_absmax"]   for r in rows],
                [r["completion_std"]   for r in rows],
                [r["completion_absmax"]for r in rows],
                [r["hit_fraction"]     for r in rows],
                xlabel="exec-time variability (std dev / base workload)",
                title="Disturbance 3: execution-time variability",
                outfile=outfile)


def plot_combined(all_rows, outfile="fig4_combined.png"):
    """
    Combined comparison: shows cases where hit fraction stayed near 100%
    while jitter grew substantially.
    """
    labels = []
    rel_std = []
    rel_max = []
    hits    = []

    for r in all_rows:
        labels.append(r["label"])
        rel_std.append(r["release_std"] * 1e6)
        rel_max.append(r["release_absmax"] * 1e6)
        hits.append(r["hit_fraction"] * 100.0)

    x = np.arange(len(labels))
    fig, ax1 = plt.subplots(figsize=(14, 5.5))

    ax1.bar(x - 0.2, rel_std, 0.4, label="release jitter std (us)",
            color="#1f77b4", edgecolor="black")
    ax1.bar(x + 0.2, rel_max, 0.4, label="release jitter max (us)",
            color="#7fb3d5", edgecolor="black")
    ax1.set_ylabel("release jitter (us)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax1.grid(True, axis="y", alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x, hits, marker="o", color="#d62728", linewidth=1.6,
             label="hit fraction (%)")
    ax2.set_ylabel("deadline hit fraction (%)", color="#d62728")
    ax2.set_ylim(0, 105)
    ax2.tick_params(axis="y", labelcolor="#d62728")

    # Combined legend
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8.5)

    ax1.set_title("Combined: jitter vs hit fraction across all disturbances")
    fig.tight_layout()
    fig.savefig(outfile, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved {outfile}")


# ===========================================================================
# Main
# ===========================================================================
if __name__ == "__main__":
    # ---- experiment configuration ----
    N_JOBS   = 200
    PERIOD   = 0.050     # 50 ms
    DEADLINE = 0.040     # 40 ms

    print("=" * 78)
    print("Mini Project 1.3 -- Jitter Analyzer Under Simulated System Noise")
    print(f"  n_jobs={N_JOBS}, T={PERIOD*1000:.0f} ms, D={DEADLINE*1000:.0f} ms")
    print("=" * 78)

    # =========================================================
    # BASELINE (control)
    # =========================================================
    print("\n--- Baseline (all disturbances off) ---")
    base = run_experiment(n_jobs=N_JOBS, period=PERIOD, deadline=DEADLINE,
                          seed=1)
    print(f"  release    std={base['jitter']['release_std']*1e6:7.2f} us"
          f"  max={base['jitter']['release_absmax']*1e6:7.2f} us")
    print(f"  completion std={base['jitter']['completion_std']*1e6:7.2f} us"
          f"  max={base['jitter']['completion_absmax']*1e6:7.2f} us")
    print(f"  hit fraction = {base['hit_fraction']*100:.1f}%")

    # =========================================================
    # DISTURBANCE 1: background CPU load
    # =========================================================
    print("\n--- Disturbance 1: background CPU load ---")
    rows1 = sweep_background(n_jobs=N_JOBS, period=PERIOD, deadline=DEADLINE)
    for r in rows1:
        print(f"  intensity={r['intensity']:4.2f}  |  "
              f"rel std={r['release_std']*1e6:8.1f} us  "
              f"rel max={r['release_absmax']*1e6:8.1f} us  |  "
              f"hit={r['hit_fraction']*100:5.1f}%")

    # =========================================================
    # DISTURBANCE 2: random extra delay
    # =========================================================
    print("\n--- Disturbance 2: random extra delay ---")
    rows2 = sweep_extra_delay(n_jobs=N_JOBS, period=PERIOD, deadline=DEADLINE)
    for r in rows2:
        print(f"  p={r['prob']:4.2f} mag={r['magnitude_ms']:5.1f} ms  |  "
              f"rel std={r['release_std']*1e6:8.1f} us  "
              f"rel max={r['release_absmax']*1e6:8.1f} us  |  "
              f"hit={r['hit_fraction']*100:5.1f}%")

    # =========================================================
    # DISTURBANCE 3: exec-time variability
    # =========================================================
    print("\n--- Disturbance 3: execution-time variability ---")
    rows3 = sweep_exec_variability(n_jobs=N_JOBS, period=PERIOD,
                                   deadline=DEADLINE)
    for r in rows3:
        print(f"  variability={r['variability']:5.2f}  |  "
              f"rel std={r['release_std']*1e6:8.1f} us  "
              f"rel max={r['release_absmax']*1e6:8.1f} us  |  "
              f"comp std={r['completion_std']*1e6:8.1f} us  |  "
              f"hit={r['hit_fraction']*100:5.1f}%")

    # =========================================================
    # PLOTS
    # =========================================================
    print("\n=== Plots ===")
    plot_background_sweep(rows1)
    plot_extra_delay_sweep(rows2)
    plot_exec_variability_sweep(rows3)

    # Combined -- pick representative configurations from all sweeps
    combined_rows = []
    # from D1
    for r in rows1:
        if r["intensity"] > 0:
            combined_rows.append({
                "label": f"BG {int(r['intensity']*100)}%",
                "release_std":      r["release_std"],
                "release_absmax":   r["release_absmax"],
                "hit_fraction":     r["hit_fraction"],
            })
    # from D2
    for r in rows2:
        if r["prob"] > 0:
            combined_rows.append({
                "label": f"DELAY p={r['prob']:.2f} m={r['magnitude_ms']:.0f}ms",
                "release_std":      r["release_std"],
                "release_absmax":   r["release_absmax"],
                "hit_fraction":     r["hit_fraction"],
            })
    # from D3
    for r in rows3:
        if r["variability"] > 0:
            combined_rows.append({
                "label": f"VAR {r['variability']:.2f}",
                "release_std":      r["release_std"],
                "release_absmax":   r["release_absmax"],
                "hit_fraction":     r["hit_fraction"],
            })
    plot_combined(combined_rows, outfile="fig4_combined.png")

    print("\n" + "=" * 78)
    print("Done. Files written:")
    print("  fig1_background_sweep.png")
    print("  fig2_extra_delay_sweep.png")
    print("  fig3_exec_variability_sweep.png")
    print("  fig4_combined.png")
    print("=" * 78)