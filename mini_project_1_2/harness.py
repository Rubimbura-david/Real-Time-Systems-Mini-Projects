"""
Mini Project 1.2 -- Measurement harness (with warmup).

A generic, reusable timing harness. Accepts:
  - any target function (takes one argument, returns anything)
  - any input generator callable  (takes a seed, returns one input)
  - a repeat count and a warmup count

A warmup phase runs the target on throwaway inputs before timing
begins. Without warmup, the first timed call absorbs interpreter
and cache warm-up effects and produces a spurious outlier -- exactly
the kind of artefact Section 1.7 warns about in measurement campaigns.

The harness makes NO assumption about the target function's internal
structure; it only requires that:
    target_fn(inp)   runs and returns something
    input_generator(seed=i)  returns one input for the call
"""

import time
import numpy as np


def run_campaign(target_fn,
                 input_generator,
                 n_calls: int = 500,
                 n_warmup: int = 50,
                 base_seed: int = 1000) -> dict:
    """
    Run a measurement campaign with warmup.

    Parameters
    ----------
    target_fn : callable
        Function under measurement. Called as target_fn(input).
    input_generator : callable
        Called as input_generator(seed=i) for i in [base_seed, base_seed+n_calls).
        Must return one input object.
    n_calls : int
        Number of timed calls.
    n_warmup : int
        Number of untimed warmup calls.
    base_seed : int
        Starting seed; each timed call uses a distinct seed.

    Returns
    -------
    dict with keys:
        'durations'  : np.ndarray[float]   execution time per call (seconds)
        'inputs'     : list                input used for each timed call
        'n_calls'    : int
        'n_warmup'   : int
        'target_name': str
    """
    # ------------------------------------------------------------------
    # 1. Warmup phase (not timed, results discarded)
    # ------------------------------------------------------------------
    for w in range(n_warmup):
        warmup_seed = base_seed - 1 - w
        inp = input_generator(seed=warmup_seed)
        target_fn(inp)

    # ------------------------------------------------------------------
    # 2. Timed phase
    # ------------------------------------------------------------------
    durations = np.empty(n_calls, dtype=float)
    inputs = [None] * n_calls

    for k in range(n_calls):
        seed_k = base_seed + k
        inp = input_generator(seed=seed_k)
        inputs[k] = inp

        t0 = time.perf_counter()
        target_fn(inp)
        t1 = time.perf_counter()

        durations[k] = t1 - t0

    return {
        "durations":   durations,
        "inputs":      inputs,
        "n_calls":     n_calls,
        "n_warmup":    n_warmup,
        "target_name": getattr(target_fn, "__name__", repr(target_fn)),
    }


# ---------------------------------------------------------------------------
# Quick self-test when run directly
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from target_functions import (
        target_early_exit,
        target_data_loop,
        target_nested_expensive,
        target_nested_conditions,
    )
    from input_strategies import STRATEGIES

    targets = {
        "target_early_exit":        target_early_exit,
        "target_data_loop":         target_data_loop,
        "target_nested_expensive":  target_nested_expensive,
        "target_nested_conditions": target_nested_conditions,
    }

    print("=" * 100)
    print("Harness sanity check -- warmup + timed campaign, 500 calls")
    print("=" * 100)
    print(f"{'target':26s} | {'strategy':11s} | "
          f"{'n':>4s} | "
          f"{'mean (us)':>10s} | "
          f"{'min (us)':>10s} | "
          f"{'max (us)':>10s} | "
          f"{'p95 (us)':>10s}")
    print("-" * 100)

    for name, fn in targets.items():
        for kind in ("random", "adversarial"):
            gen = STRATEGIES[name][kind]
            result = run_campaign(fn, gen,
                                  n_calls=500,
                                  n_warmup=50,
                                  base_seed=5000)
            d = result["durations"]
            print(f"{name:26s} | {kind:11s} | "
                  f"{result['n_calls']:4d} | "
                  f"{d.mean()*1e6:10.1f} | "
                  f"{d.min()*1e6:10.1f} | "
                  f"{d.max()*1e6:10.1f} | "
                  f"{np.percentile(d, 95)*1e6:10.1f}")