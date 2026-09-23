import '../models/recommendation_result_model.dart';

/// Two views of the SAME result set, used to show what personalization
/// changes:
///   * "For you" - SmartApp's own ranking (RecommendationEngine order).
///   * "Popular" - the generic view anyone would get: Google Play rating,
///     then review count; apps without a rating last. No SmartApp score is
///     involved.

/// [forYou] re-sorted by public popularity. Stable, deterministic tie-break
/// by name.
List<RecommendationResult> popularOrder(List<RecommendationResult> forYou) {
  final sorted = [...forYou];
  sorted.sort((a, b) {
    final ra = a.app.rating, rb = b.app.rating;
    if (ra == null && rb != null) return 1;
    if (rb == null && ra != null) return -1;
    if (ra != null && rb != null && ra != rb) return rb.compareTo(ra);
    final ca = a.app.reviewCount ?? -1, cb = b.app.reviewCount ?? -1;
    if (ca != cb) return cb.compareTo(ca);
    return a.app.name.compareTo(b.app.name);
  });
  return sorted;
}

String _key(RecommendationResult r) => r.app.packageName ?? r.app.id;

/// For each app: how many places it moved in "For you" compared with
/// "Popular". Positive = ranked higher for this user than by popularity.
Map<String, int> positionShifts(List<RecommendationResult> forYou) {
  final popular = popularOrder(forYou);
  final popularIndex = {for (var i = 0; i < popular.length; i++) _key(popular[i]): i};
  return {for (var i = 0; i < forYou.length; i++) _key(forYou[i]): popularIndex[_key(forYou[i])]! - i};
}

/// 1-based position of [result] in [order].
int positionIn(List<RecommendationResult> order, RecommendationResult result) =>
    order.indexWhere((r) => _key(r) == _key(result)) + 1;

String shiftKey(RecommendationResult r) => _key(r);
