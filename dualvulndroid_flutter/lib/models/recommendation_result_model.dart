import 'app_info_model.dart';
import 'context_effect_model.dart';

/// The six calculated sub-scores behind one app's final recommendation
/// score, each already 0-100-scale-derived and already weighted - i.e.
/// `preference + device + privacy + resource + rating + context` sums to
/// [finalScore]. Kept as named fields (not a `Map<String,double>`) so the
/// "Why this app?" breakdown can never silently drop or mislabel a
/// component.
///
/// [context] is the one field NOT drawn from the five fixed weights
/// (30/25/20/15/10) - it is a small, bounded (±10) transparent adjustment
/// from real, active [ContextEffect]s (low storage/RAM/battery, offline),
/// kept as a separate addend rather than folded into the weighted five so
/// the base weights always mean exactly what they say (Part 6: "modify
/// recommendations based on context" without "silently changing" the
/// preference-driven weighting).
///
/// Availability-aware: a factor with no verified data for this app is
/// marked unavailable in [available], contributes 0, and its weight is
/// shared proportionally across the available factors
/// ([effectiveWeights], which always sum to 1 over the available ones) -
/// "unknown" is never scored as good or bad.
class ScoreBreakdown {
  final double preference;
  final double device;
  final double privacy;
  final double resource;
  final double rating;
  final double context;

  /// Per factor, in [factorOrder]: was it scored from verified data?
  final List<bool> available;

  /// Per factor, in [factorOrder]: the weight actually applied (0 when
  /// unavailable; the available ones sum to 1).
  final List<double> effectiveWeights;

  /// Per factor, in [factorOrder]: where the evidence came from (e.g.
  /// "Google Play rating", "Verified by εxodus"), when worth showing.
  final List<String?> evidence;

  static const factorOrder = ['preference', 'device', 'privacy', 'resource', 'rating'];

  const ScoreBreakdown({
    required this.preference,
    required this.device,
    required this.privacy,
    required this.resource,
    required this.rating,
    this.context = 0,
    this.available = const [true, true, true, true, true],
    this.effectiveWeights = const [0.30, 0.25, 0.20, 0.15, 0.10],
    this.evidence = const [null, null, null, null, null],
  });

  /// How many of the five factors were scored from verified data.
  int get availableFactorCount => available.where((a) => a).length;

  /// No factor could be verified - there is nothing honest to score.
  bool get hasVerifiedFactors => availableFactorCount > 0;

  double get finalScore => (preference + device + privacy + resource + rating + context).clamp(0.0, 100.0);
}

/// One short, human-readable reason string plus whether it reflects a
/// positive contribution (checkmark) or a caveat - generated only from
/// attributes that actually contributed to the score (Part 9/10: "Do not
/// display fake reasons").
class RecommendationReason {
  final String text;
  final bool isPositive;

  const RecommendationReason(this.text, {this.isPositive = true});
}

/// One line of the "Why this app?" point breakdown (Part 7): a named
/// scoring dimension, how many of its points this app actually earned,
/// and the maximum points available for that dimension. [earnedPoints]
/// and [maxPoints] are both already-rounded, display-ready integers
/// derived directly from the same [ScoreBreakdown] the rest of the UI
/// uses - never a separately-invented number.
class ExplanationFactor {
  final String label;
  final int earnedPoints;

  /// This factor's share of the match score for THIS app - its base
  /// weight, rescaled when other factors were unavailable. 0 when the
  /// factor itself is unavailable.
  final int maxPoints;

  /// Whether this factor was scored from verified data. When false,
  /// [earnedPoints] and [maxPoints] are 0 and the UI shows "Not enough
  /// verified data" instead of points.
  final bool available;

  /// Where the evidence came from, when worth showing.
  final String? evidence;

  const ExplanationFactor({
    required this.label,
    required this.earnedPoints,
    required this.maxPoints,
    this.available = true,
    this.evidence,
  });
}

/// The full, explainable result of scoring one [AppInfo] against the
/// user's preferences and device context.
class RecommendationResult {
  final AppInfo app;
  final ScoreBreakdown breakdown;
  final List<RecommendationReason> reasons;

  /// Real, calculated 0-1 measure of how much of the data this score
  /// depended on was actually available (device signals, a user rating,
  /// at least one selected preference) - low confidence means the score
  /// leaned on neutral fallbacks, not that the app is a bad match. Never
  /// a fabricated/ML confidence value; see RecommendationEngine.confidence.
  final double confidence;

  /// The real, currently-active device-context effects (low storage/RAM/
  /// battery, offline) that influenced [ScoreBreakdown.context] for this
  /// result - shown transparently rather than left as an unexplained
  /// number (Part 6: "Show context effects transparently").
  final List<ContextEffect> activeContextEffects;

  /// Hard constraints that could not be checked for this app because the
  /// data isn't verified (e.g. "Free only" with an unknown price). The app
  /// is kept - unknown is neither a pass nor a fail - and the UI shows
  /// these as "Not verified".
  final List<String> unverifiedConstraints;

  const RecommendationResult({
    required this.app,
    required this.breakdown,
    required this.reasons,
    this.confidence = 1.0,
    this.activeContextEffects = const [],
    this.unverifiedConstraints = const [],
  });

  RecommendationResult withUnverifiedConstraints(List<String> constraints) => RecommendationResult(
        app: app,
        breakdown: breakdown,
        reasons: reasons,
        confidence: confidence,
        activeContextEffects: activeContextEffects,
        unverifiedConstraints: constraints,
      );

  /// See [ScoreBreakdown.hasVerifiedFactors].
  bool get hasVerifiedFactors => breakdown.hasVerifiedFactors;
  int get availableFactorCount => breakdown.availableFactorCount;

  /// Rounded 0-100 match percentage for display - rounding happens only
  /// here, at the presentation boundary, so internal comparisons/sorting
  /// always use the unrounded [ScoreBreakdown.finalScore].
  int get matchPercent => breakdown.finalScore.round().clamp(0, 100);

  // ---- Spec-named aliases onto the same ScoreBreakdown fields, so this
  // result can be read either way without two sources of truth. ----
  double get finalScore => breakdown.finalScore;
  double get preferenceScore => breakdown.preference;
  double get deviceScore => breakdown.device;
  double get privacyScore => breakdown.privacy;
  double get resourceScore => breakdown.resource;
  double get ratingScore => breakdown.rating;

  /// The "Why this app?" point breakdown (Part 7's "Preference Match
  /// 28/30" display), built only from [breakdown] and the engine's own
  /// fixed weight budgets - never a separate calculation.
  ///
  /// Rounds all five weighted sub-scores together via the "largest
  /// remainder" method rather than rounding each independently: the five
  /// values are real (non-integer) doubles - e.g. a device-suitability
  /// contribution of 23.75 - so rounding each on its own can make the
  /// displayed points sum to a different number than the true total
  /// rounds to (verified case: 15.0+23.75+10.0+4.5+8.2 = 61.45, which
  /// rounds to 61, but 15+24+10+5+8 = 62 if each is rounded separately).
  /// Largest-remainder rounding guarantees the five displayed integers
  /// always sum to exactly `round(preference+device+privacy+resource+rating)`.
  ///
  /// [maxPoints] is each factor's effective share (base weight rescaled
  /// over the available factors), rounded the same way so the available
  /// maxima always sum to exactly 100.
  List<ExplanationFactor> get explanationFactors {
    const labels = ['Preference Match', 'Device Suitability', 'Privacy', 'Resource Efficiency', 'Rating'];
    final points = _largestRemainderRound([preferenceScore, deviceScore, privacyScore, resourceScore, ratingScore]);
    final maxima = _largestRemainderRound(breakdown.effectiveWeights.map((w) => w * 100).toList());
    return List.generate(
      5,
      (i) => ExplanationFactor(
        label: labels[i],
        earnedPoints: breakdown.available[i] ? points[i] : 0,
        maxPoints: breakdown.available[i] ? maxima[i] : 0,
        available: breakdown.available[i],
        evidence: breakdown.evidence[i],
      ),
    );
  }

  /// The context-effect contribution actually reflected in [matchPercent],
  /// derived from the displayed total (matchPercent minus the displayed
  /// factor points) rather than independently rounding
  /// [ScoreBreakdown.context] - guarantees
  /// `explanationFactors` points + this value always sum to exactly
  /// [matchPercent], even through the 0-100 clamp on an extreme (all
  /// dimensions maxed out plus a positive context bonus) score.
  int get contextAdjustmentPoints => matchPercent - explanationFactors.fold(0, (sum, f) => sum + f.earnedPoints);
}

/// Rounds [values] to integers using the "largest remainder" method so
/// they sum to exactly `round(sum(values))`, instead of each value being
/// rounded independently (which can make displayed parts disagree with
/// the displayed total).
List<int> _largestRemainderRound(List<double> values) {
  final target = values.fold(0.0, (a, b) => a + b).round();
  final floors = values.map((v) => v.floor()).toList();
  final flooredSum = floors.fold(0, (a, b) => a + b);
  final remaining = (target - flooredSum).clamp(0, values.length);
  final remainders = List.generate(values.length, (i) => values[i] - floors[i]);
  final order = List.generate(values.length, (i) => i)..sort((a, b) => remainders[b].compareTo(remainders[a]));
  final result = List<int>.from(floors);
  for (var i = 0; i < remaining; i++) {
    result[order[i]] += 1;
  }
  return result;
}
