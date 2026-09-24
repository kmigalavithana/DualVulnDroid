import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../evaluation/evaluation_export.dart';
import '../evaluation/evaluation_models.dart';
import '../evaluation/evaluation_runner.dart';
import '../models/app_info_model.dart';
import '../models/device_profile_model.dart';
import '../models/user_preferences_model.dart';

/// Research Evaluation Mode storage. Kept under its own key and never
/// touches production history, favorites, feedback or app-interaction data
/// - evaluation activity can't change what normal users see.
class EvaluationRepository extends ChangeNotifier {
  static const storageKey = 'smartapp.evaluation_mode.v1';

  final EvaluationRunner runner;
  EvaluationDataset _data = const EvaluationDataset();
  bool _loading = true;

  EvaluationRepository({this.runner = const EvaluationRunner()}) {
    _load();
  }

  EvaluationDataset get data => _data;
  bool get isLoading => _loading;

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(storageKey);
    if (raw != null) {
      try {
        _data = EvaluationDataset.fromJsonString(raw);
      } catch (_) {
        // A corrupted store is left untouched on disk (not overwritten)
        // and the screen simply shows no data.
      }
    }
    _loading = false;
    notifyListeners();
  }

  Future<void> _save(EvaluationDataset next) async {
    _data = next;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(storageKey, jsonEncode(next.toJson()));
  }

  static String newId(String prefix) {
    final rand = Random().nextInt(1 << 32).toRadixString(16).padLeft(8, '0');
    return '$prefix-${DateTime.now().toUtc().microsecondsSinceEpoch}-$rand';
  }

  /// Freezes [apps] (already fetched live by the caller) as a candidate
  /// snapshot. The stored copy is never refreshed or edited afterwards.
  Future<CandidateSnapshot> freezeSnapshot({required String category, required List<AppInfo> apps, DateTime? now}) async {
    final unique = <String, AppInfo>{};
    for (final a in apps) {
      unique.putIfAbsent(a.packageName ?? a.id, () => a);
    }
    final snapshot = CandidateSnapshot(
      snapshotId: newId('snap'),
      collectedAt: now ?? DateTime.now(),
      category: category,
      apps: [for (final a in unique.values) appToSnapshotJson(a)],
    );
    await _save(_copy(snapshots: [..._data.snapshots, snapshot]));
    return snapshot;
  }

  Future<EvaluationTask> createTask({
    required String participantId,
    required Set<AppPreference> preferences,
    required DeviceProfileModel device,
    required CandidateSnapshot snapshot,
  }) async {
    final task = EvaluationTask(
      taskId: newId('task'),
      participantId: participantId.trim(),
      preferences: preferences,
      deviceSnapshot: device,
      category: snapshot.category,
      snapshotId: snapshot.snapshotId,
      candidateAppIds: snapshot.packageNames,
      createdAt: DateTime.now(),
    );
    await _save(_copy(tasks: [..._data.tasks, task]));
    return task;
  }

  /// A reproducible random presentation order for judging, derived from
  /// the task id (FNV-1a) and recorded on the task.
  Future<EvaluationTask> ensurePresentationOrder(EvaluationTask task) async {
    if (task.presentationOrder.isNotEmpty) return task;
    var hash = 0x811c9dc5;
    for (final unit in task.taskId.codeUnits) {
      hash = ((hash ^ unit) * 0x01000193) & 0xffffffff;
    }
    final order = [...task.candidateAppIds]..shuffle(Random(hash));
    final updated = task.withPresentationOrder(order);
    await _save(_copy(tasks: [for (final t in _data.tasks) t.taskId == task.taskId ? updated : t]));
    return updated;
  }

  /// Stores human relevance judgments (0-3) for [task]. Later labels for
  /// the same app supersede earlier ones in the analysis; all are kept.
  Future<void> saveLabels(EvaluationTask task, Map<String, int> grades) async {
    final now = DateTime.now();
    final added = [
      for (final e in grades.entries)
        RelevanceLabel(taskId: task.taskId, participantId: task.participantId, packageName: e.key, grade: e.value, labeledAt: now),
    ];
    await _save(_copy(labels: [..._data.labels, ...added]));
  }

  Future<void> saveSurvey(SurveyResponse response) async => _save(_copy(surveys: [..._data.surveys, response]));

  /// Runs every configuration on every task against its own frozen
  /// snapshot, as one evaluation (shared [evaluationId]). Tasks whose
  /// snapshot is missing are skipped, never re-fetched.
  Future<String> runEvaluation({int repetitions = 5}) async {
    final evaluationId = newId('eval');
    final byId = {for (final s in _data.snapshots) s.snapshotId: s};
    final runs = <RankingRun>[];
    for (final task in _data.tasks) {
      final snapshot = byId[task.snapshotId];
      if (snapshot == null) continue;
      for (final config in EvaluationConfig.values) {
        runs.add(runner.run(evaluationId: evaluationId, task: task, snapshot: snapshot, config: config, repetitions: repetitions));
      }
    }
    await _save(_copy(runs: [..._data.runs, ...runs]));
    return evaluationId;
  }

  EvaluationAnalysis analyse() => _data.analyse();

  /// Replaces all Evaluation Mode data with an imported dataset.
  Future<void> importDataset(EvaluationDataset dataset) => _save(dataset);

  Future<void> clearAll() => _save(const EvaluationDataset());

  EvaluationDataset _copy({
    List<CandidateSnapshot>? snapshots,
    List<EvaluationTask>? tasks,
    List<RelevanceLabel>? labels,
    List<RankingRun>? runs,
    List<SurveyResponse>? surveys,
  }) =>
      EvaluationDataset(
        snapshots: snapshots ?? _data.snapshots,
        tasks: tasks ?? _data.tasks,
        labels: labels ?? _data.labels,
        runs: runs ?? _data.runs,
        surveys: surveys ?? _data.surveys,
      );
}
