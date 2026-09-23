import 'dart:math';

import '../models/app_info_model.dart';
import '../models/device_profile_model.dart';
import '../models/feedback_model.dart';
import '../models/history_entry_model.dart';
import '../models/user_preferences_model.dart';
import 'recommendation_engine.dart';

/// Real, calculated ranking-quality metrics over the sessions that
/// actually have both a recorded recommended list (HistoryEntry) AND
/// explicit user feedback on at least one of those apps (Part 14).
/// [sessionsEvaluated] is always reported alongside the metrics so a
/// reader can judge how much real data backs them - never presented as
/// more authoritative than the sample size actually supports.
class EvaluationReport {
  final int k;
  final double precisionAtK;
  final double recallAtK;
  final double ndcgAtK;
  final int sessionsEvaluated;

  const EvaluationReport({
    required this.k,
    required this.precisionAtK,
    required this.recallAtK,
    required this.ndcgAtK,
    required this.sessionsEvaluated,
  });
}

/// Computes real evaluation metrics from real local history + feedback -
/// never fabricated. Explicitly returns `null` (Part 14: "Only show
/// metrics when actual evaluation data exists") when there is no session
/// with both a recorded recommendation list and at least one feedback
/// label to check it against.
///
/// Relevance ground truth comes only from the user's own explicit
/// feedback ([FeedbackType.isPositive]) - an app with no feedback is
/// simply excluded from that session's relevance set, never assumed
/// relevant or irrelevant.
class EvaluationEngine {
  const EvaluationEngine();

  /// [scoringVersion] restricts the evaluation to history recorded by one
  /// scoring method (see HistoryEntry.scoringVersion) so methods can be
  /// compared on the same real feedback; null evaluates all history.
  EvaluationReport? evaluate({
    required List<HistoryEntry> history,
    required List<FeedbackEntry> feedback,
    int k = 5,
    int? scoringVersion,
  }) {
    if (scoringVersion != null) {
      history = history.where((h) => h.scoringVersion == scoringVersion).toList();
    }
    // Newest feedback per app id - FeedbackRepository stores newest-first.
    final latestFeedback = <String, FeedbackType>{};
    for (final entry in feedback) {
      latestFeedback.putIfAbsent(entry.appId, () => entry.type);
    }
    if (latestFeedback.isEmpty) return null;

    double precisionSum = 0;
    double recallSum = 0;
    double ndcgSum = 0;
    int sessionsUsed = 0;

    for (final entry in history) {
      final topK = entry.recommendedAppIds.take(k).toList();
      if (topK.isEmpty) continue;
      final hasGroundTruth = topK.any(latestFeedback.containsKey);
      if (!hasGroundTruth) continue;

      final relevantInTopK = topK.where((id) => latestFeedback[id]?.isPositive == true).length;
      final knownLabeled = topK.where(latestFeedback.containsKey).length;

      precisionSum += relevantInTopK / topK.length;
      // Recall within this session's known-labeled subset (there is no
      // larger ground-truth set available locally than what the user has
      // actually given feedback on).
      if (knownLabeled > 0) recallSum += relevantInTopK / knownLabeled;
      ndcgSum += _ndcg(topK, latestFeedback);
      sessionsUsed++;
    }

    if (sessionsUsed == 0) return null;
    return EvaluationReport(
      k: k,
      precisionAtK: precisionSum / sessionsUsed,
      recallAtK: recallSum / sessionsUsed,
      ndcgAtK: ndcgSum / sessionsUsed,
      sessionsEvaluated: sessionsUsed,
    );
  }

  double _ndcg(List<String> rankedIds, Map<String, FeedbackType> feedback) {
    double dcg = 0;
    for (var i = 0; i < rankedIds.length; i++) {
      final relevant = feedback[rankedIds[i]]?.isPositive == true;
      if (relevant) dcg += 1 / _log2(i + 2);
    }
    final relevantCount = rankedIds.where((id) => feedback[id]?.isPositive == true).length;
    double idcg = 0;
    for (var i = 0; i < relevantCount; i++) {
      idcg += 1 / _log2(i + 2);
    }
    return idcg > 0 ? dcg / idcg : 0.0;
  }

  double _log2(num x) => log(x) / ln2;

  /// Measures the REAL wall-clock time [engine] takes to rank [apps] -
  /// a genuine live benchmark, never an invented number. Runs several
  /// iterations and averages to reduce single-run noise.
  /// Mean verified-data coverage (0-1) of the apps actually recommended in
  /// [history] - descriptive system data, not an accuracy metric. Null when
  /// no recorded entry carries coverage.
  double? averageMetadataCoverage(List<HistoryEntry> history) {
    final values = [
      for (final entry in history)
        for (final app in entry.recommendedApps)
          if (app.metadataCoverage != null) app.metadataCoverage!,
    ];
    if (values.isEmpty) return null;
    return values.reduce((a, b) => a + b) / values.length;
  }

  Duration measureAverageLatency({
    required RecommendationEngine engine,
    required List<AppInfo> apps,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
    int iterations = 20,
  }) {
    final stopwatch = Stopwatch()..start();
    for (var i = 0; i < iterations; i++) {
      engine.rank(apps: apps, preferences: preferences, device: device);
    }
    stopwatch.stop();
    return Duration(microseconds: (stopwatch.elapsedMicroseconds / iterations).round());
  }
}
