"""
Mini Project 1.2 -- Statistics module.

Given a numpy array of durations, computes the summary statistics
required by the WCET tool and flags outliers (a measured max that lies
far above the 99th percentile -- a rare outlier worth investigating).

Also provides the safety-margin calculation:
    recommended WCET-for-scheduling = measured_max * (1 + margin_pct)
The margin convention references the 60-70% utilization budget of
Section 1.7.
"""

import numpy as np


# ---------------------------------------------------------------------------
# Summary statistics
# ---------------------------------------------------------------------------
def compute_stats(durations: np.ndarray) -> dict:
    """
    Compute mean, std, min, max, and 90th/95th/99th percentiles.

    Parameters
    ----------
    durations : np.ndarray[float]  execution times, seconds

    Returns
    -------
    dict with all values in seconds (except 'n').
    """
    d = np.asarray(durations, dtype=float)
    return {
        "n":     int(d.size),
        "mean":  float(np.mean(d)),
        "std":   float(np.std(d, ddof=1)),
        "min":   float(np.min(d)),
        "max":   float(np.max(d)),
        "p90":   float(np.percentile(d, 90)),
        "p95":   float(np.percentile(d, 95)),
        "p99":   float(np.percentile(d, 99)),
    }


# ---------------------------------------------------------------------------
# Outlier flagging
# ---------------------------------------------------------------------------
def flag_outlier(stats: dict, ratio_threshold: float = 1.5) -> dict:
    """
    Flag when the observed max lies far above the 99th percentile.

    A large gap between max and p99 suggests a rare outlier (interpreter
    GC pause, OS scheduler hiccup, cache miss storm) rather than a
    genuine worst-case path. This matters because the WCET estimate must
    not be driven by a measurement artefact.

    Parameters
    ----------
    stats : dict  output of compute_stats()
    ratio_threshold : float   flag if max > p99 * ratio_threshold

    Returns
    -------
    dict with 'flagged' (bool), 'ratio', 'explanation' (str)
    """
    ratio = stats["max"] / stats["p99"] if stats["p99"] > 0 else float("inf")
    flagged = ratio > ratio_threshold

    if flagged:
        explanation = (
            f"max ({stats['max']*1e6:.1f} us) is {ratio:.2f}x the 99th "
            f"percentile ({stats['p99']*1e6:.1f} us) -- investigate for "
            f"measurement artefact (GC, scheduler, cache) before trusting "
            f"this as a WCET estimate."
        )
    else:
        explanation = (
            f"max / p99 = {ratio:.2f} -- no outlier concern."
        )

    return {"flagged": flagged, "ratio": ratio, "explanation": explanation}


# ---------------------------------------------------------------------------
# Safety margin
# ---------------------------------------------------------------------------
def margined_wcet(stats: dict, margin_pct: float = 30.0) -> float:
    """
    Recommended WCET-for-scheduling:
        margined = measured_max * (1 + margin_pct/100)

    The default 30% margin corresponds to a 70% utilization budget --
    i.e. the tool suggests scheduling at 70% of the margined WCET to
    leave headroom, matching the 60-70% convention in Section 1.7.
    """
    return stats["max"] * (1.0 + margin_pct / 100.0)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    rng = np.random.default_rng(0)
    sample = rng.normal(loc=500e-6, scale=80e-6, size=500)
    # inject a fake outlier
    sample[42] = 3e-3

    s = compute_stats(sample)
    print("=== Stats (sample with injected outlier) ===")
    for k, v in s.items():
        if k == "n":
            print(f"  {k:5s} : {v}")
        else:
            print(f"  {k:5s} : {v*1e6:8.2f} us")

    print("\n=== Outlier flag ===")
    flag = flag_outlier(s)
    print(f"  flagged : {flag['flagged']}")
    print(f"  ratio   : {flag['ratio']:.2f}")
    print(f"  note    : {flag['explanation']}")

    print("\n=== Margined WCET ===")
    for margin in (10, 20, 30, 50):
        w = margined_wcet(s, margin)
        print(f"  margin {margin:3d}%  ->  {w*1e6:8.2f} us")