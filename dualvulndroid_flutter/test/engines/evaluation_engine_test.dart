import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/engines/evaluation_engine.dart';
import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/feedback_model.dart';
import 'package:dualvulndroid_flutter/models/history_entry_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';

const _engine = EvaluationEngine();

HistoryEntry _entry(List<String> recommendedAppIds) => HistoryEntry(
      id: recommendedAppIds.join(),
      category: AppCategory.utilities,
      preferences: const {},
      resultCount: recommendedAppIds.length,
      timestamp: DateTime.now(),
      recommendedApps: recommendedAppIds
          .map((id) => RecommendedAppEntry(packageName: id, name: id, score: 0))
          .toList(),
    );

void main() {
  group('EvaluationEngine.evaluate', () {
    test('returns null when there is no feedback at all', () {
      final report = _engine.evaluate(history: [_entry(['a', 'b'])], feedback: const []);
      expect(report, isNull);
    });

    test('returns null when history is empty even if feedback exists', () {
      final report = _engine.evaluate(
        history: const [],
        feedback: [FeedbackEntry(appId: 'a', type: FeedbackType.useful, timestamp: DateTime.now())],
      );
      expect(report, isNull);
    });

    test('returns null when feedback exists but for apps never recommended in any session', () {
      final report = _engine.evaluate(
        history: [_entry(['a', 'b'])],
        feedback: [FeedbackEntry(appId: 'z', type: FeedbackType.useful, timestamp: DateTime.now())],
      );
      expect(report, isNull);
    });

    test('a perfect session (every recommended app marked useful) scores maximum precision and NDCG', () {
      final report = _engine.evaluate(
        history: [_entry(['a', 'b', 'c'])],
        feedback: [
          FeedbackEntry(appId: 'a', type: FeedbackType.useful, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'b', type: FeedbackType.preferThis, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'c', type: FeedbackType.useful, timestamp: DateTime.now()),
        ],
      );
      expect(report, isNotNull);
      expect(report!.precisionAtK, closeTo(1.0, 0.0001));
      expect(report.ndcgAtK, closeTo(1.0, 0.0001));
      expect(report.sessionsEvaluated, 1);
    });

    test('a session with only negative feedback scores zero precision', () {
      final report = _engine.evaluate(
        history: [_entry(['a', 'b'])],
        feedback: [
          FeedbackEntry(appId: 'a', type: FeedbackType.notUseful, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'b', type: FeedbackType.notForMe, timestamp: DateTime.now()),
        ],
      );
      expect(report, isNotNull);
      expect(report!.precisionAtK, 0.0);
      expect(report.ndcgAtK, 0.0);
    });

    test('a relevant app ranked first scores a higher NDCG than the same app ranked last', () {
      final firstReport = _engine.evaluate(
        history: [_entry(['relevant', 'other1', 'other2'])],
        feedback: [
          FeedbackEntry(appId: 'relevant', type: FeedbackType.useful, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'other1', type: FeedbackType.notUseful, timestamp: DateTime.now()),
        ],
      );
      final lastReport = _engine.evaluate(
        history: [_entry(['other1', 'other2', 'relevant'])],
        feedback: [
          FeedbackEntry(appId: 'relevant', type: FeedbackType.useful, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'other1', type: FeedbackType.notUseful, timestamp: DateTime.now()),
        ],
      );
      expect(firstReport!.ndcgAtK, greaterThan(lastReport!.ndcgAtK));
    });

    test('only the newest feedback for a given app is used as its relevance label', () {
      final report = _engine.evaluate(
        history: [_entry(['a'])],
        feedback: [
          // Newest first, matching FeedbackRepository's real ordering.
          FeedbackEntry(appId: 'a', type: FeedbackType.useful, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'a', type: FeedbackType.notUseful, timestamp: DateTime.now().subtract(const Duration(days: 1))),
        ],
      );
      expect(report!.precisionAtK, closeTo(1.0, 0.0001));
    });

    test('respects a smaller k by only evaluating the top k recommended apps', () {
      final report = _engine.evaluate(
        history: [_entry(['bad1', 'bad2', 'good'])],
        feedback: [
          FeedbackEntry(appId: 'bad1', type: FeedbackType.notUseful, timestamp: DateTime.now()),
          FeedbackEntry(appId: 'good', type: FeedbackType.useful, timestamp: DateTime.now()),
        ],
        k: 1,
      );
      // Top-1 is "bad1", which is known-negative -> precision 0 at k=1.
      expect(report!.precisionAtK, 0.0);
    });
  });

  group('EvaluationEngine.measureAverageLatency', () {
    test('measures a real, non-negative duration for an actual rank() call', () {
      const engine = RecommendationEngine();
      final apps = [
        const AppInfo(
          id: 'a',
          name: 'A',
          category: AppCategory.utilities,
          description: 'x',
          iconKey: 'apps_outlined',
          sizeMb: 10,
          hasAds: false,
          trackerCount: 0,
          isOpenSource: true,
          supportsOffline: true,
          isFree: true,
          resourceLevel: ResourceLevel.light,
        ),
      ];
      final latency = _engine.measureAverageLatency(
        engine: engine,
        apps: apps,
        preferences: const UserPreferencesModel(),
        device: const DeviceProfileModel(),
        iterations: 5,
      );
      expect(latency.inMicroseconds, greaterThanOrEqualTo(0));
    });
  });
}
