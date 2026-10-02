"""
Mini Project 1.2 -- Target functions for WCET measurement.

Four functions of increasing structural complexity. The first three
have genuinely exploitable worst-case paths; the fourth demonstrates
a target where the deepest branch is *not* measurably more expensive
than shallow branches, so the tool's adversarial strategy cannot
produce a distinct worst case. This is a Section 1.7 lesson in itself:
adversarial input is necessary but not sufficient to reveal the worst
case -- the worst case must actually exist to be measured.
"""


# ---------------------------------------------------------------------------
# Target 1: early-exit branch
# ---------------------------------------------------------------------------
def target_early_exit(data: list) -> int:
    """
    Scan a list looking for a sentinel value (-1).

    Worst case: sentinel NEVER appears -> full scan.
    Best case:  sentinel is the first element -> return immediately.
    """
    for i, v in enumerate(data):
        if v == -1:
            return i          # early exit
    return len(data)


# ---------------------------------------------------------------------------
# Target 2: data-dependent loop count
# ---------------------------------------------------------------------------
def target_data_loop(data: list) -> float:
    """
    Iterative accumulation whose iteration count AND per-iteration cost
    depend on the input.

    Worst case: all values are positive and large -> long loop, expensive
                per-iteration arithmetic.
    Best case:  all values are zero -> loop terminates quickly with
                trivial work per iteration.
    """
    total = 0.0
    for v in data:
        if v > 0:
            # expensive per-iteration work
            for k in range(20):
                total += (v * (k + 1)) ** 0.5
        else:
            # trivial per-iteration work
            total += v
    return total


# ---------------------------------------------------------------------------
# Target 3: nested conditionals with EXPENSIVE deep branch
# ---------------------------------------------------------------------------
def target_nested_expensive(data: list) -> int:
    """
    Nested conditionals -- the deepest branch carries an inner loop so
    that reaching it is genuinely more expensive than shallow branches.

    Worst case: all values > 1000 -> deepest branch every iteration.
    """
    score = 0
    for v in data:
        if v > 0:
            if v > 100:
                if v > 500:
                    if v > 1000:
                        # deepest branch: 50-iteration inner loop
                        for k in range(50):
                            score += (v * (k + 1)) % 997
                    else:
                        score += v * 2
                else:
                    score += v
            else:
                score += v // 2
        else:
            score -= 1
    return score


# ---------------------------------------------------------------------------
# Target 4: nested conditionals WITHOUT expensive deep branch
# ---------------------------------------------------------------------------
def target_nested_conditions(data: list) -> int:
    """
    Same nested-conditional shape as target_nested_expensive, but the
    deepest branch performs only a trivial arithmetic update.

    The purpose of this function is to demonstrate that 'adversarial
    input' cannot produce a measurable worst case when the code itself
    has no genuinely expensive path -- the per-element loop overhead
    dominates, and worst-case == typical case.
    """
    score = 0
    for v in data:
        if v > 0:
            if v > 100:
                if v > 500:
                    if v > 1000:
                        score += v * 3       # trivial
                    else:
                        score += v * 2
                else:
                    score += v
            else:
                score += v // 2
        else:
            score -= 1
    return score


# ---------------------------------------------------------------------------
# Sanity check
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("target_early_exit        :",
          target_early_exit(list(range(1000))))
    print("target_data_loop         :",
          target_data_loop([10] * 100))
    print("target_nested_expensive  :",
          target_nested_expensive([1500] * 50))
    print("target_nested_conditions :",
          target_nested_conditions([1500] * 50))