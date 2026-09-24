import '../engines/recommendation_engine.dart';
import '../models/app_info_model.dart';
import '../models/recommendation_result_model.dart';
import 'evaluation_models.dart';
import 'legacy_scorer.dart';
import 'ranking_metrics.dart';

/// Runs evaluation configurations over frozen snapshots and analyses the
/// results. Wraps the production engine - it never changes its behavior,
/// never fetches live data, and never uses a SmartApp score as ground truth.
class EvaluationRunner {
  final RecommendationEngine engine;
  final LegacyScorer legacy;

  const EvaluationRunner({this.engine = const RecommendationEngine(), this.legacy = const LegacyScorer()});

  /// The task's candidates, as [config] may see them, in snapshot order.
  /// Only apps inside the frozen snapshot are ever used.
  List<AppInfo> candidatesFor(EvaluationTask task, CandidateSnapshot snapshot, EvaluationConfig config) {
    if (snapshot.snapshotId != task.snapshotId) {
      throw ArgumentError('task ${task.taskId} uses snapshot ${task.snapshotId}, not ${snapshot.snapshotId}');
    }
    final wanted = task.candidateAppIds.toSet();
    return [
      for (final raw in snapshot.apps)
        if (wanted.contains(raw['packageName'] ?? raw['id'])) appForConfig(raw, config),
    ];
  }

  List<RecommendationResult> rank(EvaluationTask task, List<AppInfo> candidates, EvaluationConfig config) {
    switch (config) {
      case EvaluationConfig.a:
        return legacy.rank(apps: candidates, preferences: task.userPreferences, device: task.deviceSnapshot);
      case EvaluationConfig.b:
      case EvaluationConfig.c:
        // Default weights for every participant: What-If overrides are a
        // personal UI setting, not part of the compared configuration.
        return engine.rank(apps: candidates, preferences: task.userPreferences, device: task.deviceSnapshot);
    }
  }

  /// Ranks [task]'s frozen candidates with [config], timing
  /// [repetitions] identical rankings.
  RankingRun run({
    required String evaluationId,
    required EvaluationTask task,
    required CandidateSnapshot snapshot,
    required EvaluationConfig config,
    int repetitions = 5,
    DateTime? now,
  }) {
    final candidates = candidatesFor(task, snapshot, config);
    final latencies = <int>[];
    List<RecommendationResult>? ranked;
    for (var i = 0; i < repetitions; i++) {
      final watch = Stopwatch()..start();
      final result = rank(task, candidates, config);
      watch.stop();
      latencies.add(watch.elapsedMicroseconds);
      ranked ??= result;
    }
    final results = ranked ?? const <RecommendationResult>[];
    return RankingRun(
      evaluationId: evaluationId,
      timestamp: now ?? DateTime.now(),
      snapshotId: snapshot.snapshotId,
      config: config,
      taskId: task.taskId,
      participantId: task.participantId,
      ranking: [for (final r in results) r.app.packageName ?? r.app.id],
      scores: [for (final r in results) r.matchPercent],
      latenciesMicros: latencies,
      explanationsConsistent: results.where(ExplanationCheck.isConsistent).length,
      explanationsChecked: results.length,
    );
  }
}

/// Explainability consistency: do the points the "Why this app?" screen
/// displays (RecommendationResult.explanationFactors) agree with the real
/// weighted contributions in the same result? Checked from the result
/// itself - no expected values are hardcoded.
class ExplanationCheck {
  ExplanationCheck._();

  static bool isConsistent(RecommendationResult r) {
    final b = r.breakdown;
    final contributions = [b.preference, b.device, b.privacy, b.resource, b.rating];
    final factors = r.explanationFactors;
    if (factors.length != contributions.length) return false;
    for (var i = 0; i < factors.length; i++) {
      final f = factors[i];
      if (f.available != b.available[i]) return false;
      if (!f.available) {
        if (f.earnedPoints != 0 || f.maxPoints != 0 || contributions[i] != 0) return false;
        continue;
      }
      // Largest-remainder rounding moves a value by less than 1 point.
      if ((f.earnedPoints - contributions[i]).abs() >= 1) return false;
      if (f.earnedPoints > f.maxPoints) return false;
    }
    final displayed = factors.fold<int>(0, (a, f) => a + f.earnedPoints) + r.contextAdjustmentPoints;
    if (displayed != r.matchPercent) return false;
    if (r.hasVerifiedFactors && factors.where((f) => f.available).fold<int>(0, (a, f) => a + f.maxPoints) != 100) return false;
    return true;
  }
}

/// One configuration's metrics on one evaluable task.
class TaskMetrics {
  final String taskId;
  final String participantId;
  final EvaluationConfig config;
  final Map<String, double?> values;

  const TaskMetrics(this.taskId, this.participantId, this.config, this.values);

  static const names = ['precision@3', 'recall@3', 'ndcg@3', 'precision@5', 'recall@5', 'ndcg@5'];
}

class PairedComparison {
  final String metric;
  final EvaluationConfig from;
  final EvaluationConfig to;

  /// taskId -> (to - from), only for tasks where both are defined.
  final Map<String, double> differences;
  final WilcoxonResult? wilcoxon;
  final BootstrapCi? bootstrap;

  const PairedComparison(this.metric, this.from, this.to, this.differences, this.wilcoxon, this.bootstrap);
}

class CoverageReport {
  final int apps;
  final double overall;
  final double privacy;
  final double openSource;
  final double resource;
  final double storeMetadata;

  const CoverageReport(this.apps, this.overall, this.privacy, this.openSource, this.resource, this.storeMetadata);

  /// Coverage of the frozen apps as captured (what configuration C sees).
  /// Descriptive data completeness - not accuracy.
  static CoverageReport? of(Iterable<Map<String, dynamic>> snapshotApps) {
    final apps = [for (final raw in snapshotApps) appForConfig(raw, EvaluationConfig.c)];
    if (apps.isEmpty) return null;
    double share(bool Function(AppInfo) f) => apps.where(f).length / apps.length;
    return CoverageReport(
      apps.length,
      apps.map((a) => a.metadataCoverage).reduce((a, b) => a + b) / apps.length,
      share((a) => a.trackerCount != null),
      share((a) => a.isOpenSource != null),
      share((a) => a.sizeMb != null || a.resourceLevel != null),
      share((a) => a.isFree != null || a.hasAds != null),
    );
  }
}

/// Everything the Evaluation screen and the exports report, computed only
/// from stored evaluation data.
class EvaluationAnalysis {
  final int taskCount;
  final int participantCount;
  final int appCount;
  final int evaluableTaskCount;
  final List<TaskMetrics> perTask;

  /// config -> metric -> mean over tasks where the metric is defined.
  final Map<EvaluationConfig, Map<String, double?>> means;
  final Map<EvaluationConfig, Summary?> latencyMicros;
  final Map<EvaluationConfig, (int consistent, int checked)> explanations;
  final List<PairedComparison> paired;
  final CoverageReport? coverage;

  /// Statement index -> (mean, n), only for answered statements.
  final Map<int, (double, int)> surveyMeans;

  const EvaluationAnalysis({
    required this.taskCount,
    required this.participantCount,
    required this.appCount,
    required this.evaluableTaskCount,
    required this.perTask,
    required this.means,
    required this.latencyMicros,
    required this.explanations,
    required this.paired,
    required this.coverage,
    required this.surveyMeans,
  });

  bool get hasRankingData => perTask.isNotEmpty;

  double? explanationConsistencyRate(EvaluationConfig config) {
    final e = explanations[config];
    if (e == null || e.$2 == 0) return null;
    return e.$1 / e.$2;
  }

  /// Latest labels per task: (taskId -> packageName -> grade).
  static Map<String, Map<String, int>> labelsByTask(List<RelevanceLabel> labels) {
    final sorted = [...labels]..sort((a, b) => a.labeledAt.compareTo(b.labeledAt));
    final out = <String, Map<String, int>>{};
    for (final l in sorted) {
      (out[l.taskId] ??= {})[l.packageName] = l.grade;
    }
    return out;
  }

  static EvaluationAnalysis build({
    required List<EvaluationTask> tasks,
    required List<CandidateSnapshot> snapshots,
    required List<RelevanceLabel> labels,
    required List<RankingRun> runs,
    required List<SurveyResponse> surveys,
  }) {
    final labelMap = labelsByTask(labels);
    // A task is evaluable only when every candidate has a human label.
    bool evaluable(EvaluationTask t) {
      final l = labelMap[t.taskId];
      return l != null && t.candidateAppIds.isNotEmpty && t.candidateAppIds.every(l.containsKey);
    }

    // Latest run per (task, config).
    final latest = <(String, EvaluationConfig), RankingRun>{};
    for (final run in runs) {
      final key = (run.taskId, run.config);
      final existing = latest[key];
      if (existing == null || run.timestamp.isAfter(existing.timestamp)) latest[key] = run;
    }

    final perTask = <TaskMetrics>[];
    for (final task in tasks.where(evaluable)) {
      final grades = labelMap[task.taskId]!;
      for (final config in EvaluationConfig.values) {
        final run = latest[(task.taskId, config)];
        if (run == null) continue;
        final ranking = run.ranking.where(grades.containsKey).toList();
        perTask.add(TaskMetrics(task.taskId, task.participantId, config, {
          'precision@3': RankingMetrics.precisionAtK(ranking, grades, 3),
          'recall@3': RankingMetrics.recallAtK(ranking, grades, 3),
          'ndcg@3': RankingMetrics.ndcgAtK(ranking, grades, 3),
          'precision@5': RankingMetrics.precisionAtK(ranking, grades, 5),
          'recall@5': RankingMetrics.recallAtK(ranking, grades, 5),
          'ndcg@5': RankingMetrics.ndcgAtK(ranking, grades, 5),
        }));
      }
    }

    final means = <EvaluationConfig, Map<String, double?>>{};
    for (final config in EvaluationConfig.values) {
      final rows = perTask.where((m) => m.config == config);
      means[config] = {
        for (final name in TaskMetrics.names)
          name: () {
            final vs = rows.map((r) => r.values[name]).whereType<double>().toList();
            return vs.isEmpty ? null : vs.reduce((a, b) => a + b) / vs.length;
          }(),
      };
    }

    final latencyMicros = <EvaluationConfig, Summary?>{};
    final explanations = <EvaluationConfig, (int, int)>{};
    for (final config in EvaluationConfig.values) {
      final configRuns = latest.values.where((r) => r.config == config).toList();
      latencyMicros[config] = Summary.of(configRuns.expand((r) => r.latenciesMicros));
      explanations[config] = (
        configRuns.fold(0, (a, r) => a + r.explanationsConsistent),
        configRuns.fold(0, (a, r) => a + r.explanationsChecked),
      );
    }

    final paired = <PairedComparison>[];
    for (final (from, to) in const [
      (EvaluationConfig.a, EvaluationConfig.b),
      (EvaluationConfig.b, EvaluationConfig.c),
      (EvaluationConfig.a, EvaluationConfig.c),
    ]) {
      for (final metric in TaskMetrics.names) {
        final diffs = <String, double>{};
        for (final task in tasks.where(evaluable)) {
          double? v(EvaluationConfig c) =>
              perTask.where((m) => m.taskId == task.taskId && m.config == c).firstOrNull?.values[metric];
          final x = v(from), y = v(to);
          if (x != null && y != null) diffs[task.taskId] = y - x;
        }
        final values = diffs.values.toList();
        paired.add(PairedComparison(metric, from, to, diffs, WilcoxonResult.compute(values), BootstrapCi.of(values)));
      }
    }

    final snapshotIds = tasks.map((t) => t.snapshotId).toSet();
    final usedApps = <String, Map<String, dynamic>>{};
    for (final s in snapshots.where((s) => snapshotIds.contains(s.snapshotId))) {
      for (final raw in s.apps) {
        usedApps.putIfAbsent('${s.snapshotId}/${raw['packageName'] ?? raw['id']}', () => raw);
      }
    }

    final surveyMeans = <int, (double, int)>{};
    for (var i = 0; i < SurveyResponse.statements.length; i++) {
      final scores = surveys.map((s) => s.answers[i]).whereType<int>().toList();
      if (scores.isNotEmpty) surveyMeans[i] = (scores.reduce((a, b) => a + b) / scores.length, scores.length);
    }

    return EvaluationAnalysis(
      taskCount: tasks.length,
      participantCount: tasks.map((t) => t.participantId).toSet().length,
      appCount: usedApps.values.map((a) => a['packageName'] ?? a['id']).toSet().length,
      evaluableTaskCount: tasks.where(evaluable).length,
      perTask: perTask,
      means: means,
      latencyMicros: latencyMicros,
      explanations: explanations,
      paired: paired,
      coverage: CoverageReport.of(usedApps.values),
      surveyMeans: surveyMeans,
    );
  }
}
