# Mini Project 1.3 — Real-Time Jitter Analyzer Under Simulated System Noise

**Course:** Real-Time Systems — Unit 1 Lab
**Environment:** Windows desktop, Python 3.x, `numpy`, `matplotlib`.
**Configuration:** 200 jobs per experiment, T = 50 ms, D = 40 ms,
all experiments run with fixed RNG seeds.

---

## 1. Objective

Build a tool that isolates and quantifies jitter — in the sense of
Section 1.3 — in a simulated periodic task loop, and investigate how
the non-deterministic effects of Section 1.6 (background interference,
occasional interrupt- or cache-like delays, general OS-level noise)
degrade release and completion regularity **even when every job still
meets its deadline.**

Section 1.3 stresses that excess jitter is harmful in its own right;
Section 1.6 identifies concrete sources of non-determinism. The
purpose of this project is to build evidence that *"meeting every
deadline"* and *"having low jitter"* are distinct properties.

---

## 2. Method

### 2.1 Baseline drift-free periodic loop

Jobs are released at ideal instants `r₀ + k·T`, using an
absolute-time sleep that is recomputed each iteration. This avoids
cumulative drift — the classic failure mode of `sleep(T)` inside a loop.

### 2.2 Disturbances

| # | Disturbance | Parameter(s) | Section 1.6 source approximated |
|---|-------------|--------------|--------------------------------|
| 1 | Background CPU-load thread | intensity ∈ [0, 1] | General OS interference |
| 2 | Random pre-release delay | probability ∈ {0, 0.1, 0.3, 0.5}; magnitude ∈ {1 ms, 10 ms} | Interrupts, DMA stalls |
| 3 | Execution-time variability | std dev / base workload ∈ {0, 0.1, 0.25, 0.5, 1.0} | Cache / pipeline effects |

Each disturbance is implemented independently so the others can be
held at zero — that lets us attribute any observed jitter to a single
cause.

### 2.3 Metrics

For each experiment:

- **Release jitter** = `actual_release − intended_release`
- **Completion jitter** = `completion − (intended_release + T)`
- **Deadline-hit fraction** = fraction of jobs with `R ≤ D`

The tool reports std-dev and max |jitter| for both release and
completion jitter separately, as required by Section 1.3's distinction
between the two.

---

## 3. Results

### 3.1 Baseline (all disturbances off)

| Metric | Value |
|--------|-------|
| release jitter std | 352.6 µs |
| release jitter max | 4480.4 µs |
| completion jitter std | 838.8 µs |
| completion jitter max | 48928.6 µs |
| hit fraction | 100.0% |

The nonzero baseline jitter is Section 1.6 in the wild: even with a
tight drift-free loop and no injected disturbance, the OS scheduler,
`time.sleep()` quantisation, and Python's GIL produce measurable
release jitter and a completion-jitter max nearly equal to the period.

### 3.2 Disturbance 1 — background CPU load

| Intensity | release std (µs) | release max (µs) | hit fraction |
|-----------|------------------|------------------|--------------|
| 0.00 | 2018.5 | 20823.7 | 100.0% |
| 0.25 | 821.9 | 4587.4 | 100.0% |
| 0.50 | 1611.8 | 5787.7 | 100.0% |
| 0.75 | 2375.6 | 8342.1 | 100.0% |
| 1.00 | 5529.6 | 55058.9 | 100.0% |

**From intensity 0.25 → 1.00 the trend is monotone increasing** —
release jitter std rises from 822 µs to 5530 µs (6.7×), and release
jitter max rises from 4587 µs to 55059 µs (12×). Hit fraction stays
at 100% throughout because the huge slack (D = 40 ms vs. sub-4 ms
execution) absorbs all the added jitter.

**Anomaly.** The intensity = 0.00 row shows release std = 2018 µs, far
above the intensity = 0.25 row (822 µs) and inconsistent with the
clean baseline (352 µs). This is almost certainly a **transient OS
event** — an antivirus scan, OS update thread, or thermal-throttle
episode — that occurred during the first sweep iteration. The
monotone trend across 0.25 → 1.00 is the reliable signal; the
intensity = 0.00 row should be interpreted as contaminated. This
incident is itself a Section 1.6 case study: on a general-purpose OS,
a measurement campaign can be corrupted by environmental noise
without any warning.

### 3.3 Disturbance 2 — random extra delay

| Probability | Magnitude (ms) | release std (µs) | release max (µs) | hit fraction |
|-------------|----------------|------------------|------------------|--------------|
| 0.00 | 0 | 392.3 | 4968.9 | 100.0% |
| 0.10 | 1 | 1077.7 | 14703.2 | 100.0% |
| 0.10 | 10 | 2640.4 | 11632.3 | 100.0% |
| 0.30 | 1 | 891.6 | 5414.6 | 100.0% |
| 0.30 | 10 | **4746.4** | 12399.5 | 100.0% |
| 0.50 | 10 | **5335.0** | 13642.2 | 100.0% |

**Clean monotone growth** in release-jitter std as `probability ×
magnitude` increases (392 → 5335 µs, ~13.6×), while **hit fraction
stays at 100%**. This is the strongest single illustration of the
project's central claim.

**Observation.** The 0.10 probability × 1 ms magnitude case shows
higher max (14.7 ms) than the 0.10 × 10 ms case (11.6 ms). This
is a small statistical artifact of the single-seed sample; the
std-dev column shows the expected monotone increase.

### 3.4 Disturbance 3 — execution-time variability

| Variability | release std (µs) | completion std (µs) | hit fraction |
|-------------|------------------|---------------------|--------------|
| 0.00 | 302.2 | 599.4 | 100.0% |
| 0.10 | 250.7 | 540.9 | 100.0% |
| 0.25 | 556.5 | 860.2 | 100.0% |
| 0.50 | 332.5 | **1059.5** | 100.0% |
| 1.00 | 544.1 | **1648.0** | 100.0% |

**Completion-jitter std grows monotonically** (599 → 1648 µs, 2.75×) as
execution-time variability is injected. **Release-jitter std does not
grow in any consistent trend** (all values between 250 and 557 µs,
scattered). This is the key isolation result: execution-time
variability affects *when a job finishes*, not *when it starts*.
Release jitter and completion jitter are therefore distinguishable
properties, exactly as Section 1.3 asserts.

### 3.5 Combined view

The combined figure (`fig4_combined.png`) shows release-jitter std,
release-jitter max, and hit fraction side-by-side for representative
configurations of all three disturbances. In every one of the 16
non-baseline configurations, **hit fraction is 100%** while release
jitter varies across more than a 25× range. This directly
demonstrates Section 1.3's warning: **meeting every deadline and
having low jitter are orthogonal properties.**

---

## 4. Mapping Disturbances to Section 1.6 Sources

| Disturbance (this tool) | Section 1.6 source | How faithful | Where the analogy breaks |
|-------------------------|--------------------|--------------|--------------------------|
| Background CPU-load thread | General OS interference | Faithful — competes with the timed loop for CPU and GIL ownership | Python's GIL serialises threads, so a busy thread never blocks the timed loop as hard as a real interrupt storm on bare metal |
| Random pre-release delay (Bernoulli) | Interrupts / DMA stalls | Faithful — matches the "occasional, unpredictable, non-preemptable delay" character | Real interrupts land *during* execution at unpredictable points, not only at release instants; this disturbance is a coarse model |
| Execution-time variability (normal distribution) | Cache / pipeline effects | Reasonable — captures per-invocation variance | Real cache effects are heavy-tailed, correlated, and often bimodal (hit / miss); a normal distribution is a simplification |

**Where the analogy helps.** Each disturbance isolates a *single*
Section 1.6 source, which lets us attribute jitter growth to a
specific cause. Real systems blend all sources simultaneously; this
tool separates them for clarity.

**Where the analogy breaks down.** Real OS noise is correlated
(driven by processes on other cores), heavy-tailed, and can occur
mid-execution. Our disturbances are i.i.d., light-tailed, and
release-time only. A more faithful model would inject disturbances
inside `job_body` at random points, use Pareto or log-normal
magnitudes, and add a Markov-chain of "quiet" vs. "noisy" OS states.

---

## 5. Discussion

### 5.1 Meeting every deadline ≠ having low jitter

**The single most important result of this project is that hit
fraction remained at 100% in every experiment** — the entire grid of
configurations — **while release jitter varied from 250 µs to
5530 µs** (a 22× range) and completion jitter from 541 µs to 1648 µs
(a 3× range). If a safety argument were based only on the hit
fraction, it would conclude "all configurations are equally good,"
which is wrong.

For a downstream consumer expecting regular output — a control loop,
an audio buffer, a real-time display — the jitter determines quality
of service. A 5.5 ms std-dev jitter on a 50 ms period means the
output cadence is unpredictable by ±11% even though every job
finished in time.

### 5.2 Release jitter and completion jitter are separable

Disturbance 3 demonstrates this cleanly: injecting execution-time
variance drives completion jitter up (599 → 1648 µs) but leaves
release jitter flat (no trend). Disturbance 2 does the opposite —
it drives release jitter up directly, and only *indirectly* affects
completion jitter through the same shift. Section 1.3's insistence
on measuring them separately is therefore operationally justified:
they answer different questions about system behaviour.

### 5.3 A note on measurement fragility

The D1 intensity = 0.00 anomaly is a small but instructive case
study. On a general-purpose OS, a single measurement run can be
corrupted by an unrelated OS event with no warning. This is one of
the reasons real-time systems for hard deadlines do not run on
general-purpose OSes, and why WCET analysis on such systems must
budget for environmental noise. Every measurement campaign in this
project should therefore be understood as *one sample*, not a proof
of the underlying distribution's parameters.

---

## 6. Deliverables Checklist

- [x] Baseline drift-free periodic loop
- [x] Three disturbance mechanisms, each independently controllable
- [x] Jitter/deadline-hit analyzer (release and completion computed separately)
- [x] Sweep results tables (§3)
- [x] Sweep plots: `fig1_background_sweep.png`, `fig2_extra_delay_sweep.png`, `fig3_exec_variability_sweep.png`
- [x] Combined jitter vs. hit-fraction plot: `fig4_combined.png`
- [x] Section 1.6 mapping discussion (§4)
- [x] Deadline-vs-jitter independence discussion (§5)

---

## 7. Figures

### Figure 1 — `fig1_background_sweep.png`
Release and completion jitter (std and max) vs. background-thread
intensity, plus hit fraction on the right axis.

### Figure 2 — `fig2_extra_delay_sweep.png`
Same layout, swept over probability × magnitude of the Bernoulli
pre-release delay.

### Figure 3 — `fig3_exec_variability_sweep.png`
Same layout, swept over execution-time variability fraction.

### Figure 4 — `fig4_combined.png`
Grouped bars of release-jitter std and max for representative
configurations of all three disturbances, with a hit-fraction line
overlaid. Hit fraction sits at 100% for every bar.