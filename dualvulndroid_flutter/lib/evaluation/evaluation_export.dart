import 'dart:convert';

import 'evaluation_models.dart';
import 'evaluation_runner.dart';
import 'ranking_metrics.dart';

/// All Evaluation Mode data. Serialized as one JSON document (lossless -
/// importable back) and as CSV tables for statistics tools. Only stored
/// rows are written; nothing is padded or invented.
class EvaluationDataset {
  static const formatVersion = 1;

  final List<CandidateSnapshot> snapshots;
  final List<EvaluationTask> tasks;
  final List<RelevanceLabel> labels;
  final List<RankingRun> runs;
  final List<SurveyResponse> surveys;

  const EvaluationDataset({
    this.snapshots = const [],
    this.tasks = const [],
    this.labels = const [],
    this.runs = const [],
    this.surveys = const [],
  });

  bool get isEmpty => snapshots.isEmpty && tasks.isEmpty && labels.isEmpty && runs.isEmpty && surveys.isEmpty;

  EvaluationAnalysis analyse() =>
      EvaluationAnalysis.build(tasks: tasks, snapshots: snapshots, labels: labels, runs: runs, surveys: surveys);

  Map<String, dynamic> toJson() => {
        'format': 'smartapp-evaluation',
        'formatVersion': formatVersion,
        'snapshots': [for (final s in snapshots) s.toJson()],
        'tasks': [for (final t in tasks) t.toJson()],
        'labels': [for (final l in labels) l.toJson()],
        'runs': [for (final r in runs) r.toJson()],
        'surveys': [for (final s in surveys) s.toJson()],
      };

  factory EvaluationDataset.fromJson(Map<String, dynamic> json) {
    if (json['format'] != 'smartapp-evaluation') throw const FormatException('Not a SmartApp evaluation export');
    List<Map<String, dynamic>> list(String key) => [for (final e in (json[key] as List? ?? const [])) Map<String, dynamic>.from(e as Map)];
    return EvaluationDataset(
      snapshots: list('snapshots').map(CandidateSnapshot.fromJson).toList(),
      tasks: list('tasks').map(EvaluationTask.fromJson).toList(),
      labels: list('labels').map(RelevanceLabel.fromJson).toList(),
      runs: list('runs').map(RankingRun.fromJson).toList(),
      surveys: list('surveys').map(SurveyResponse.fromJson).toList(),
    );
  }

  String toJsonString() => const JsonEncoder.withIndent('  ').convert(toJson());

  static EvaluationDataset fromJsonString(String text) => EvaluationDataset.fromJson(jsonDecode(text) as Map<String, dynamic>);

  // ---- CSV exports ---------------------------------------------------------

  /// Per-task, per-configuration metrics (empty cell = undefined metric).
  String taskResultsCsv(EvaluationAnalysis analysis) => _csv(
        ['taskId', 'participantId', 'config', ...TaskMetrics.names],
        [
          for (final m in analysis.perTask)
            [m.taskId, m.participantId, m.config.code, for (final n in TaskMetrics.names) _num(m.values[n])],
        ],
      );

  /// Paired per-task differences, ready for Wilcoxon signed-rank / bootstrap.
  String pairedDifferencesCsv(EvaluationAnalysis analysis) => _csv(
        ['metric', 'comparison', 'taskId', 'difference'],
        [
          for (final p in analysis.paired)
            for (final e in p.differences.entries) [p.metric, '${p.to.code}-${p.from.code}', e.key, _num(e.value)],
        ],
      );

  String rankingsCsv() => _csv(
        ['evaluationId', 'timestamp', 'snapshotId', 'config', 'taskId', 'participantId', 'rank', 'packageName', 'matchPercent'],
        [
          for (final r in runs)
            for (var i = 0; i < r.ranking.length; i++)
              [r.evaluationId, r.timestamp.toUtc().toIso8601String(), r.snapshotId, r.config.code, r.taskId, r.participantId, '${i + 1}', r.ranking[i], '${r.scores[i]}'],
        ],
      );

  String labelsCsv() => _csv(
        ['taskId', 'participantId', 'packageName', 'grade', 'labeledAt'],
        [for (final l in labels) [l.taskId, l.participantId, l.packageName, '${l.grade}', l.labeledAt.toUtc().toIso8601String()]],
      );

  String latencyCsv() => _csv(
        ['evaluationId', 'config', 'taskId', 'repetition', 'latencyMicros'],
        [
          for (final r in runs)
            for (var i = 0; i < r.latenciesMicros.length; i++) [r.evaluationId, r.config.code, r.taskId, '${i + 1}', '${r.latenciesMicros[i]}'],
        ],
      );

  String explanationCsv() => _csv(
        ['evaluationId', 'config', 'taskId', 'consistent', 'checked'],
        [for (final r in runs) [r.evaluationId, r.config.code, r.taskId, '${r.explanationsConsistent}', '${r.explanationsChecked}']],
      );

  String coverageCsv() => _csv(
        ['snapshotId', 'packageName', 'metadataCoverage', 'metadataSources', 'collectedAt'],
        [
          for (final s in snapshots)
            for (final a in s.apps)
              [
                s.snapshotId,
                '${a['packageName'] ?? a['id']}',
                _num((a['metadataCoverage'] as num?)?.toDouble()),
                ((a['metadataSources'] as List?) ?? const []).join('|'),
                s.collectedAt.toUtc().toIso8601String(),
              ],
        ],
      );

  String surveyCsv() => _csv(
        ['participantId', 'submittedAt', 'statementIndex', 'statement', 'score'],
        [
          for (final s in surveys)
            for (final e in s.answers.entries)
              [s.participantId, s.submittedAt.toUtc().toIso8601String(), '${e.key}', SurveyResponse.statements[e.key], '${e.value}'],
        ],
      );

  /// Every CSV table, keyed by file name.
  Map<String, String> allCsv() {
    final analysis = analyse();
    return {
      'task_results.csv': taskResultsCsv(analysis),
      'paired_differences.csv': pairedDifferencesCsv(analysis),
      'rankings.csv': rankingsCsv(),
      'relevance_labels.csv': labelsCsv(),
      'latency.csv': latencyCsv(),
      'explanation_consistency.csv': explanationCsv(),
      'metadata_coverage.csv': coverageCsv(),
      'survey.csv': surveyCsv(),
    };
  }

  static String _num(double? v) => v == null ? '' : v.toStringAsFixed(6);

  static String _csv(List<String> header, List<List<String>> rows) {
    String cell(String v) => v.contains(RegExp(r'[",\n]')) ? '"${v.replaceAll('"', '""')}"' : v;
    return [header, ...rows].map((r) => r.map(cell).join(',')).join('\n');
  }
}

/// Formats a summary for display: mean, or null-safe "—".
String formatMetric(double? v) => v == null ? '—' : v.toStringAsFixed(3);

/// A short description of a paired comparison's statistics, or null when
/// there are no paired data (no conclusion is ever stated without data).
String? describePaired(PairedComparison p) {
  if (p.differences.isEmpty) return null;
  final parts = <String>['n=${p.differences.length}'];
  final ci = p.bootstrap;
  if (ci != null) parts.add('mean Δ ${ci.mean.toStringAsFixed(3)} [95% CI ${ci.lower.toStringAsFixed(3)}, ${ci.upper.toStringAsFixed(3)}]');
  final w = p.wilcoxon;
  if (w != null) {
    parts.add(w.pTwoSided == null
        ? 'Wilcoxon W+=${w.wPlus.toStringAsFixed(1)} W-=${w.wMinus.toStringAsFixed(1)} (n<10: use exact tables)'
        : 'Wilcoxon z=${w.z!.toStringAsFixed(2)} p=${w.pTwoSided!.toStringAsFixed(3)}');
  }
  return parts.join(' · ');
}

// Re-exported for screens that only import this file.
typedef LatencySummary = Summary;
