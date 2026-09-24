import '../models/app_info_model.dart';
import '../models/context_effect_model.dart';
import '../models/device_profile_model.dart';
import '../models/recommendation_result_model.dart';
import '../models/user_preferences_model.dart';
import 'constraint_engine.dart';
import 'context_engine.dart';

/// The relative importance of each of the five scoring dimensions.
/// Defaults match the spec's initial weights (30/25/20/15/10) exactly.
/// [normalized] rescales an arbitrary set of positive weights so they sum
/// to 1.0 - used by the What-If Simulator (Part 8) to turn "High/Medium/
/// Low priority" choices into a real, calculated weight set rather than a
/// hardcoded alternative table.
class EngineWeights {
  final double preference;
  final double device;
  final double privacy;
  final double resource;
  final double rating;

  const EngineWeights({
    this.preference = 0.30,
    this.device = 0.25,
    this.privacy = 0.20,
    this.resource = 0.15,
    this.rating = 0.10,
  });

  static const defaults = EngineWeights();

  double get total => preference + device + privacy + resource + rating;

  /// Rescales this weight set so its five components sum to exactly 1.0,
  /// preserving their relative proportions - falls back to [defaults] if
  /// every weight is zero (nothing to scale).
  EngineWeights normalized() {
    final t = total;
    if (t <= 0) return defaults;
    return EngineWeights(
      preference: preference / t,
      device: device / t,
      privacy: privacy / t,
      resource: resource / t,
      rating: rating / t,
    );
  }

  Map<String, double> toMap() => {
        'preference': preference,
        'device': device,
        'privacy': privacy,
        'resource': resource,
        'rating': rating,
      };

  static EngineWeights fromMap(Map<String, dynamic>? map) {
    if (map == null) return defaults;
    double read(String key, double fallback) {
      final v = map[key];
      return v is num ? v.toDouble() : fallback;
    }

    return EngineWeights(
      preference: read('preference', defaults.preference),
      device: read('device', defaults.device),
      privacy: read('privacy', defaults.privacy),
      resource: read('resource', defaults.resource),
      rating: read('rating', defaults.rating),
    ).normalized();
  }
}

/// A named priority level for one scoring dimension (What-If Simulator,
/// Part 8) - a friendlier input than a raw weight, converted to real
/// weights via [EngineWeights.fromPriorities].
enum PriorityLevel {
  low(0.5),
  medium(1.0),
  high(1.5);

  final double multiplier;
  const PriorityLevel(this.multiplier);
}

extension EngineWeightsPriorities on EngineWeights {
  /// Builds a real, normalized [EngineWeights] by multiplying each base
  /// weight by its chosen [PriorityLevel], then rescaling back to a
  /// 1.0 total - so "Resource efficiency = High" always produces a
  /// calculated weight set, never a hardcoded alternative.
  static EngineWeights fromPriorities({
    PriorityLevel preference = PriorityLevel.medium,
    PriorityLevel device = PriorityLevel.medium,
    PriorityLevel privacy = PriorityLevel.medium,
    PriorityLevel resource = PriorityLevel.medium,
    PriorityLevel rating = PriorityLevel.medium,
  }) {
    const base = EngineWeights.defaults;
    return EngineWeights(
      preference: base.preference * preference.multiplier,
      device: base.device * device.multiplier,
      privacy: base.privacy * privacy.multiplier,
      resource: base.resource * resource.multiplier,
      rating: base.rating * rating.multiplier,
    ).normalized();
  }
}

/// Explainable, weighted, constraint-filtered, context-aware
/// recommendation scoring. Pure and stateless - no I/O, no Flutter
/// dependency - so it's fully unit testable in isolation and swappable
/// later for an ML-based implementation (see RecommendationModel)
/// without touching any screen.
///
/// Every sub-score is computed independently on a 0-100 scale from real,
/// named [AppInfo]/[DeviceProfileModel]/[UserPreferencesModel] fields -
/// never a hardcoded result - then multiplied by its weight so the five
/// weighted contributions (plus the small, bounded context addend) sum
/// to the final 0-100 score.
class RecommendationEngine {
  final ConstraintEngine _constraints;
  final ContextEngine _context;

  const RecommendationEngine({
    ConstraintEngine constraints = const ConstraintEngine(),
    ContextEngine context = const ContextEngine(),
  })  : _constraints = constraints,
        _context = context;

  /// Recorded with each history entry so Evaluation can compare scoring
  /// methods: 2 = availability-aware scoring over verified metadata.
  static const int scoringVersion = 2;

  static const double preferenceWeight = 0.30;
  static const double deviceWeight = 0.25;
  static const double privacyWeight = 0.20;
  static const double resourceWeight = 0.15;
  static const double ratingWeight = 0.10;

  /// Scores a single app and returns its full, explainable result.
  /// [weights] defaults to the spec's fixed 30/25/20/15/10 split but can
  /// be overridden (already normalized) for a temporary What-If
  /// simulation without ever touching the user's saved preferences.
  ///
  /// Availability-aware: each factor is scored only from VERIFIED data.
  /// A factor with nothing verified for this app is unavailable - it
  /// contributes nothing and its weight is shared proportionally across
  /// the available factors, so the available factors keep their intended
  /// relative importance and "unknown" is never scored as good or bad.
  /// If no factor at all can be verified, the score is 0 and the result
  /// reports [RecommendationResult.hasVerifiedFactors] = false.
  RecommendationResult score({
    required AppInfo app,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
    EngineWeights weights = EngineWeights.defaults,
  }) {
    final raws = <double?>[
      _preferenceScore(app, preferences.selectedPreferences),
      _deviceScore(app, device),
      _privacyScore(app),
      _resourceScore(app),
      _ratingScore(app),
    ];
    final baseWeights = [weights.preference, weights.device, weights.privacy, weights.resource, weights.rating];
    final available = raws.map((r) => r != null).toList();
    final availableWeight = List.generate(5, (i) => available[i] ? baseWeights[i] : 0.0).fold(0.0, (a, b) => a + b);
    final effective = List.generate(5, (i) => available[i] && availableWeight > 0 ? baseWeights[i] / availableWeight : 0.0);
    final contributions = List.generate(5, (i) => (raws[i] ?? 0) * effective[i]);

    final activeEffects = _context.evaluate(device);
    // Context effects only nudge a real score; with nothing verified there
    // is no score to adjust.
    final contextScore = availableWeight > 0 ? _context.contextScoreFor(app, activeEffects) : 0.0;

    final breakdown = ScoreBreakdown(
      preference: contributions[0],
      device: contributions[1],
      privacy: contributions[2],
      resource: contributions[3],
      rating: contributions[4],
      context: contextScore,
      available: available,
      effectiveWeights: effective,
      evidence: _evidence(app, preferences.selectedPreferences, device, available),
    );

    final reasons = _buildReasons(
      app: app,
      selectedPreferences: preferences.selectedPreferences,
      device: device,
      deviceRaw: raws[1],
      privacyRaw: raws[2],
      resourceRaw: raws[3],
      ratingRaw: raws[4],
      activeEffects: activeEffects,
      contextScore: contextScore,
    );

    return RecommendationResult(
      app: app,
      breakdown: breakdown,
      reasons: reasons,
      confidence: _confidence(app: app, preferences: preferences, device: device),
      activeContextEffects: activeEffects,
    );
  }

  /// Scores every app in [apps] that passes [constraints] (default:
  /// Android-compatibility only, so existing callers are unaffected) and
  /// returns them ranked highest match first (ties broken by name, so
  /// results are deterministic).
  List<RecommendationResult> rank({
    required List<AppInfo> apps,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
    EngineWeights weights = EngineWeights.defaults,
    HardConstraints constraints = const HardConstraints(),
  }) {
    final eligible = _constraints.filter(apps: apps, constraints: constraints, device: device);
    final results = eligible.map((a) {
      final result = score(app: a, preferences: preferences, device: device, weights: weights);
      final unverified = _constraints.unverifiedConstraints(a, constraints);
      return unverified.isEmpty ? result : result.withUnverifiedConstraints(unverified);
    }).toList();
    results.sort((a, b) {
      final byScore = b.breakdown.finalScore.compareTo(a.breakdown.finalScore);
      return byScore != 0 ? byScore : a.app.name.compareTo(b.app.name);
    });
    return results;
  }

  /// The real, currently-active context effects for [device] - exposed so
  /// screens can show the same transparent banner ("Because your storage
  /// is low, smaller apps are prioritized.") that drove [rank]'s scoring,
  /// without recomputing it separately.
  List<ContextEffect> contextEffectsFor(DeviceProfileModel device) => _context.evaluate(device);

  // ---- Sub-scores (each 0-100, or null = unavailable) ----

  /// How well the app matches the preferences the user selected, counted
  /// ONLY over preferences whose underlying attribute is verified for this
  /// app (see AppInfo.preferenceStatus). Unverified preferences are left
  /// out rather than counted as failures. Unavailable when the user
  /// selected nothing or none of their selections can be verified.
  double? _preferenceScore(AppInfo app, Set<AppPreference> selected) {
    final statuses = selected.map(app.preferenceStatus).whereType<bool>().toList();
    if (statuses.isEmpty) return null;
    return statuses.where((s) => s).length / statuses.length * 100;
  }

  /// How suitable the app is for THIS device. Scored from the app's known
  /// resource level against the device's real RAM. Android-version
  /// compatibility alone is only informative when it FAILS (a compatible
  /// app says nothing about fit), so a verified incompatibility is scored
  /// and a mere "compatible, resource use unknown" is unavailable.
  double? _deviceScore(AppInfo app, DeviceProfileModel device) {
    final sdk = device.androidSdkInt;
    final minSdk = app.minimumAndroidSdk;
    final incompatible = sdk != null && minSdk != null && sdk < minSdk;
    final ram = device.ramTotalMb;
    final resourceLevel = app.resourceLevel;
    double? score;
    if (ram != null && resourceLevel != null) {
      score = switch (resourceLevel) {
        ResourceLevel.light => 100,
        ResourceLevel.moderate => ram >= 3072 ? 95 : (ram >= 2048 ? 70 : 40),
        ResourceLevel.heavy => ram >= 6144 ? 95 : (ram >= 4096 ? 60 : 25),
      };
      if (device.isLowRamDevice == true && resourceLevel != ResourceLevel.light) {
        score = (score - 20).clamp(0, 100).toDouble();
      }
    }
    if (incompatible) {
      // A hard practical constraint, not a soft preference.
      score = score == null ? 15 : (score < 15 ? score : 15);
    }
    return score?.clamp(0, 100).toDouble();
  }

  /// How privacy-respecting the app is (tracker count from a verified
  /// source such as an Exodus report). Unavailable when no source
  /// verified it - never assumed clean or dirty.
  double? _privacyScore(AppInfo app) {
    final trackers = app.trackerCount;
    if (trackers == null) return null;
    if (trackers == 0) return 100;
    if (trackers <= 2) return 75;
    if (trackers <= 5) return 50;
    return 20;
  }

  /// General resource efficiency of the app itself - from its declared
  /// resource level, or else from a real, store-reported install size.
  /// Unavailable when neither is known (never estimated).
  double? _resourceScore(AppInfo app) {
    final resourceLevel = app.resourceLevel;
    final sizeMb = app.sizeMb;
    if (resourceLevel != null) {
      double base = switch (resourceLevel) {
        ResourceLevel.light => 100,
        ResourceLevel.moderate => 65,
        ResourceLevel.heavy => 30,
      };
      if (sizeMb != null && sizeMb > 150) base -= 10;
      return base.clamp(0, 100).toDouble();
    }
    if (sizeMb == null) return null;
    if (sizeMb <= 30) return 100;
    if (sizeMb <= 100) return 75;
    if (sizeMb <= 250) return 50;
    return 25;
  }

  /// User rating, rescaled from 0-5 stars to 0-100. Unavailable when the
  /// app has no rating.
  double? _ratingScore(AppInfo app) {
    final rating = app.rating;
    if (rating == null) return null;
    return (rating / 5.0 * 100).clamp(0, 100).toDouble();
  }

  /// Where each available factor's evidence came from, for "Why this app?".
  List<String?> _evidence(AppInfo app, Set<AppPreference> selected, DeviceProfileModel device, List<bool> available) {
    final verifiable = selected.where((p) => app.preferenceStatus(p) != null).length;
    final demo = app.isCuratedSample;
    return [
      available[0] && verifiable < selected.length ? 'Based on $verifiable of your ${selected.length} preferences - the rest aren\'t verified' : null,
      available[1] ? (app.resourceLevel != null && device.ramTotalMb != null ? 'Your device\'s RAM vs the app\'s resource use' : 'Android version requirement') : null,
      available[2] ? (app.privacyDataSource == 'exodus' ? 'Verified by εxodus' : (demo ? 'Demo dataset' : null)) : null,
      available[3] ? (app.resourceLevel == null ? 'App size from the store' : (demo ? 'Demo dataset' : null)) : null,
      available[4] ? (app.isLiveData ? 'Google Play rating' : null) : null,
    ];
  }

  /// Real, calculated 0-1 confidence: the fraction of the signals this
  /// score actually depended on that were genuinely available, rather
  /// than a neutral fallback. Never a fabricated/ML confidence - purely a
  /// measure of data completeness. Includes the app's own resource level
  /// and tracker count so confidence honestly drops for real Google Play
  /// results (which don't report either) rather than only reflecting
  /// device/rating/preference availability.
  double _confidence({
    required AppInfo app,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
  }) {
    final signals = <bool>[
      device.ramTotalMb != null,
      device.androidSdkInt != null,
      app.rating != null,
      preferences.selectedPreferences.isNotEmpty,
      app.resourceLevel != null,
      app.trackerCount != null,
    ];
    final available = signals.where((s) => s).length;
    return available / signals.length;
  }

  // ---- Explanation ----

  List<RecommendationReason> _buildReasons({
    required AppInfo app,
    required Set<AppPreference> selectedPreferences,
    required DeviceProfileModel device,
    required double? deviceRaw,
    required double? privacyRaw,
    required double? resourceRaw,
    required double? ratingRaw,
    required List<ContextEffect> activeEffects,
    required double contextScore,
  }) {
    final reasons = <RecommendationReason>[];

    for (final pref in selectedPreferences) {
      final status = app.preferenceStatus(pref);
      if (status == true) {
        reasons.add(RecommendationReason('Matches your preference for ${pref.label.toLowerCase()}'));
      } else if (status == false) {
        reasons.add(RecommendationReason('Doesn\'t meet your preference for ${pref.label.toLowerCase()}', isPositive: false));
      }
    }

    if (device.androidSdkInt != null && app.minimumAndroidSdk != null && device.androidSdkInt! < app.minimumAndroidSdk!) {
      reasons.add(RecommendationReason('Needs Android ${app.minimumAndroidSdk} or newer than your device has', isPositive: false));
    } else if (device.ramTotalMb != null && deviceRaw != null && deviceRaw >= 70) {
      reasons.add(const RecommendationReason('Suitable for your device\'s available resources'));
    }

    if (privacyRaw != null && privacyRaw >= 75) {
      reasons.add(RecommendationReason(app.trackerCount == 0 ? 'No trackers detected' : 'Very few trackers detected'));
    }

    if (resourceRaw != null && resourceRaw >= 65 && app.resourceLevel != null) {
      reasons.add(RecommendationReason('${app.resourceLevel!.label} resource usage'));
    }

    if (ratingRaw != null && ratingRaw >= 80 && app.rating != null) {
      reasons.add(RecommendationReason('Highly rated by users (${app.rating!.toStringAsFixed(1)}★)'));
    }

    if (contextScore > 0 && activeEffects.isNotEmpty) {
      reasons.add(const RecommendationReason('A good fit for your device\'s current condition'));
    } else if (contextScore < 0 && activeEffects.isNotEmpty) {
      reasons.add(const RecommendationReason('Less ideal given your device\'s current condition', isPositive: false));
    }

    if (reasons.isEmpty) {
      reasons.add(const RecommendationReason('Closest available match for the criteria you selected', isPositive: false));
    }

    return reasons;
  }

  /// A single natural-language sentence summarizing the strongest
  /// positive reasons (Part 9's card example: "Matches your preference
  /// for low resource usage and offline access.") - built only from the
  /// SAME reasons list the "Why this app?" screen shows, never a
  /// separately-invented sentence.
  String summarize(RecommendationResult result) {
    final positive = result.reasons.where((r) => r.isPositive).map((r) => r.text).toList();
    if (positive.isEmpty) {
      return result.reasons.isNotEmpty ? '${result.reasons.first.text}.' : 'A possible match based on the available information.';
    }
    if (positive.length == 1) return '${positive[0]}.';
    final second = positive[1];
    final lowerSecond = second.isEmpty ? second : '${second[0].toLowerCase()}${second.substring(1)}';
    return '${positive[0]} and $lowerSecond.';
  }
}
