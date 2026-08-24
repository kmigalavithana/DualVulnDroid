"""
Phase 8C, Parts K/L: unit tests for alternatives.py's pure, deterministic
ranking functions. alternatives.py never touches the database itself, so
these tests use lightweight duck-typed stand-ins for Application rows
(only .id/.app_name/.package_name/.category are ever read) rather than a
real DB session - consistent with compatibility.py's testing style.
"""

from types import SimpleNamespace

import alternatives


def _app(id, app_name, package_name=None, category=None):
    return SimpleNamespace(id=id, app_name=app_name, package_name=package_name, category=category)


def _candidate(app, risk_level=None, security_score=None, confidence=None):
    return {"application": app, "risk_level": risk_level, "security_score": security_score, "confidence": confidence}


# =====================================================
# 24. No alternatives
# =====================================================
def test_no_alternatives_when_no_candidates():
    target = _app(1, "Target App", category="Finance")
    result = alternatives.rank_alternatives(target, "HIGH", candidates=[])
    assert result == []


def test_no_alternatives_when_all_candidates_filtered_out():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Risky Other App", category="Finance"), risk_level="HIGH", security_score=20)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert result == []


# =====================================================
# 25. Same-category candidates
# =====================================================
def test_same_category_candidates_are_included():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Other Finance App", category="Finance"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert len(result) == 1
    assert result[0]["applicationId"] == 2


def test_different_category_candidate_excluded_when_target_category_known():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Unrelated Weather App", category="Weather"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert result == []


# =====================================================
# 26. Higher-risk candidate excluded
# =====================================================
def test_high_risk_candidate_is_excluded():
    target = _app(1, "Target App", category="Finance")
    candidates = [
        _candidate(_app(2, "Low Risk App", category="Finance"), risk_level="LOW", security_score=90),
        _candidate(_app(3, "High Risk App", category="Finance"), risk_level="HIGH", security_score=20),
    ]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    ids = [r["applicationId"] for r in result]
    assert 2 in ids
    assert 3 not in ids


def test_critical_risk_candidate_is_excluded():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Critical App", category="Finance"), risk_level="CRITICAL", security_score=5)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert result == []


# =====================================================
# 27. Unknown category handled safely
# =====================================================
def test_unknown_target_category_does_not_exclude_every_candidate():
    target = _app(1, "Target App", category=None)
    candidates = [_candidate(_app(2, "Some App", category="Finance"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert len(result) == 1


def test_unknown_candidate_category_does_not_wrongly_match_a_known_target_category():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Some App", category=None), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    # Still included (category filter only excludes on a real mismatch,
    # per Part K: "do not assume category equivalence if category is
    # missing" - an unknown candidate category isn't a mismatch either)...
    assert len(result) == 1
    # ...but the "same category" reason is never claimed since it isn't
    # actually known to be true.
    assert not any("category" in r.lower() for r in result[0]["reasons"])


# =====================================================
# 28. Selected application excluded
# =====================================================
def test_target_application_never_appears_in_its_own_alternatives():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(target, risk_level="LOW", security_score=95)]  # target somehow in the candidate pool
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert result == []


# =====================================================
# 29. Deterministic ranking
# =====================================================
def test_ranking_is_deterministic_across_repeated_calls():
    target = _app(1, "Target App", category="Finance")
    candidates = [
        _candidate(_app(2, "App B", category="Finance"), risk_level="LOW", security_score=70),
        _candidate(_app(3, "App C", category="Finance"), risk_level="LOW", security_score=95),
        _candidate(_app(4, "App D", category="Finance"), risk_level="MEDIUM", security_score=99),
    ]
    first = alternatives.rank_alternatives(target, "HIGH", candidates)
    second = alternatives.rank_alternatives(target, "HIGH", list(reversed(candidates)))
    assert [r["applicationId"] for r in first] == [r["applicationId"] for r in second]
    # LOW risk beats MEDIUM regardless of score; within LOW, higher score first.
    assert [r["applicationId"] for r in first] == [3, 2, 4]


def test_ranking_respects_limit():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(i, f"App {i}", category="Finance"), risk_level="LOW", security_score=i) for i in range(2, 12)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates, limit=3)
    assert len(result) == 3


# =====================================================
# 30. Transparent ranking reasons
# =====================================================
def test_ranking_reasons_reflect_real_lower_risk():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Safer App", category="Finance"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert any("Lower assessed security risk" in r for r in result[0]["reasons"])
    assert any("LOW" in r and "HIGH" in r for r in result[0]["reasons"])


def test_ranking_reasons_reflect_real_shared_category():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Safer App", category="Finance"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert any("Same verified application category" in r and "Finance" in r for r in result[0]["reasons"])


def test_no_unexplained_black_box_score_field():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Safer App", category="Finance"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    # Only real, existing fields - no invented "matchScore"/"rank" etc.
    assert set(result[0].keys()) == {"applicationId", "name", "packageName", "riskLevel", "securityScore", "securityConfidence", "reasons"}


# =====================================================
# 31. No fake applications
# =====================================================
def test_every_returned_field_traces_back_to_a_real_candidate_value():
    target = _app(1, "Target App", category="Finance")
    real_app = _app(2, "Real Safer App", package_name="com.real.safer", category="Finance")
    candidates = [_candidate(real_app, risk_level="LOW", security_score=88, confidence=77)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    entry = result[0]
    assert entry["applicationId"] == real_app.id
    assert entry["name"] == real_app.app_name
    assert entry["packageName"] == real_app.package_name
    assert entry["securityScore"] == 88
    assert entry["securityConfidence"] == 77


def test_never_fabricates_download_counts_ratings_or_popularity():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Safer App", category="Finance"), risk_level="LOW", security_score=90)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    forbidden = {"downloads", "downloadCount", "rating", "ratings", "popularity", "playStoreRank", "reviews"}
    assert not (forbidden & set(result[0].keys()))


def test_candidate_missing_risk_level_is_excluded_never_ranked_as_a_guess():
    target = _app(1, "Target App", category="Finance")
    candidates = [_candidate(_app(2, "Unassessed App", category="Finance"), risk_level=None, security_score=None)]
    result = alternatives.rank_alternatives(target, "HIGH", candidates)
    assert result == []
