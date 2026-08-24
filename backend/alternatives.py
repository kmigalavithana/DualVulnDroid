"""
Phase 8C, Parts K/L: deterministic, real-data-only alternative-application
ranking. Never fabricates a candidate, a score, a rating, a download
count, popularity, or a Play Store ranking - every field returned here
comes from a real, already-stored Application/Scan row. No new security
score is computed; the existing decision engine's real security_score/
risk_level/confidence are reused as-is.

Pure and deterministic: no I/O, no database access. Callers (app.py) are
responsible for fetching real (application, latest_scan) pairs from the
database and passing them in.

This is a SEPARATE mechanism from db.crud.get_alternatives(), which only
returns explicitly-curated AlternativeApp links (a human/future-process
curated a specific pair). That mechanism is untouched and still checked
first (see app.py) - this module is the fallback deterministic ranking
used when no curator has linked anything yet, which today is effectively
always, since nothing currently populates alternative_apps.
"""

from typing import Optional

HIGH_RISK_LEVELS = {"HIGH", "CRITICAL"}
_RISK_SEVERITY = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def filter_candidates(target_application, target_risk_level: Optional[str], candidates: list) -> list:
    """
    candidates: list of dicts, each already carrying real data the
    caller fetched: {"application": <Application row>, "risk_level": str|None,
    "security_score": int|None, "confidence": int|None}.

    Filters applied (Part K):
      1. Same category as the target - ONLY applied when the target's
         own category is actually known (non-None/non-empty). An unknown
         target category does not exclude every candidate; it simply
         means this filter is skipped, never "assume equivalence" and
         never "assume everything is disqualified" either.
      2/4. The candidate has a real, complete assessment: a non-null
         risk_level (both "has been assessed" and "assessment data is
         usable for ranking" collapse to this one real signal - there is
         no separate synthetic "completeness" concept in the schema to
         check beyond this).
      3. The candidate is not the target application itself.
      5. The candidate's risk_level is not HIGH/CRITICAL.
    """
    target_category = getattr(target_application, "category", None)
    result = []
    for candidate in candidates:
        app = candidate["application"]
        if app.id == target_application.id:
            continue
        risk_level = candidate.get("risk_level")
        if not risk_level:
            continue
        if risk_level.upper() in HIGH_RISK_LEVELS:
            continue
        if target_category and app.category and app.category != target_category:
            continue
        result.append(candidate)
    return result


def rank_alternatives(target_application, target_risk_level: Optional[str], candidates: list,
                       limit: int = 5) -> list:
    """
    Filters (see filter_candidates) then ranks by real assessed risk
    (lower severity first), breaking ties by real security_score
    (higher first, treating a missing score as the worst tiebreak value
    rather than best - never lets an absent score look artificially
    good). Every result carries transparent, specifically-true reasons -
    never a fixed boilerplate pair, never an unexplained score.
    """
    filtered = filter_candidates(target_application, target_risk_level, candidates)

    def _sort_key(candidate):
        severity = _RISK_SEVERITY.get((candidate.get("risk_level") or "").upper(), 99)
        score = candidate.get("security_score")
        score_key = -(score if score is not None else -1)
        return (severity, score_key)

    ranked = sorted(filtered, key=_sort_key)[:limit]

    results = []
    for candidate in ranked:
        app = candidate["application"]
        reasons = []
        risk_level = candidate.get("risk_level")
        if target_risk_level and risk_level and _RISK_SEVERITY.get(risk_level.upper(), 99) < _RISK_SEVERITY.get(target_risk_level.upper(), 99):
            reasons.append(f"Lower assessed security risk ({risk_level}) than the selected application ({target_risk_level}).")
        target_category = getattr(target_application, "category", None)
        if target_category and app.category and app.category == target_category:
            reasons.append(f"Same verified application category ({app.category}).")
        if not reasons:
            reasons.append("Assessed and not classified as high or critical risk.")

        results.append({
            "applicationId": app.id,
            "name": app.app_name,
            "packageName": app.package_name,
            "riskLevel": risk_level,
            "securityScore": candidate.get("security_score"),
            "securityConfidence": candidate.get("confidence"),
            "reasons": reasons,
        })
    return results
