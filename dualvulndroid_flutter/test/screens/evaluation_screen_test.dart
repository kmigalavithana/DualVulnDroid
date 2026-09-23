import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/evaluation/evaluation_export.dart';
import 'package:dualvulndroid_flutter/evaluation/evaluation_models.dart';
import 'package:dualvulndroid_flutter/evaluation/evaluation_runner.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/evaluation_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/screens/evaluation_screen.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';

Widget _wrap(EvaluationRepository repo) => MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: repo),
        ChangeNotifierProvider(create: (_) => HistoryRepository()),
        ChangeNotifierProvider(create: (_) => FeedbackRepository()),
      ],
      child: MaterialApp(theme: AppTheme.light, home: const EvaluationScreen()),
    );

Future<EvaluationRepository> _loadedRepo(WidgetTester tester) async {
  final repo = EvaluationRepository();
  await tester.runAsync(() async {
    while (repo.isLoading) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
  });
  return repo;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('15. empty state: "No evaluation data available." and no invented numbers', (tester) async {
    final repo = await _loadedRepo(tester);
    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('Evaluation Dataset'), findsOneWidget);
    expect(find.text('No evaluation data available.'), findsWidgets);
    expect(find.text('0 of 0 tasks fully labeled'), findsOneWidget);
    expect(find.textContaining('NDCG'), findsNothing, reason: 'no metric table without data');
    final runButton = tester.widget<OutlinedButton>(find.ancestor(of: find.text('Run A / B / C'), matching: find.byWidgetPredicate((w) => w is OutlinedButton)));
    expect(runButton.onPressed, isNull, reason: 'nothing to run without tasks');
  });

  testWidgets('a partly labeled task keeps Run A / B / C disabled and says why', (tester) async {
    final repo = await _loadedRepo(tester);
    final snapshot = CandidateSnapshot(
      snapshotId: 's',
      collectedAt: DateTime.utc(2026, 9, 24),
      category: 'Notes',
      apps: [
        for (final pkg in ['a', 'b'])
          {'id': pkg, 'name': pkg, 'packageName': pkg, 'category': 'Productivity', 'rating': 4.5, 'realData': true, 'source': 'google_play'},
      ],
    );
    await tester.runAsync(() => repo.importDataset(EvaluationDataset(
          snapshots: [snapshot],
          tasks: [
            EvaluationTask(
              taskId: 't',
              participantId: 'P01',
              preferences: const {},
              deviceSnapshot: const DeviceProfileModel(ramTotalMb: 4096),
              category: 'Notes',
              snapshotId: 's',
              candidateAppIds: snapshot.packageNames,
              createdAt: DateTime.utc(2026, 9, 24),
            ),
          ],
          labels: [RelevanceLabel(taskId: 't', participantId: 'P01', packageName: 'a', grade: 2, labeledAt: DateTime.utc(2026, 9, 24))],
        )));

    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('0 of 1 tasks fully labeled'), findsOneWidget);
    expect(find.text('Rate every app in a task (tap it below) to enable Run A / B / C.'), findsOneWidget);
    final runButton = tester.widget<OutlinedButton>(find.ancestor(of: find.text('Run A / B / C'), matching: find.byWidgetPredicate((w) => w is OutlinedButton)));
    expect(runButton.onPressed, isNull, reason: 'running would only report "no data"');
  });

  testWidgets('with real labels + runs the screen shows the measured A/B/C values side by side', (tester) async {
    final repo = await _loadedRepo(tester);
    final snapshot = CandidateSnapshot(
      snapshotId: 's',
      collectedAt: DateTime.utc(2026, 9, 24),
      category: 'Notes',
      apps: [
        for (final (pkg, rating) in [('a', 4.8), ('b', 4.1), ('c', 3.7)])
          {'id': pkg, 'name': pkg, 'packageName': pkg, 'category': 'Productivity', 'rating': rating, 'realData': true, 'source': 'google_play'},
      ],
    );
    final task = EvaluationTask(
      taskId: 't',
      participantId: 'P01',
      preferences: {AppPreference.free},
      deviceSnapshot: const DeviceProfileModel(ramTotalMb: 4096),
      category: 'Notes',
      snapshotId: 's',
      candidateAppIds: snapshot.packageNames,
      createdAt: DateTime.utc(2026, 9, 24),
    );
    await tester.runAsync(() async {
      await repo.importDataset(EvaluationDataset(
        snapshots: [snapshot],
        tasks: [task],
        labels: [
          for (final (pkg, g) in [('a', 3), ('b', 0), ('c', 2)])
            RelevanceLabel(taskId: 't', participantId: 'P01', packageName: pkg, grade: g, labeledAt: DateTime.utc(2026, 9, 24)),
        ],
      ));
      await repo.runEvaluation(repetitions: 2);
    });

    await tester.pumpWidget(_wrap(repo));
    await tester.pumpAndSettle();

    expect(find.text('1 of 1 tasks fully labeled'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('NDCG@3'), 150, scrollable: find.byType(Scrollable).first);
    final analysis = repo.analyse();
    for (final c in EvaluationConfig.values) {
      expect(find.text(formatMetric(analysis.means[c]!['ndcg@3'])), findsWidgets, reason: c.code);
    }
    expect(find.text('Precision@3'), findsOneWidget);
    expect(find.text('Recall@5'), findsOneWidget);
    expect(TaskMetrics.names, hasLength(6));
  });
}
