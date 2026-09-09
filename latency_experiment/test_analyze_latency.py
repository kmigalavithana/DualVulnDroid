"""
Latency-measurement experiment task, Part 10 items 7/8 (plus general
correctness): tests for analyze_latency.py's pure statistics/grouping
functions. No backend, no IDE, no file I/O beyond temp files.
"""
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import analyze_latency as al


# ---- 7. Percentile calculation ----

def test_percentile_of_single_value_is_that_value():
    assert al.percentile([42.0], 95) == 42.0


def test_percentile_p50_matches_median_for_odd_count():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert al.percentile(values, 50) == 3.0


def test_percentile_p0_and_p100_are_min_and_max():
    values = [5.0, 1.0, 9.0, 3.0]
    assert al.percentile(values, 0) == 1.0
    assert al.percentile(values, 100) == 9.0


def test_percentile_known_interpolated_value():
    # sorted: [10, 20, 30, 40] -> index space 0..3; p90 -> k = 0.9*3 = 2.7
    # -> between index 2 (30) and 3 (40), frac 0.7 -> 30 + 0.7*10 = 37.0
    values = [40.0, 10.0, 30.0, 20.0]
    assert abs(al.percentile(values, 90) - 37.0) < 1e-9


def test_percentile_rejects_empty_list():
    try:
        al.percentile([], 50)
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---- 8. Insufficient subgroup handling ----

def test_compute_stats_returns_none_below_minimum_sample_size():
    assert al.compute_stats([]) is None
    assert al.compute_stats([1.0]) is None  # MIN_SAMPLES_FOR_STATS == 2


def test_compute_stats_returns_real_values_at_minimum_sample_size():
    stats = al.compute_stats([10.0, 20.0])
    assert stats is not None
    assert stats["n"] == 2
    assert stats["mean"] == 15.0
    assert stats["min"] == 10.0
    assert stats["max"] == 20.0


def test_stats_table_reports_insufficient_n_honestly_not_fabricated_numbers():
    rows = [{"end_to_end_ms": 100.0, "pipeline_ms": 50.0, "backend_total_ms": 10.0, "prediction_ms": 2.0}]
    table = al.stats_table_for_group(rows)
    assert table["end_to_end_ms"]["n"] == 1
    assert table["end_to_end_ms"]["stats"] is None  # 1 sample is below the minimum - never fabricated

    md = al.format_stats_table_markdown(table, al.METRIC_LABELS)
    assert "insufficient" in md
    assert "1" in md  # the real count is still shown, not hidden


def test_group_rows_by_category_separates_overall_and_each_cwe():
    rows = [
        {"expected_cwe": "CWE-89"}, {"expected_cwe": "CWE-89"},
        {"expected_cwe": "CWE-295"},
        {"expected_cwe": "SAFE"}, {"expected_cwe": "SAFE"}, {"expected_cwe": "SAFE"},
    ]
    groups = al.group_rows_by_category(rows)
    assert len(groups["overall"]) == 6
    assert len(groups["CWE-89"]) == 2
    assert len(groups["CWE-295"]) == 1
    assert len(groups["SAFE"]) == 3


def test_group_with_zero_samples_is_empty_not_an_error():
    rows = [{"expected_cwe": "CWE-89"}]
    groups = al.group_rows_by_category(rows)
    assert groups["CWE-295"] == []


# ---- read_rows / CSV round trip sanity ----

def test_read_rows_parses_numeric_columns_as_floats(tmp_path):
    csv_path = tmp_path / "sample.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "run_id", "language", "code_type", "expected_cwe", "prediction",
            "debounce_ms", "request_ms", "backend_total_ms", "prediction_ms",
            "plugin_response_ms", "annotation_ms", "pipeline_ms", "end_to_end_ms", "timestamp",
        ])
        writer.writerow(["1", "java", "cwe89_vulnerable", "CWE-89", "SQL Injection",
                          "500.0", "100.0", "50.0", "10.0", "1.0", "2.0", "103.0", "603.0", "2026-01-01T00:00:00Z"])
    rows = al.read_rows(str(csv_path))
    assert len(rows) == 1
    assert isinstance(rows[0]["end_to_end_ms"], float)
    assert rows[0]["end_to_end_ms"] == 603.0
    assert isinstance(rows[0]["run_id"], int)
