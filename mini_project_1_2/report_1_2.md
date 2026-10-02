# Mini Project 1.2 — Measurement-Based WCET Estimation and Confidence Tool

**Course:** Real-Time Systems — Unit 1 Lab
**Environment:** Windows desktop, Python 3.x, `numpy`, `matplotlib`.
No RTOS or dedicated hardware.
**Configuration:** 500 timed calls per strategy, 50 warmup calls,
30% safety margin (~70% utilization budget).

---

## 1. Objective

Build a small reusable Python tool that estimates a target function's
worst-case execution time (WCET) using the measurement-based approach
of Section 1.7, quantifies the statistical confidence and inherent
unsoundness of that estimate, and compares it against a hand-crafted
adversarial input approximating the worst-case path a static analyzer
would need to consider.

The tool's output is deliberately **not** a single number — the manual
emphasises that a defensible WCET estimate must include an honest
statement of its limitations. The tool therefore reports measured max,
percentile distribution, outlier flags, and a margined recommendation.

---

## 2. Architecture

| Module | Purpose | Key requirement it satisfies |
|--------|---------|------------------------------|
| `target_functions.py` | 4 target functions of increasing structural complexity | "Implement two or three target functions of increasing structural complexity" |
| `input_strategies.py` | Random + adversarial input generators per target | "At least two input-generation strategies per target" |
| `harness.py` | Generic measurement harness with warmup | "Accepts any target function and input generator without assuming anything about the function's internal structure" |
| `stats_module.py` | Summary stats, outlier flag, safety margin | "Compute mean, std, min, max, and 90/95/99th percentiles … support a configurable safety margin" |
| `wcet_tool.py` | Ties everything together; histograms + comparison table | "Visualize the execution-time distribution … and report a comparison table" |

**Design decisions worth noting:**

- The harness accepts a callable `input_generator(seed=i)` rather than
  a fixed list, so any input shape (list, scalar, dict, etc.) works
  without modifying the harness.
- A **warmup phase** of 50 untimed calls precedes the timed phase.
  Without it, the first timed call absorbs interpreter and cache
  warm-up effects and produces a spurious outlier. This is
  measurement discipline, not a language feature — the manual's
  Section 1.7 warns that measurement artefacts must be actively
  guarded against.
- **Distinct seeds per call** ensure input variety within a strategy.
- The `stats_module.flag_outlier()` heuristic warns when the measured
  max exceeds the 99th percentile by more than 1.5×. Such a gap is
  more consistent with a GC pause, OS preemption, or cache-miss storm
  than with a genuine worst-case code path.

---

## 3. Target Functions

| Target | Structural feature | Worst-case path |
|--------|--------------------|-----------------|
| `target_early_exit` | Early-exit branch on sentinel value | Sentinel is absent → full scan |
| `target_data_loop` | Data-dependent loop count and per-iteration cost | All values positive and large → expensive branch every iteration |
| `target_nested_expensive` | 4-level nested conditionals, deepest branch has a 50-iteration inner loop | All values > 1000 → deepest, most expensive branch every iteration |
| `target_nested_conditions` | Same nesting shape, but deepest branch is trivial | None — every branch costs roughly the same as the loop overhead |

`target_nested_conditions` is deliberately **not** worse in its deep
branch. Its purpose is to demonstrate that when a function has no
genuinely expensive path, adversarial input cannot manufacture one —
a Section 1.7 lesson about the limits of measurement-based WCET.

---

## 4. Results

### 4.1 Comparison table

| Target | Random mean (µs) | Random max (µs) | Adv. mean (µs) | Adv. max (µs) | Adv/Rand max | Margined WCET (µs) |
|--------|-----------------:|----------------:|---------------:|--------------:|-------------:|-------------------:|
| `target_early_exit` | 33.3 | 133.6 | 60.6 | 98.3 | **0.74** | 127.8 |
| `target_data_loop` | 828.3 | 1748.3 | 1049.0 | 2187.1 | **1.25** | 2843.2 |
| `target_nested_expensive` | 150.5 | 326.2 | 1597.6 | 2949.4 | **9.04** | 3834.2 |
| `target_nested_conditions` | 35.4 | 129.2 | 38.5 | 427.9 | **3.31** | 556.3 |

The margined WCET is `adv_max × 1.30`, matching a 30% safety margin
and corresponding to the 60–70% utilization-budget convention of
Section 1.7.

### 4.2 Distributions

Four histograms (`hist_target_*.png`) show random vs. adversarial
execution-time distributions for each target, with the measured max
of each strategy and the margined WCET marked as vertical lines.

`wcet_comparison.png` shows the per-target random max, adversarial max,
and margined WCET as a grouped log-scale bar chart.

---

## 5. Discussion — What the Tool Estimated Confidently, and What It Did Not

### 5.1 Confident estimates

**`target_nested_expensive`** is the tool's strongest result:
adversarial mean is **10.6×** the random mean, and adversarial max is
**9.04×** the random max. The two histograms are visually almost
non-overlapping. The margined WCET of 3834 µs is a defensible
"WCET-for-scheduling" value, provided the design budget allows 30%
margin.

**`target_data_loop`** shows a weaker but consistent signal: adversarial
mean is 1.27× random mean; adversarial max is 1.25× random max. The
margined WCET of 2843 µs is credible.

### 5.2 Estimates the tool could NOT confidently make

**`target_early_exit`** — the adversarial *mean* is higher than random
(as expected — the sentinel is absent so every call scans the full
list), but the adversarial *max* is **lower** than the random max
(98 µs vs 134 µs). This happens because the random distribution
occasionally produces a call with the sentinel near the end of the
list, which costs nearly the same as a full scan *plus* a favourable
draw from the interpreter's variance. The "adversarial" input, being
deterministic, has lower variance.

**Interpretation.** The measured max is a **sample statistic**, not a
stable bound. Two strategies that differ only in mean can produce
*maxes* in either order. Any WCET estimate that relies on a single
"max" value is fragile.

**`target_nested_conditions`** — the tool flagged the adversarial
maximum (427.9 µs) as **5.08×** the 99th percentile (84.2 µs). That is
far more consistent with a GC pause or OS preemption than with a
genuine worst-case path. The random run was also flagged. The tool's
message tells the user explicitly: *investigate for measurement
artefact before trusting this as a WCET estimate.* This is exactly the
behaviour the manual requires — a tool that reports its own
limitations instead of a single authoritative number.

### 5.3 What the tool cannot do (Section 1.7 soundness/pessimism trade-off)

The manual frames the problem as: **measurement is cheap but unsafe;
static analysis is safe but pessimistic.** This tool sits at the
"cheap but unsafe" end, and the results confirm both halves:

1. **Unsoundness.** For `target_early_exit`, the tool reported a lower
   adversarial max than random max — the *measured* max is not a
   proven bound, because the true worst case may depend on hardware
   state (cache line evictions, branch-predictor aliasing, pipeline
   hazards) that no input can deterministically force.

2. **Outlier confusion.** For `target_nested_conditions`, the tool
   could not distinguish a genuine worst-case path from an OS/GC
   artefact without further investigation. This is measurement's
   inherent ambiguity: it sees *what happened*, not *what could
   happen*.

3. **Where static analysis is required.** A certification process
   (Section 1.8) would not accept this tool's output as a bound,
   because it cannot:
   - Prove that the worst-case path was exercised.
   - Distinguish input-caused latency from environmental latency.
   - Reason about hardware-state-dependent timing (cache, TLB).

   The tool's output is useful as a **sanity check** on a static
   analysis (if the measured max exceeds the static bound, something
   is wrong) and as a **calibration input** for choosing safety
   margins — but not as a substitute for analysis.

### 5.4 Which estimates are likely correct, and which are likely underestimates

| Target | Tool's estimate | Likely verdict |
|--------|-----------------|----------------|
| `target_nested_expensive` | margined 3834 µs | **Probably close to real WCET** — the worst path is input-triggerable and adversarial input reaches it |
| `target_data_loop` | margined 2843 µs | **Probably a mild underestimate** — hardware state effects (cache, branch predictor) may add 10–30% |
| `target_early_exit` | margined 127.8 µs | **Definitely an underestimate** — the adversarial max was *below* the random max, so the true worst case is at least ~134 µs + margin |
| `target_nested_conditions` | margined 556.3 µs | **Indeterminate** — the flagged max may be genuine, or may be an artefact; the underlying function's real WCET is probably within 2× the random max |

---

## 6. Certification Caveat (Section 1.8)

For a safety-critical system, the outputs of this tool alone are
**insufficient** to certify a WCET bound, because:

1. **No proof of worst-case coverage.** The tool tests inputs, not
   control-flow paths; it cannot demonstrate that every path the static
   analyzer would consider has been exercised.
2. **Environmental contamination.** All measurements include OS,
   interpreter, and hardware noise. A certified bound must be free
   of such contamination or must bound it explicitly.
3. **No hardware-state modelling.** Cache behaviour, branch-predictor
   state, and pipeline effects are not exercised deterministically.

The proper role of this tool in a certification flow is:

- **Cross-checking** a static analyzer's WCET bound: if measurement
  exceeds the static bound, the analyzer is unsound or the hardware
  model is wrong.
- **Empirical calibration** of the safety margin between typical and
  worst-case behaviour.
- **Regression testing** — a fast, cheap check that a code change has
  not substantially altered timing behaviour.

---

## 7. Deliverables Checklist

- [x] Source code: `harness.py`, `stats_module.py`, `target_functions.py`,
      `input_strategies.py`, `wcet_tool.py`
- [x] Four target functions with two input strategies each
- [x] Histograms: `hist_target_early_exit.png`, `hist_target_data_loop.png`,
      `hist_target_nested_expensive.png`, `hist_target_nested_conditions.png`
- [x] Combined comparison: `wcet_comparison.png`
- [x] Comparison table (§4.1)
- [x] Written discussion (§5)
- [x] Certification caveat (§6)

---

## 8. Note on the "adversarial max < random max" result

The most interesting finding in this project is that **adversarial
input does not always produce the highest *measured* max**, even when
it produces a higher *mean*. This is not a bug in the tool — it is a
fundamental limitation of measurement-based WCET analysis, and it is
the strongest possible argument for Section 1.7's conclusion: a
sound WCET bound requires static analysis, and measurement can only
support and calibrate the analysis, never replace it.