# DualVulnDroid Real-Time Detection Pipeline — Latency Experiment

## 1. Experimental setup

Real, non-simulated measurement of the existing IDE real-time detection pipeline: IDE code edit -> 500ms debounce -> CodeSentinelAnnotator -> APIClient -> FastAPI `/predict` -> predictor.py -> XGBoost prediction -> static/data-flow evidence -> decision engine -> HTTP response -> IDE annotation creation -> finding visible in editor. No detection logic, model, threshold, or decision-engine behavior was changed to produce these numbers - only opt-in, disabled-by-default timing instrumentation was added (see LatencyTelemetry.kt and predictor.py's `capture_timing` parameter).

## 2. Hardware/software environment

- OS: Windows 11 (amd64)
- Java: 21.0.6
- Available processors: 8
- Plugin build identifier: 1.0-SNAPSHOT
- Backend URL used: http://127.0.0.1:8000/predict
- Debounce setting: 500 ms
- Experiment date/time (UTC): 2026-09-07T09:21:21.620031200Z

## 3. Measurement methodology

Driven by `DualVulnDroid/src/test/kotlin/.../LatencyExperimentTest.kt`, a headless IntelliJ Platform test (`BasePlatformTestCase`) that runs the REAL, registered `CodeSentinelAnnotator` through IntelliJ's real daemon highlighting pipeline (`myFixture.doHighlighting()`), against the REAL running FastAPI backend - no mocked API, no mocked predictor, for either the warm-up or measured phases. **Documented limitation** (explicitly permitted by the task's own escape valve): this runs inside a headless JVM test instance, not a visible IDE window with a human or UI-automation tool physically typing keystrokes - no pixels are rendered or captured. What IS real: the actual PSI/document state, the actual registered `ExternalAnnotator`, the actual 500ms `Thread.sleep` debounce, the actual OkHttp network round trip, the actual `AnnotationHolder`-based annotation creation.

T0 ("code edit event received") is measured at `collectInformation()` entry - this architecture has no separate `DocumentListener`; IntelliJ's own daemon detects the edit and re-invokes the registered `ExternalAnnotator`, so this is the earliest point the plugin's own code observes it.

## 4. Warm-up procedure

5 of 5 warm-up scans were performed and discarded before measurement began (Part 4A) - one of each code type, covering both CWE categories and safe code, so the JVM/backend/model are warm before any measured timestamp is taken.

## 5. Number of measured events

**50** of 50 requested measured events produced a complete, valid measurement (0 missed/documented - see Limitations).

## 6. Timing definitions

**Two different latency definitions are reported - never conflated (Part 7):**

- **A. User-perceived end-to-end latency** (`end_to_end_ms`, T8-T0): code edit -> annotation available. **Includes** the intentional 500ms debounce.
- **B. Detection pipeline latency** (`pipeline_ms`, T8-T1): debounce completed -> annotation available. **Excludes** the intentional debounce time - this isolates actual backend/network/annotation processing.

Also reported: `backend_total_ms` (T5-T3, backend request-received -> prediction complete) and `prediction_ms` (backend-internal: feature extraction + XGBoost inference only, a narrower sub-span within `backend_total_ms` - see predictor.py's `_timing` breakdown; it also separately reports `shap_and_rule_detection_ms`/`dataflow_ms`/`decision_ms`, not repeated in the headline tables below but present in the raw JSON metadata's per-request timing when the benchmark header is used).

## 7. Raw-data location

`latency_experiment/latency_results.csv` and `latency_experiment/latency_results.json` (same directory as this report) - outside `DualVulnDroid/`, `backend/`, and the frozen IEEE workspace, per the task's Part 5 instruction.

## 8. Statistical results

All values in **milliseconds**, computed from the raw CSV only - see `analyze_latency.py`. P90/P95/P99 use the nearest-rank method (`percentile()` in that script).

## 9. Overall latency table

N = 50 measured runs in this category.

| Metric | N | Mean | Median | Min | Max | StdDev | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| End-to-end (code edit -> annotation, includes debounce) | 50 | 602.29 | 596.91 | 555.79 | 659.57 | 29.42 | 649.68 | 654.25 | 658.06 |
| Detection pipeline (debounce complete -> annotation, EXCLUDES debounce) | 50 | 100.55 | 94.79 | 51.56 | 157.18 | 29.50 | 148.87 | 152.47 | 156.19 |
| Backend total | 50 | 70.58 | 73.78 | 41.45 | 124.74 | 15.67 | 83.37 | 85.37 | 106.07 |
| XGBoost prediction (backend-internal) | 50 | 13.71 | 11.33 | 8.11 | 54.61 | 6.84 | 18.01 | 19.35 | 39.25 |

## 10. CWE-89 latency table

N = 20 measured runs in this category.

| Metric | N | Mean | Median | Min | Max | StdDev | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| End-to-end (code edit -> annotation, includes debounce) | 20 | 612.92 | 600.11 | 591.05 | 659.57 | 24.68 | 655.84 | 656.65 | 658.99 |
| Detection pipeline (debounce complete -> annotation, EXCLUDES debounce) | 20 | 110.97 | 98.18 | 89.61 | 157.18 | 24.88 | 154.17 | 155.26 | 156.79 |
| Backend total | 20 | 73.85 | 72.96 | 69.42 | 80.29 | 3.56 | 78.34 | 79.14 | 80.06 |
| XGBoost prediction (backend-internal) | 20 | 11.87 | 10.91 | 8.11 | 19.77 | 2.86 | 14.52 | 18.88 | 19.59 |

## 11. CWE-295 latency table

N = 10 measured runs in this category.

| Metric | N | Mean | Median | Min | Max | StdDev | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| End-to-end (code edit -> annotation, includes debounce) | 10 | 614.53 | 611.29 | 589.87 | 649.47 | 22.81 | 641.35 | 645.41 | 648.66 |
| Detection pipeline (debounce complete -> annotation, EXCLUDES debounce) | 10 | 113.30 | 110.03 | 88.34 | 148.74 | 22.78 | 139.40 | 144.07 | 147.81 |
| Backend total | 10 | 73.84 | 74.24 | 71.56 | 75.93 | 1.61 | 75.45 | 75.69 | 75.89 |
| XGBoost prediction (backend-internal) | 10 | 12.11 | 11.49 | 10.59 | 16.81 | 1.79 | 13.29 | 15.05 | 16.46 |

## 12. SAFE latency table

N = 20 measured runs in this category.

| Metric | N | Mean | Median | Min | Max | StdDev | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| End-to-end (code edit -> annotation, includes debounce) | 20 | 585.53 | 592.17 | 555.79 | 652.40 | 29.71 | 622.06 | 645.64 | 651.05 |
| Detection pipeline (debounce complete -> annotation, EXCLUDES debounce) | 20 | 83.76 | 89.88 | 51.56 | 150.02 | 29.70 | 120.86 | 142.79 | 148.58 |
| Backend total | 20 | 65.67 | 67.17 | 41.45 | 124.74 | 24.02 | 85.95 | 88.54 | 117.50 |
| XGBoost prediction (backend-internal) | 20 | 16.35 | 16.79 | 9.45 | 54.61 | 9.93 | 18.74 | 24.83 | 48.66 |

## 13. Interpretation

Across 50 measured real-time scans, the mean user-perceived end-to-end latency (code edit to visible annotation, debounce included) was **602.3 ms** (median 596.9 ms, P95 654.3 ms, P99 658.1 ms). Of that, the detection-pipeline portion alone (debounce excluded) averaged **100.5 ms** (median 94.8 ms) - i.e. roughly 17% of the user-perceived latency is the deliberate 500ms debounce, not backend/network/annotation processing.

Backend processing itself averaged 70.6 ms of that pipeline time, of which XGBoost inference (`prediction_ms`) averaged 13.7 ms when available - the remainder of backend time is SHAP/rule-based line localization, data-flow analysis, and decision-engine evaluation (see predictor.py's fuller internal breakdown).

**On whether this evidence supports the existing "real-time/in-editor detection" functional description**: the measured pipeline latency (annotation appears within roughly 152 ms of the debounce completing, 95th percentile) is fast enough that a developer would perceive the finding as appearing promptly after they pause typing, which is consistent with the plugin's existing functional claim of in-editor, real-time-feeling detection. This is NOT, on its own, a formal real-time systems guarantee (no worst-case bound, no load testing, a single machine, a single session, snippet sizes representative but not exhaustive) - see Limitations. The data supports the EXISTING functional description; it does not establish a new latency SLA, and none should be inferred from it.

## 14. Limitations

- **Not a visible-IDE, human-keystroke measurement.** Driven by a headless IntelliJ Platform JUnit test, not a rendered window with real keystrokes (see Methodology). Real keystroke-to-daemon-trigger latency (outside this plugin's own code, inside IntelliJ's own typing/highlighting-scheduling internals) is not captured by T0, since T0 is measured at this plugin's own `collectInformation()` entry, not at the raw keystroke.
- **Single machine, single session, sequential runs.** No concurrent-editor load, no multi-file project context, no measurement of tail behavior under real developer multitasking (switching files, IDE indexing in the background, etc.).
- **A fixed, small set of representative code snippets** (traced-source CWE-89, parameterized-safe CWE-89, HostnameVerifier CWE-295, real-check safe CWE-295), each small (a handful of lines) - not a stress test of large files or many simultaneous findings.
- **`backend_total_ms`/`prediction_ms` come from a SEPARATE, out-of-band request** (`APIClient.fetchBenchmarkTiming`, made AFTER each measured cycle completes, requesting the backend's own `X-Benchmark-Timing` breakdown for the identical code) - not from the actual measured request itself, since the real-time path never sends that header. This cannot affect T0-T8 in any way, but does mean these two columns reflect a second, immediately-following request rather than the literal measured one.
- **No fabricated "real-time" claim.** As instructed: low measured latency alone does not, by itself, prove a formal real-time guarantee; see Interpretation above for the precise, hedged claim this data actually supports.
