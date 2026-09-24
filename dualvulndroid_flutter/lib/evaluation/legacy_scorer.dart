import '../engines/context_engine.dart';
import '../engines/recommendation_engine.dart';
import '../models/app_info_model.dart';
import '../models/device_profile_model.dart';
import '../models/recommendation_result_model.dart';
import '../models/user_preferences_model.dart';

/// Evaluation configuration A ("before enrichment"): the scoring formula the
/// production engine used BEFORE availability-aware scoring (scoringVersion
/// 1), re-implemented here only for evaluation - production never calls it.
///
/// Differences from the current engine, reproduced exactly:
///   * unknown attributes get fixed neutral sub-scores (device 60, privacy
///     50, resource 50, rating 50) instead of being left out;
///   * with preferences selected, every preference the app can't be
///     VERIFIED to satisfy counts as unmet (matched / selected), and with
///     none selected the preference sub-score is a neutral 60;
///   * all five factors always carry their fixed 30/25/20/15/10 weights.
/// Everything else (sub-score tables, ±10 context adjustment via the same
/// ContextEngine, ranking order/tie-break) is unchanged. The formula's
/// output is checked against the live BEFORE audit recorded in
/// docs/metadata_enrichment_audit.md (see legacy_scorer tests).
class LegacyScorer {
  final ContextEngine context;

  const LegacyScorer({this.context = const ContextEngine()});

  ContextEngine get _context => context;

  RecommendationResult score({
    required AppInfo app,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
    EngineWeights weights = EngineWeights.defaults,
  }) {
    final effects = _context.evaluate(device);
    return RecommendationResult(
      app: app,
      breakdown: ScoreBreakdown(
        preference: _preference(app, preferences.selectedPreferences) * weights.preference,
        device: _device(app, device) * weights.device,
        privacy: _privacy(app) * weights.privacy,
        resource: _resource(app) * weights.resource,
        rating: _rating(app) * weights.rating,
        context: _context.contextScoreFor(app, effects),
        effectiveWeights: [weights.preference, weights.device, weights.privacy, weights.resource, weights.rating],
      ),
      reasons: const [],
      activeContextEffects: effects,
    );
  }

  List<RecommendationResult> rank({
    required List<AppInfo> apps,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
  }) {
    final results = [for (final a in apps) score(app: a, preferences: preferences, device: device)];
    results.sort((a, b) {
      final byScore = b.breakdown.finalScore.compareTo(a.breakdown.finalScore);
      return byScore != 0 ? byScore : a.app.name.compareTo(b.app.name);
    });
    return results;
  }

  double _preference(AppInfo app, Set<AppPreference> selected) {
    if (selected.isEmpty) return 60;
    return selected.where(app.satisfies).length / selected.length * 100;
  }

  double _device(AppInfo app, DeviceProfileModel device) {
    double score = 60;
    final ram = device.ramTotalMb;
    final level = app.resourceLevel;
    if (ram != null && level != null) {
      score = switch (level) {
        ResourceLevel.light => 100,
        ResourceLevel.moderate => ram >= 3072 ? 95 : (ram >= 2048 ? 70 : 40),
        ResourceLevel.heavy => ram >= 6144 ? 95 : (ram >= 4096 ? 60 : 25),
      };
      if (device.isLowRamDevice == true && level != ResourceLevel.light) {
        score = (score - 20).clamp(0, 100).toDouble();
      }
    }
    final sdk = device.androidSdkInt;
    final minSdk = app.minimumAndroidSdk;
    if (sdk != null && minSdk != null && sdk < minSdk) {
      score = score < 15 ? score : 15;
    }
    return score.clamp(0, 100).toDouble();
  }

  double _privacy(AppInfo app) {
    final trackers = app.trackerCount;
    if (trackers == null) return 50;
    if (trackers == 0) return 100;
    if (trackers <= 2) return 75;
    if (trackers <= 5) return 50;
    return 20;
  }

  double _resource(AppInfo app) {
    final level = app.resourceLevel;
    if (level == null) return 50;
    double base = switch (level) {
      ResourceLevel.light => 100,
      ResourceLevel.moderate => 65,
      ResourceLevel.heavy => 30,
    };
    final sizeMb = app.sizeMb;
    if (sizeMb != null && sizeMb > 150) base -= 10;
    return base.clamp(0, 100).toDouble();
  }

  double _rating(AppInfo app) {
    final rating = app.rating;
    if (rating == null) return 50;
    return (rating / 5.0 * 100).clamp(0, 100).toDouble();
  }
}
