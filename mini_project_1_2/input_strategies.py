"""
Mini Project 1.2 -- Input generation strategies.

For each target function we provide two strategies:

  - random      : representative workload, produces a realistic distribution
  - adversarial : hand-crafted to force the longest code path

Section 1.7 -- measurement-based WCET is unsound because a random
campaign may never exercise the true worst case. The adversarial
strategy closes part of that gap but not all of it, because the true
worst case may depend on hardware state (cache, branch predictor) that
no input can force deterministically.
"""

import numpy as np


# ===========================================================================
# Target 1: target_early_exit
# ===========================================================================
def random_input_early_exit(seed: int, size: int = 2000) -> list:
    """
    A list of length `size` where -1 appears at a random position.
    The run-time depends on where the -1 falls: sometimes short, sometimes long.
    """
    rng = np.random.default_rng(seed)
    data = rng.integers(low=0, high=100, size=size).tolist()
    pos = int(rng.integers(low=0, high=size))   # where -1 hides
    data[pos] = -1
    return data


def adversarial_input_early_exit(seed: int, size: int = 2000) -> list:
    """
    A list of length `size` WITHOUT -1 -- forces a full scan every time.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(low=0, high=100, size=size).tolist()


# ===========================================================================
# Target 2: target_data_loop
# ===========================================================================
def random_input_data_loop(seed: int, size: int = 500) -> list:
    """
    Mixed positive and non-positive values. Positive values trigger the
    expensive inner loop; non-positive values fall through cheaply.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(low=-100, high=200, size=size).tolist()


def adversarial_input_data_loop(seed: int, size: int = 500) -> list:
    """
    All large positive values -> every iteration takes the expensive
    branch AND uses a large magnitude (maximizing the sqrt-work).
    """
    rng = np.random.default_rng(seed)
    return rng.integers(low=900, high=1000, size=size).tolist()


# ===========================================================================
# Random generator used by BOTH nested-conditional targets
# ===========================================================================
def random_input_nested(seed: int, size: int = 500) -> list:
    """
    Values spanning all branches. Most are below 1000 so that the deep
    branch (v > 1000) is rare.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(low=-200, high=1100, size=size).tolist()


# ===========================================================================
# Target 3: target_nested_expensive
# ===========================================================================
def adversarial_input_nested_expensive(seed: int, size: int = 500) -> list:
    """
    All values > 1000 -> deepest (expensive) branch every iteration.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(low=1001, high=2000, size=size).tolist()


# ===========================================================================
# Target 4: target_nested_conditions (the "no expensive path" target)
# ===========================================================================
def adversarial_input_nested(seed: int, size: int = 500) -> list:
    """
    All values > 1000 -> deepest branch every iteration. But this target
    has no genuinely expensive path, so no measurable worst case appears.
    """
    rng = np.random.default_rng(seed)
    return rng.integers(low=1001, high=2000, size=size).tolist()


# ===========================================================================
# Registry -- lets the harness look up strategies by name
# ===========================================================================
STRATEGIES = {
    "target_early_exit": {
        "random":      random_input_early_exit,
        "adversarial": adversarial_input_early_exit,
    },
    "target_data_loop": {
        "random":      random_input_data_loop,
        "adversarial": adversarial_input_data_loop,
    },
    "target_nested_expensive": {
        "random":      random_input_nested,
        "adversarial": adversarial_input_nested_expensive,
    },
    "target_nested_conditions": {
        "random":      random_input_nested,
        "adversarial": adversarial_input_nested,
    },
}


if __name__ == "__main__":
    for name, strategies in STRATEGIES.items():
        for kind, fn in strategies.items():
            sample = fn(seed=42)
            print(f"{name:26s} | {kind:11s} | "
                  f"len={len(sample):5d} | "
                  f"min={min(sample):6} | max={max(sample):6}")