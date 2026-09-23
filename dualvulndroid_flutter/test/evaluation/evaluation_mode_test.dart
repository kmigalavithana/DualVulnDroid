import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/evaluation/evaluation_export.dart';
import 'package:dualvulndroid_flutter/evaluation/evaluation_models.dart';
import 'package:dualvulndroid_flutter/evaluation/evaluation_runner.dart';
import 'package:dualvulndroid_flutter/evaluation/legacy_scorer.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/recommendation_result_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/evaluation_repository.dart';

const _device = DeviceProfileModel(androidSdkInt: 36, androidRelease: '16', ramTotalMb: 1946, isLowRamDevice: false);

Map<String, dynamic> _snapApp(String pkg, {double? rating, bool? isFree, bool? hasAds, bool? isOpenSource, int? trackers, List<String>? sources}) => {
      'id': pkg,
      'name': pkg,
      'packageName': pkg,
      'category': 'Productivity',
      'rating': rating,
      'realData': true,
      'source': 'google_play',
      'isFree': isFree,
      'hasAds': hasAds,
      'isOpenSource': isOpenSource,
      'trackerCount': trackers,
      'metadataSources': sources ?? ['google_play'],
    };

final _snapshot = CandidateSnapshot(
  snapshotId: 'snap-1',
  collectedAt: DateTime.utc(2026, 9, 24),
  category: 'Productivity',
  apps: [
    _snapApp('p.adfree', rating: 4.2, isFree: true, isOpenSource: true, sources: ['google_play', 'google_play_details', 'fdroid']),
    _snapApp('p.ads', rating: 4.8, isFree: true, hasAds: true, sources: ['google_play', 'google_play_details']),
    _snapApp('p.paid', rating: 4.5, isFree: false, sources: ['google_play', 'google_play_details']),
    _snapApp('p.plain', rating: 3.9),
  ],
);

EvaluationTask _task({String id = 't1', String participant = 'P01', Set<AppPreference>? prefs}) => EvaluationTask(
      taskId: id,
      participantId: participant,
      preferences: prefs ?? {AppPreference.free, AppPreference.noAds, AppPreference.openSource},
      deviceSnapshot: _device,
      category: 'Productivity',
      snapshotId: 'snap-1',
      candidateAppIds: _snapshot.packageNames,
      createdAt: DateTime.utc(2026, 9, 24),
    );

List<RelevanceLabel> _labels(String taskId, Map<String, int> grades) => [
      for (final e in grades.entries)
        RelevanceLabel(taskId: taskId, participantId: 'P01', packageName: e.key, grade: e.value, labeledAt: DateTime.utc(2026, 9, 24, 10)),
    ];

void main() {
  const runner = EvaluationRunner();

  group('Configuration A reproduces the pre-change scoring', () {
    test('matches the recorded live BEFORE audit (7 preferences: 40-42%)', () {
      AppInfo live(double rating) => AppInfo.fromSmartAppJson(_snapApp('x', rating: rating));
      final prefs = UserPreferencesModel(selectedPreferences: AppPreference.values.toSet());
      // Recorded audit: all-7-preference live apps scored 40-42 (rating 3.9-4.9).
      expect(const LegacyScorer().score(app: live(4.6), preferences: prefs, device: _device).matchPercent, 42);
      expect(const LegacyScorer().score(app: live(3.9), preferences: prefs, device: _device).matchPercent, 40);
      // No preferences: 58-60 in the audit.
      expect(const LegacyScorer().score(app: live(4.8), preferences: const UserPreferencesModel(), device: _device).matchPercent, 60);
    });

    test('A and B/C only see Google Play search fields; C sees enrichment', () {
      final raw = _snapshot.apps.first;
      expect(appForConfig(raw, EvaluationConfig.a).isOpenSource, isNull);
      expect(appForConfig(raw, EvaluationConfig.b).isFree, isNull);
      expect(appForConfig(raw, EvaluationConfig.c).isOpenSource, isTrue);
      expect(appForConfig(raw, EvaluationConfig.c).isFree, isTrue);
      expect(appForConfig(raw, EvaluationConfig.b).rating, 4.2);
    });
  });

  group('13. Frozen candidate snapshot', () {
    test('every configuration ranks exactly the snapshot candidates, nothing else', () {
      for (final config in EvaluationConfig.values) {
        final run = runner.run(evaluationId: 'e', task: _task(), snapshot: _snapshot, config: config, repetitions: 2);
        expect(run.ranking.toSet(), _snapshot.packageNames.toSet(), reason: config.code);
        expect(run.snapshotId, 'snap-1');
      }
    });

    test('a task can only run against its own snapshot', () {
      final other = CandidateSnapshot(snapshotId: 'snap-2', collectedAt: DateTime.utc(2026), category: 'x', apps: const []);
      expect(() => runner.run(evaluationId: 'e', task: _task(), snapshot: other, config: EvaluationConfig.b), throwsArgumentError);
    });

    test('snapshot codec round-trips live fields without inventing values', () {
      final app = AppInfo.fromSmartAppJson(_snapApp('p.x', rating: 4.1, hasAds: true));
      final json = appToSnapshotJson(app);
      expect(json['hasAds'], isTrue);
      expect(json['isFree'], isNull);
      expect(json['sizeMb'], isNull);
      final back = AppInfo.fromSmartAppJson(json);
      expect(back.rating, 4.1);
      expect(back.hasAds, isTrue);
      expect(back.supportsOffline, isNull);
    });
  });

  group('11. Paired comparison', () {
    test('same task + candidates, only the configuration changes; per-task differences are computed', () {
      final task = _task();
      final runs = [
        for (final c in EvaluationConfig.values) runner.run(evaluationId: 'e1', task: task, snapshot: _snapshot, config: c, repetitions: 1),
      ];
      // Participant judged the ad-free open-source app best.
      final labels = _labels('t1', {'p.adfree': 3, 'p.ads': 1, 'p.paid': 0, 'p.plain': 2});
      final analysis = EvaluationAnalysis.build(tasks: [task], snapshots: [_snapshot], labels: labels, runs: runs, surveys: const []);

      expect(analysis.evaluableTaskCount, 1);
      expect(analysis.perTask.map((m) => m.config), EvaluationConfig.values);
      // C can use the verified store/F-Droid facts; A and B cannot.
      final c = runs.firstWhere((r) => r.config == EvaluationConfig.c);
      expect(c.ranking.first, 'p.adfree');
      final ndcgCa = analysis.paired.firstWhere((p) => p.metric == 'ndcg@3' && p.from == EvaluationConfig.a && p.to == EvaluationConfig.c);
      final expected = analysis.perTask.firstWhere((m) => m.config == EvaluationConfig.c).values['ndcg@3']! -
          analysis.perTask.firstWhere((m) => m.config == EvaluationConfig.a).values['ndcg@3']!;
      expect(ndcgCa.differences['t1'], closeTo(expected, 1e-12));
      expect(ndcgCa.wilcoxon!.pTwoSided, isNull, reason: 'one pair: no p-value is reported');
      expect(ndcgCa.bootstrap, isNull, reason: 'one pair: no confidence interval is reported');
    });
  });

  group('14. No fake metrics', () {
    test('no labels -> no ranking metrics at all', () {
      final runs = [runner.run(evaluationId: 'e', task: _task(), snapshot: _snapshot, config: EvaluationConfig.b)];
      final analysis = EvaluationAnalysis.build(tasks: [_task()], snapshots: [_snapshot], labels: const [], runs: runs, surveys: const []);
      expect(analysis.hasRankingData, isFalse);
      expect(analysis.means[EvaluationConfig.b]!.values, everyElement(isNull));
      expect(analysis.surveyMeans, isEmpty);
    });

    test('incompletely labeled tasks are skipped, never filled in', () {
      final runs = [runner.run(evaluationId: 'e', task: _task(), snapshot: _snapshot, config: EvaluationConfig.b)];
      final partial = _labels('t1', {'p.adfree': 3, 'p.ads': 1});
      final analysis = EvaluationAnalysis.build(tasks: [_task()], snapshots: [_snapshot], labels: partial, runs: runs, surveys: const []);
      expect(analysis.evaluableTaskCount, 0);
      expect(analysis.perTask, isEmpty);
    });

    test('labels are human input only: grades outside 0-3 are rejected', () {
      expect(
        () => RelevanceLabel(taskId: 't', participantId: 'p', packageName: 'a', grade: 4, labeledAt: DateTime.utc(2026)),
        throwsArgumentError,
      );
    });
  });

  group('9. Metadata coverage (descriptive)', () {
    test('computed from the frozen apps as captured', () {
      final coverage = CoverageReport.of(_snapshot.apps)!;
      expect(coverage.apps, 4);
      expect(coverage.openSource, 0.25);
      expect(coverage.storeMetadata, 0.75);
      expect(coverage.privacy, 0);
      final expectedOverall = _snapshot.apps.map((a) => appForConfig(a, EvaluationConfig.c).metadataCoverage).reduce((a, b) => a + b) / 4;
      expect(coverage.overall, closeTo(expectedOverall, 1e-12));
    });
  });

  group('10. Explanation consistency', () {
    test('every real result from A, B and C is consistent', () {
      for (final c in EvaluationConfig.values) {
        final run = runner.run(evaluationId: 'e', task: _task(), snapshot: _snapshot, config: c, repetitions: 1);
        expect(run.explanationsChecked, 4);
        expect(run.explanationsConsistent, 4, reason: c.code);
      }
    });

    test('a result whose displayed factors disagree with its values is caught', () {
      final app = AppInfo.fromSmartAppJson(_snapApp('bad', rating: 4));
      final tampered = RecommendationResult(
        app: app,
        breakdown: const ScoreBreakdown(
          preference: 0,
          device: 0,
          privacy: 12, // claims privacy points...
          resource: 0,
          rating: 80,
          available: [false, false, false, false, true], // ...but privacy is marked unavailable
          effectiveWeights: [0, 0, 0, 0, 1],
        ),
        reasons: const [],
      );
      expect(ExplanationCheck.isConsistent(tampered), isFalse);
      final real = const RecommendationEngine().score(app: app, preferences: const UserPreferencesModel(), device: _device);
      expect(ExplanationCheck.isConsistent(real), isTrue);
    });
  });

  group('12. Export / import', () {
    test('JSON round-trips losslessly and CSV has only stored rows', () {
      final task = _task();
      final runs = [for (final c in EvaluationConfig.values) runner.run(evaluationId: 'e', task: task, snapshot: _snapshot, config: c, repetitions: 3)];
      final dataset = EvaluationDataset(
        snapshots: [_snapshot],
        tasks: [task],
        labels: _labels('t1', {'p.adfree': 3, 'p.ads': 1, 'p.paid': 0, 'p.plain': 2}),
        runs: runs,
        surveys: [SurveyResponse(participantId: 'P01', answers: {0: 4, 2: 5}, submittedAt: DateTime.utc(2026, 9, 24))],
      );
      final back = EvaluationDataset.fromJsonString(dataset.toJsonString());
      expect(back.toJson(), dataset.toJson());

      final csv = back.allCsv();
      expect(csv['relevance_labels.csv']!.split('\n'), hasLength(1 + 4));
      expect(csv['rankings.csv']!.split('\n'), hasLength(1 + 3 * 4));
      expect(csv['latency.csv']!.split('\n'), hasLength(1 + 3 * 3));
      expect(csv['survey.csv']!.split('\n'), hasLength(1 + 2), reason: 'only answered statements');
      expect(csv['task_results.csv']!.split('\n'), hasLength(1 + 3));
      expect(csv['paired_differences.csv']!.split('\n').first, 'metric,comparison,taskId,difference');
    });

    test('an empty dataset exports headers only - no fabricated rows', () {
      for (final table in const EvaluationDataset().allCsv().values) {
        expect(table.split('\n'), hasLength(1));
      }
    });

    test('non-evaluation JSON is rejected on import', () {
      expect(() => EvaluationDataset.fromJsonString('{"format":"other"}'), throwsFormatException);
    });
  });

  group('16. Survey storage + isolation', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    test('responses persist under the evaluation key only, separate from production data', () async {
      final repo = EvaluationRepository();
      while (repo.isLoading) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      await repo.saveSurvey(SurveyResponse(participantId: 'P01', answers: {1: 3}, submittedAt: DateTime.utc(2026)));

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getKeys(), {EvaluationRepository.storageKey});

      final reloaded = EvaluationRepository();
      while (reloaded.isLoading) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      expect(reloaded.data.surveys.single.answers, {1: 3});
      expect(() => SurveyResponse(participantId: 'x', answers: {0: 6}, submittedAt: DateTime.utc(2026)), throwsArgumentError);
    });

    test('runEvaluation uses stored snapshots only and records reproducibility data', () async {
      final repo = EvaluationRepository();
      while (repo.isLoading) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      await repo.importDataset(EvaluationDataset(snapshots: [_snapshot], tasks: [_task()]));
      final id = await repo.runEvaluation(repetitions: 2);
      final runs = repo.data.runs;
      expect(runs, hasLength(3));
      expect(runs.map((r) => r.evaluationId).toSet(), {id});
      expect(runs.map((r) => r.snapshotId).toSet(), {'snap-1'});
      expect(runs.every((r) => r.latenciesMicros.length == 2), isTrue);
    });

    test('judging order is randomized but reproducible per task', () async {
      final repo = EvaluationRepository();
      while (repo.isLoading) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      await repo.importDataset(EvaluationDataset(snapshots: [_snapshot], tasks: [_task()]));
      final ordered = await repo.ensurePresentationOrder(repo.data.tasks.single);
      expect(ordered.presentationOrder.toSet(), _snapshot.packageNames.toSet());
      final again = await repo.ensurePresentationOrder(ordered);
      expect(again.presentationOrder, ordered.presentationOrder);
    });
  });
}
