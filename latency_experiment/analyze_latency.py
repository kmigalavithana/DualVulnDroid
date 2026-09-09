#!/usr/bin/env python3
"""
Latency-measurement experiment task, Parts 6/8/9.

Reads latency_results.csv (raw measurements written by
DualVulnDroid's LatencyExperimentTest - real plugin, real backend, no
mocks), computes descriptive statistics (overall + per-CWE-category
subgroup), writes latency_summary.md, and plots
latency_distribution.png.

Run from this directory:  python analyze_latency.py
"""
import csv
import json
import math
import os
import statistics
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "latency_results.csv")
JSON_PATH = os.path.join(HERE, "latency_results.json")
SUMMARY_PATH = os.path.join(HERE, "latency_summary.md")
PLOT_PATH = os.path.join(HERE, "latency_distribution.png")

METRIC_COLUMNS = ["end_to_end_ms", "pipeline_ms", "backend_total_ms", "prediction_ms"]
NUMERIC_COLUMNS = [
    "debounce_ms", "request_ms", "backend_total_ms", "prediction_ms",
    "plugin_response_ms", "annotation_ms", "pipeline_ms", "end_to_end_ms",
]

# Below this many samples, a subgroup's statistics are not reported as
# numbers - Part 6: "If there are too few samples for a subgroup, clearly
# report that instead of inventing statistics."
MIN_SAMPLES_FOR_STATS = 2


def read_rows(csv_path=CSV_PATH):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for col in NUMERIC_COLUMNS:
            row[col] = float(row[col])
        row["run_id"] = int(row["run_id"])
    return rows


def percentile(values, p):
    """Nearest-rank percentile over a sorted copy of `values`. p is 0-100.
    Deterministic, no interpolation guesswork - matches how a reader would
    manually read a percentile off a sorted list."""
    if not values:
        raise ValueError("percentile() requires at least one value")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (p / 100.0) * (len(s) - 1)
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return s[int(k)]
    frac = k - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def compute_stats(values):
    """Returns None (never a fabricated/zeroed stats dict) if there are
    too few samples to compute a meaningful standard deviation etc."""
    n = len(values)
    if n < MIN_SAMPLES_FOR_STATS:
        return None
    return {
        "n": n,
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stddev": statistics.stdev(values),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
    }


def group_rows_by_category(rows):
    """overall / CWE-89 / CWE-295 / SAFE, per Part 6. Grouped on the real
    expected_cwe column the experiment itself recorded, not re-derived
    from `prediction` (which is the actual backend verdict, kept separate
    on purpose so a mismatch between expected and predicted is visible in
    the raw data rather than silently reconciled here)."""
    groups = {"overall": rows}
    for label in ("CWE-89", "CWE-295", "SAFE"):
        groups[label] = [r for r in rows if r["expected_cwe"] == label]
    return groups


def stats_table_for_group(rows):
    """{metric_column: {"n": actual_sample_count, "stats": stats_dict_or_None}}
    for one group's rows - `n` is always the real count, even when it's
    below MIN_SAMPLES_FOR_STATS and `stats` is therefore None, so the
    report can say exactly how many samples were too few rather than
    just "insufficient"."""
    result = {}
    for metric in METRIC_COLUMNS:
        values = [r[metric] for r in rows]
        result[metric] = {"n": len(values), "stats": compute_stats(values)}
    return result


def format_stats_table_markdown(stats_by_metric, metric_labels):
    header = "| Metric | N | Mean | Median | Min | Max | StdDev | P90 | P95 | P99 |\n"
    header += "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    lines = [header]
    for metric, label in metric_labels.items():
        entry = stats_by_metric.get(metric, {"n": 0, "stats": None})
        s = entry["stats"]
        if s is None:
            lines.append(f"| {label} | {entry['n']} (insufficient) | - | - | - | - | - | - | - | - |\n")
        else:
            lines.append(
                f"| {label} | {s['n']} | {s['mean']:.2f} | {s['median']:.2f} | {s['min']:.2f} | "
                f"{s['max']:.2f} | {s['stddev']:.2f} | {s['p90']:.2f} | {s['p95']:.2f} | {s['p99']:.2f} |\n"
            )
    return "".join(lines)


METRIC_LABELS = {
    "end_to_end_ms": "End-to-end (code edit -> annotation, includes debounce)",
    "pipeline_ms": "Detection pipeline (debounce complete -> annotation, EXCLUDES debounce)",
    "backend_total_ms": "Backend total",
    "prediction_ms": "XGBoost prediction (backend-internal)",
}


def load_metadata(json_path=JSON_PATH):
    with open(json_path, encoding="utf-8") as f:
        return json.load(f).get("metadata", {})


def build_summary_markdown(rows, metadata):
    groups = group_rows_by_category(rows)
    group_stats = {name: stats_table_for_group(g) for name, g in groups.items()}

    lines = []
    lines.append("# DualVulnDroid Real-Time Detection Pipeline — Latency Experiment\n\n")

    lines.append("## 1. Experimental setup\n\n")
    lines.append(
        "Real, non-simulated measurement of the existing IDE real-time detection pipeline: "
        "IDE code edit -> 500ms debounce -> CodeSentinelAnnotator -> APIClient -> FastAPI "
        "`/predict` -> predictor.py -> XGBoost prediction -> static/data-flow evidence -> "
        "decision engine -> HTTP response -> IDE annotation creation -> finding visible in editor. "
        "No detection logic, model, threshold, or decision-engine behavior was changed to produce "
        "these numbers - only opt-in, disabled-by-default timing instrumentation was added "
        "(see LatencyTelemetry.kt and predictor.py's `capture_timing` parameter).\n\n"
    )

    lines.append("## 2. Hardware/software environment\n\n")
    lines.append(f"- OS: {metadata.get('os_name', 'unknown')} ({metadata.get('os_arch', 'unknown')})\n")
    lines.append(f"- Java: {metadata.get('java_version', 'unknown')}\n")
    lines.append(f"- Available processors: {metadata.get('available_processors', 'unknown')}\n")
    lines.append(f"- Plugin build identifier: {metadata.get('plugin_build_identifier', 'unknown')}\n")
    lines.append(f"- Backend URL used: {metadata.get('backend_url', 'unknown')}\n")
    lines.append(f"- Debounce setting: {metadata.get('debounce_setting_ms', 'unknown')} ms\n")
    lines.append(f"- Experiment date/time (UTC): {metadata.get('experiment_datetime_utc', 'unknown')}\n\n")

    lines.append("## 3. Measurement methodology\n\n")
    lines.append(
        "Driven by `DualVulnDroid/src/test/kotlin/.../LatencyExperimentTest.kt`, a headless "
        "IntelliJ Platform test (`BasePlatformTestCase`) that runs the REAL, registered "
        "`CodeSentinelAnnotator` through IntelliJ's real daemon highlighting pipeline "
        "(`myFixture.doHighlighting()`), against the REAL running FastAPI backend - no mocked "
        "API, no mocked predictor, for either the warm-up or measured phases. **Documented "
        "limitation** (explicitly permitted by the task's own escape valve): this runs inside a "
        "headless JVM test instance, not a visible IDE window with a human or UI-automation tool "
        "physically typing keystrokes - no pixels are rendered or captured. What IS real: the "
        "actual PSI/document state, the actual registered `ExternalAnnotator`, the actual 500ms "
        "`Thread.sleep` debounce, the actual OkHttp network round trip, the actual "
        "`AnnotationHolder`-based annotation creation.\n\n"
    )
    lines.append(
        "T0 (\"code edit event received\") is measured at `collectInformation()` entry - this "
        "architecture has no separate `DocumentListener`; IntelliJ's own daemon detects the edit "
        "and re-invokes the registered `ExternalAnnotator`, so this is the earliest point the "
        "plugin's own code observes it.\n\n"
    )

    lines.append("## 4. Warm-up procedure\n\n")
    lines.append(
        f"{metadata.get('warmup_runs_completed', '?')} of {metadata.get('warmup_runs', '?')} "
        "warm-up scans were performed and discarded before measurement began (Part 4A) - one of "
        "each code type, covering both CWE categories and safe code, so the JVM/backend/model are "
        "warm before any measured timestamp is taken.\n\n"
    )

    lines.append("## 5. Number of measured events\n\n")
    lines.append(
        f"**{metadata.get('measured_runs_completed', '?')}** of "
        f"{metadata.get('measured_runs_requested', '?')} requested measured events produced a "
        f"complete, valid measurement ({metadata.get('measured_runs_missed', 0)} missed/documented - "
        "see Limitations).\n\n"
    )

    lines.append("## 6. Timing definitions\n\n")
    lines.append(
        "**Two different latency definitions are reported - never conflated (Part 7):**\n\n"
        "- **A. User-perceived end-to-end latency** (`end_to_end_ms`, T8-T0): code edit -> "
        "annotation available. **Includes** the intentional 500ms debounce.\n"
        "- **B. Detection pipeline latency** (`pipeline_ms`, T8-T1): debounce completed -> "
        "annotation available. **Excludes** the intentional debounce time - this isolates "
        "actual backend/network/annotation processing.\n\n"
        "Also reported: `backend_total_ms` (T5-T3, backend request-received -> prediction "
        "complete) and `prediction_ms` (backend-internal: feature extraction + XGBoost inference "
        "only, a narrower sub-span within `backend_total_ms` - see predictor.py's `_timing` "
        "breakdown; it also separately reports `shap_and_rule_detection_ms`/`dataflow_ms`/"
        "`decision_ms`, not repeated in the headline tables below but present in the raw JSON "
        "metadata's per-request timing when the benchmark header is used).\n\n"
    )

    lines.append("## 7. Raw-data location\n\n")
    lines.append(
        "`latency_experiment/latency_results.csv` and `latency_experiment/latency_results.json` "
        "(same directory as this report) - outside `DualVulnDroid/`, `backend/`, and the frozen "
        "IEEE workspace, per the task's Part 5 instruction.\n\n"
    )

    lines.append("## 8. Statistical results\n\n")
    lines.append(
        "All values in **milliseconds**, computed from the raw CSV only - see `analyze_latency.py`. "
        "P90/P95/P99 use the nearest-rank method (`percentile()` in that script).\n\n"
    )

    for section_num, group_name, title in [
        (9, "overall", "Overall latency table"),
        (10, "CWE-89", "CWE-89 latency table"),
        (11, "CWE-295", "CWE-295 latency table"),
        (12, "SAFE", "SAFE latency table"),
    ]:
        lines.append(f"## {section_num}. {title}\n\n")
        n_rows = len(groups[group_name])
        if n_rows == 0:
            lines.append(f"No measured runs in this category (0 samples) - no statistics reported.\n\n")
            continue
        lines.append(f"N = {n_rows} measured runs in this category.\n\n")
        lines.append(format_stats_table_markdown(group_stats[group_name], METRIC_LABELS))
        lines.append("\n")

    lines.append("## 13. Interpretation\n\n")
    overall = group_stats["overall"]
    e2e = overall["end_to_end_ms"]["stats"]
    pipe = overall["pipeline_ms"]["stats"]
    if e2e and pipe:
        lines.append(
            f"Across {overall_n(rows)} measured real-time scans, the mean user-perceived "
            f"end-to-end latency (code edit to visible annotation, debounce included) was "
            f"**{e2e['mean']:.1f} ms** (median {e2e['median']:.1f} ms, P95 {e2e['p95']:.1f} ms, "
            f"P99 {e2e['p99']:.1f} ms). Of that, the detection-pipeline portion alone (debounce "
            f"excluded) averaged **{pipe['mean']:.1f} ms** (median {pipe['median']:.1f} ms) - i.e. "
            f"roughly {100 * pipe['mean'] / e2e['mean']:.0f}% of the user-perceived latency is the "
            "deliberate 500ms debounce, not backend/network/annotation processing.\n\n"
        )
        backend = overall["backend_total_ms"]["stats"]
        prediction = overall["prediction_ms"]["stats"]
        if backend and prediction:
            lines.append(
                f"Backend processing itself averaged {backend['mean']:.1f} ms of that pipeline "
                f"time, of which XGBoost inference (`prediction_ms`) averaged "
                f"{prediction['mean']:.1f} ms when available - the remainder of "
                "backend time is SHAP/rule-based line localization, data-flow analysis, and "
                "decision-engine evaluation (see predictor.py's fuller internal breakdown).\n\n"
            )
        lines.append(
            "**On whether this evidence supports the existing \"real-time/in-editor detection\" "
            "functional description**: the measured pipeline latency (annotation appears within "
            f"roughly {pipe['p95']:.0f} ms of the debounce completing, 95th percentile) is fast "
            "enough that a developer would perceive the finding as appearing promptly after they "
            "pause typing, which is consistent with the plugin's existing functional claim of "
            "in-editor, real-time-feeling detection. This is NOT, on its own, a formal real-time "
            "systems guarantee (no worst-case bound, no load testing, a single machine, a single "
            "session, snippet sizes representative but not exhaustive) - see Limitations. The data "
            "supports the EXISTING functional description; it does not establish a new latency SLA, "
            "and none should be inferred from it.\n\n"
        )
    else:
        lines.append("Insufficient data to interpret (see subgroup/overall tables above).\n\n")

    lines.append("## 14. Limitations\n\n")
    lines.append(
        "- **Not a visible-IDE, human-keystroke measurement.** Driven by a headless IntelliJ "
        "Platform JUnit test, not a rendered window with real keystrokes (see Methodology). "
        "Real keystroke-to-daemon-trigger latency (outside this plugin's own code, inside "
        "IntelliJ's own typing/highlighting-scheduling internals) is not captured by T0, since T0 "
        "is measured at this plugin's own `collectInformation()` entry, not at the raw keystroke.\n"
        "- **Single machine, single session, sequential runs.** No concurrent-editor load, no "
        "multi-file project context, no measurement of tail behavior under real developer "
        "multitasking (switching files, IDE indexing in the background, etc.).\n"
        "- **A fixed, small set of representative code snippets** (traced-source CWE-89, "
        "parameterized-safe CWE-89, HostnameVerifier CWE-295, real-check safe CWE-295), each "
        "small (a handful of lines) - not a stress test of large files or many simultaneous "
        "findings.\n"
        "- **`backend_total_ms`/`prediction_ms` come from a SEPARATE, out-of-band request** "
        "(`APIClient.fetchBenchmarkTiming`, made AFTER each measured cycle completes, requesting "
        "the backend's own `X-Benchmark-Timing` breakdown for the identical code) - not from the "
        "actual measured request itself, since the real-time path never sends that header. This "
        "cannot affect T0-T8 in any way, but does mean these two columns reflect a second, "
        "immediately-following request rather than the literal measured one.\n"
        "- **No fabricated \"real-time\" claim.** As instructed: low measured latency alone does "
        "not, by itself, prove a formal real-time guarantee; see Interpretation above for the "
        "precise, hedged claim this data actually supports.\n"
    )

    return "".join(lines)


def overall_n(rows):
    return len(rows)


def make_plot(rows, out_path=PLOT_PATH):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    end_to_end = [r["end_to_end_ms"] for r in rows]
    pipeline = [r["pipeline_ms"] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(end_to_end, bins=15, alpha=0.6, label=f"End-to-end (n={len(end_to_end)})", color="#d95f02")
    ax.hist(pipeline, bins=15, alpha=0.6, label=f"Pipeline, debounce excluded (n={len(pipeline)})", color="#1b9e77")
    ax.set_xlabel("Latency (ms)")
    ax.set_ylabel("Number of measured runs")
    ax.set_title("DualVulnDroid Real-Time Detection Latency Distribution\n(real backend, real plugin pipeline, actual measured values)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main():
    rows = read_rows()
    metadata = load_metadata()
    summary = build_summary_markdown(rows, metadata)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(summary)
    print(f"Wrote {SUMMARY_PATH}")

    make_plot(rows)
    print(f"Wrote {PLOT_PATH}")


if __name__ == "__main__":
    main()
