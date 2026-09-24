import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/evaluation_engine.dart';
import '../engines/recommendation_engine.dart';
import '../evaluation/evaluation_export.dart';
import '../evaluation/evaluation_models.dart';
import '../evaluation/evaluation_runner.dart';
import '../repositories/evaluation_repository.dart';
import '../repositories/feedback_repository.dart';
import '../repositories/history_repository.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';
import 'evaluation_flows.dart';

/// Research Evaluation Mode, in plain language first: what the test is, the
/// three steps, and a one-line answer to "which ranking method agrees best
/// with people?". The full statistics stay available under "Detailed
/// numbers". Every value is computed from stored evaluation data; with no
/// data the screen says so and shows no numbers.
class EvaluationScreen extends StatelessWidget {
  const EvaluationScreen({super.key});

  /// Paired tests needed before the Wilcoxon test reports a p-value.
  static const reliableTaskCount = 10;

  /// Plain names for the three ranking methods.
  static String methodName(EvaluationConfig c) => switch (c) {
        EvaluationConfig.a => 'Old scoring',
        EvaluationConfig.b => 'New scoring',
        EvaluationConfig.c => 'New scoring + extra data',
      };

  static String methodDescription(EvaluationConfig c) => switch (c) {
        EvaluationConfig.a => 'The earlier formula: unknown information was counted as neutral or as a failed preference.',
        EvaluationConfig.b => 'Only verified information counts; uses the Google Play search result alone.',
        EvaluationConfig.c => 'Same as New scoring, plus verified extra data (Play store facts, F-Droid, εxodus).',
      };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final repo = context.watch<EvaluationRepository>();
    if (repo.isLoading) return const Scaffold(body: LoadingView());
    final analysis = repo.analyse();
    final data = repo.data;
    final rated = analysis.evaluableTaskCount;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Evaluation'),
        actions: [
          IconButton(
            tooltip: 'Export / import',
            icon: const Icon(Icons.ios_share_rounded),
            onPressed: () => showEvaluationExportSheet(context),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
        children: [
          Text('Does SmartApp rank apps the way people would?', style: theme.textTheme.titleMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'A person rates a fixed set of apps without seeing any SmartApp score. SmartApp then checks which of its '
            'ranking methods puts the apps that person liked at the top. SmartApp\'s own scores are never used as the answer.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.xl),

          // ---- The three steps ---------------------------------------------
          const SectionHeader(title: 'How it works', icon: AppIcons.evaluation),
          SmartAppCard(
            child: Column(
              children: [
                _Step(
                  number: 1,
                  title: 'Create a test',
                  body: 'Enter a participant code and pick a category. SmartApp saves up to 10 live apps so they cannot change during the test.',
                  status: '${analysis.taskCount} test(s) created',
                  done: analysis.taskCount > 0,
                ),
                _Step(
                  number: 2,
                  title: 'Rate every app',
                  body: 'The participant rates each app from 0 (not suitable) to 3 (highly suitable). Apps appear in random order.',
                  status: '$rated of ${analysis.taskCount} tests fully rated',
                  done: rated > 0,
                ),
                _Step(
                  number: 3,
                  title: 'Compare the methods',
                  body: 'SmartApp ranks the same apps with its three methods and checks each ranking against the ratings.',
                  status: analysis.hasRankingData ? 'Compared' : 'Not compared yet',
                  done: analysis.hasRankingData,
                  last: true,
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              FilledButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EvaluationTaskScreen())),
                icon: const Icon(Icons.add_rounded),
                label: const Text('New test'),
              ),
              OutlinedButton.icon(
                // Metrics only use fully rated tests, so comparing earlier
                // would "succeed" and still show no results.
                onPressed: rated == 0
                    ? null
                    : () async {
                        await context.read<EvaluationRepository>().runEvaluation();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Compared the three methods on $rated fully rated test(s).')),
                          );
                        }
                      },
                icon: const Icon(Icons.play_arrow_rounded),
                label: const Text('Compare methods'),
              ),
              OutlinedButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EvaluationSurveyScreen())),
                icon: const Icon(Icons.rate_review_outlined),
                label: const Text('Survey'),
              ),
            ],
          ),
          if (data.tasks.isNotEmpty && rated == 0) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Rate every app in a test (tap it below) to enable Compare methods.',
              style: theme.textTheme.bodySmall?.copyWith(color: AppColors.warning),
            ),
          ],
          if (data.tasks.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.lg),
            SmartAppCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  for (final task in data.tasks)
                    NavigationRow(
                      icon: Icons.assignment_outlined,
                      iconColor: AppColors.textSecondary,
                      title: '${task.participantId} · ${task.category}',
                      subtitle: _labelStatus(data, task),
                      onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => RelevanceJudgingScreen(taskId: task.taskId))),
                    ),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.section),

          // ---- The methods ------------------------------------------------
          const SectionHeader(title: 'The three methods compared'),
          SmartAppCard(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
            child: Column(
              children: [
                for (final c in EvaluationConfig.values)
                  DetailRow(label: '${c.code} · ${methodName(c)}', value: methodDescription(c)),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.section),

          // ---- Result -----------------------------------------------------
          const SectionHeader(title: 'Result', subtitle: 'How closely each method\'s top 5 matches the people\'s ratings.'),
          if (!analysis.hasRankingData) const _NoData() else _ResultSummary(analysis: analysis),
          const SizedBox(height: AppSpacing.section),

          // ---- Everything else, for the thesis ------------------------------
          _DetailedNumbers(analysis: analysis),
        ],
      ),
    );
  }

  static String _labelStatus(EvaluationDataset data, EvaluationTask task) {
    final labeled = data.labels.where((l) => l.taskId == task.taskId).map((l) => l.packageName).toSet();
    final done = task.candidateAppIds.where(labeled.contains).length;
    return '$done of ${task.candidateAppIds.length} apps rated · tap to rate';
  }
}

class _Step extends StatelessWidget {
  final int number;
  final String title;
  final String body;
  final String status;
  final bool done;
  final bool last;
  const _Step({required this.number, required this.title, required this.body, required this.status, required this.done, this.last = false});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colour = done ? AppColors.success : AppColors.textSecondary;
    return Padding(
      padding: EdgeInsets.only(bottom: last ? 0 : AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 14,
            backgroundColor: colour.withValues(alpha: 0.12),
            child: done
                ? Icon(Icons.check_rounded, size: 16, color: colour)
                : Text('$number', style: theme.textTheme.labelMedium?.copyWith(color: colour)),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleSmall),
                const SizedBox(height: 2),
                Text(body, style: theme.textTheme.bodySmall),
                const SizedBox(height: 2),
                Text(status, style: theme.textTheme.labelSmall?.copyWith(color: colour, letterSpacing: 0)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// The plain-language answer: one agreement bar per method, which method
/// agreed best, and how far the result can be trusted.
class _ResultSummary extends StatelessWidget {
  final EvaluationAnalysis analysis;
  const _ResultSummary({required this.analysis});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final scores = {for (final c in EvaluationConfig.values) c: analysis.means[c]?['ndcg@5']};
    final known = scores.entries.where((e) => e.value != null).toList()..sort((a, b) => b.value!.compareTo(a.value!));
    final best = known.isEmpty ? null : known.first;
    final tie = known.length > 1 && best != null && (best.value! - known[1].value!).abs() < 0.005;
    final paired = analysis.paired.where((p) => p.metric == 'ndcg@5' && p.from == EvaluationConfig.a && p.to == EvaluationConfig.c).firstOrNull;
    final n = analysis.evaluableTaskCount;

    return SmartAppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final c in EvaluationConfig.values) ...[
            Row(
              children: [
                Expanded(child: Text('${c.code} · ${EvaluationScreen.methodName(c)}', style: theme.textTheme.bodyMedium)),
                Text(scores[c] == null ? '—' : '${(scores[c]! * 100).round()}%', style: theme.textTheme.titleSmall),
              ],
            ),
            const SizedBox(height: 4),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(value: scores[c] ?? 0, minHeight: 8, backgroundColor: AppColors.border),
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          Text(
            '100% means the apps people rated highest are exactly at the top of that method\'s list.',
            style: theme.textTheme.bodySmall,
          ),
          if (best != null) ...[
            const SizedBox(height: AppSpacing.md),
            Text(
              tie ? 'The methods agreed with people about equally well.' : '${EvaluationScreen.methodName(best.key)} agreed best with people.',
              style: theme.textTheme.titleSmall,
            ),
          ],
          if (paired != null && paired.differences.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xs),
            Text(_betterWorse(paired), style: theme.textTheme.bodySmall),
          ],
          const SizedBox(height: AppSpacing.xs),
          Text(_reliability(paired, n), style: theme.textTheme.bodySmall?.copyWith(color: AppColors.textSecondary)),
        ],
      ),
    );
  }

  static String _betterWorse(PairedComparison p) {
    final d = p.differences.values;
    final better = d.where((v) => v > 0.0005).length;
    final worse = d.where((v) => v < -0.0005).length;
    final same = d.length - better - worse;
    return 'New scoring + extra data compared with Old scoring: better in $better test(s), worse in $worse, the same in $same.';
  }

  static String _reliability(PairedComparison? p, int n) {
    final pValue = p?.wilcoxon?.pTwoSided;
    if (n < EvaluationScreen.reliableTaskCount || pValue == null) {
      return 'Based on $n rated test(s). At least ${EvaluationScreen.reliableTaskCount} are needed before a difference can be called reliable.';
    }
    return pValue < 0.05
        ? 'Based on $n rated tests, this difference is statistically reliable (p = ${pValue.toStringAsFixed(3)}).'
        : 'Based on $n rated tests, this difference could still be due to chance (p = ${pValue.toStringAsFixed(3)}).';
  }
}

/// Every measured value, grouped under one collapsible section so the
/// screen stays readable. Plain names first, research names in brackets.
class _DetailedNumbers extends StatelessWidget {
  final EvaluationAnalysis analysis;
  const _DetailedNumbers({required this.analysis});

  static const _metricNames = {
    'precision@3': 'Good apps in the top 3 (Precision@3)',
    'recall@3': 'Share of good apps found in the top 3 (Recall@3)',
    'ndcg@3': 'Order quality of the top 3 (NDCG@3)',
    'precision@5': 'Good apps in the top 5 (Precision@5)',
    'recall@5': 'Share of good apps found in the top 5 (Recall@5)',
    'ndcg@5': 'Order quality of the top 5 (NDCG@5)',
  };

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      padding: EdgeInsets.zero,
      child: Theme(
        data: theme.copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          title: Text('Detailed numbers', style: theme.textTheme.titleSmall),
          subtitle: Text('For the thesis: every metric, statistics, coverage, timing and survey.', style: theme.textTheme.bodySmall),
          childrenPadding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ResponsiveGrid(
              columns: 3,
              spacing: AppSpacing.sm,
              children: [
                MetricCard(label: 'Tests', value: '${analysis.taskCount}'),
                MetricCard(label: 'Participants', value: '${analysis.participantCount}'),
                MetricCard(label: 'Apps', value: '${analysis.appCount}'),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),
            const _Glossary(),
            const SizedBox(height: AppSpacing.lg),
            Text('Ranking quality (averages over fully rated tests)', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            if (!analysis.hasRankingData)
              const _NoData()
            else
              _ConfigTable(
                rows: [
                  for (final name in TaskMetrics.names)
                    (_metricNames[name]!, [for (final c in EvaluationConfig.values) formatMetric(analysis.means[c]![name])]),
                ],
              ),
            const SizedBox(height: AppSpacing.lg),
            Text('Method against method, test by test', style: theme.textTheme.titleSmall),
            Text(
              'Δ is the average change in order quality; the 95% range comes from 2,000 bootstrap resamples. '
              'The Wilcoxon test gives a p-value once at least ${EvaluationScreen.reliableTaskCount} tests differ.',
              style: theme.textTheme.bodySmall,
            ),
            const SizedBox(height: AppSpacing.xs),
            if (!analysis.hasRankingData)
              const _NoData()
            else
              for (final p in analysis.paired.where((p) => p.metric.startsWith('ndcg')))
                DetailRow(
                  label: '${p.metric.toUpperCase()}  ${p.to.code} vs ${p.from.code}',
                  value: describePaired(p) ?? 'No paired data',
                  muted: p.differences.isEmpty,
                ),
            const SizedBox(height: AppSpacing.lg),
            Text('Verified data behind the tested apps', style: theme.textTheme.titleSmall),
            Text('How complete the data was - not an accuracy figure.', style: theme.textTheme.bodySmall),
            const SizedBox(height: AppSpacing.xs),
            if (analysis.coverage == null)
              const _NoData()
            else
              ResponsiveGrid(
                columns: 3,
                spacing: AppSpacing.sm,
                children: [
                  MetricCard(label: 'Average', value: _pct(analysis.coverage!.overall)),
                  MetricCard(label: 'Privacy', value: _pct(analysis.coverage!.privacy)),
                  MetricCard(label: 'Open source', value: _pct(analysis.coverage!.openSource)),
                  MetricCard(label: 'Resource', value: _pct(analysis.coverage!.resource)),
                  MetricCard(label: 'Store', value: _pct(analysis.coverage!.storeMetadata)),
                ],
              ),
            const SizedBox(height: AppSpacing.lg),
            Text('Time to rank one test on this phone', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            if (EvaluationConfig.values.every((c) => analysis.latencyMicros[c] == null))
              const _NoData()
            else
              _ConfigTable(
                rows: [
                  ('Mean', [for (final c in EvaluationConfig.values) _ms(analysis.latencyMicros[c]?.mean)]),
                  ('Median', [for (final c in EvaluationConfig.values) _ms(analysis.latencyMicros[c]?.median)]),
                  ('P95', [for (final c in EvaluationConfig.values) _ms(analysis.latencyMicros[c]?.p95)]),
                ],
              ),
            const SizedBox(height: AppSpacing.lg),
            Text('"Why this app?" explanations that match the real score', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            if (EvaluationConfig.values.every((c) => analysis.explanationConsistencyRate(c) == null))
              const _NoData()
            else
              _ConfigTable(
                rows: [
                  (
                    'Consistent',
                    [
                      for (final c in EvaluationConfig.values)
                        analysis.explanationConsistencyRate(c) == null
                            ? '—'
                            : '${analysis.explanations[c]!.$1}/${analysis.explanations[c]!.$2} (${_pct(analysis.explanationConsistencyRate(c)!)})',
                    ],
                  ),
                ],
              ),
            const SizedBox(height: AppSpacing.lg),
            Text('Survey (1 = strongly disagree, 5 = strongly agree)', style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.xs),
            if (analysis.surveyMeans.isEmpty)
              const _NoData()
            else
              for (final e in analysis.surveyMeans.entries)
                DetailRow(label: SurveyResponse.statements[e.key], value: '${e.value.$1.toStringAsFixed(2)} (n=${e.value.$2})'),
            const SizedBox(height: AppSpacing.lg),
            const _InAppFeedbackSection(),
          ],
        ),
      ),
    );
  }

  static String _pct(double v) => '${(v * 100).round()}%';
  static String _ms(double? micros) => micros == null ? '—' : '${(micros / 1000).toStringAsFixed(2)} ms';
}

class _Glossary extends StatelessWidget {
  const _Glossary();

  @override
  Widget build(BuildContext context) {
    return const InsightBanner(
      title: 'What the numbers mean',
      icon: AppIcons.info,
      color: AppColors.textSecondary,
      messages: [
        'A "good app" is one the participant rated 2 (suitable) or 3 (highly suitable).',
        'Precision@k: of the first k apps a method shows, how many are good.',
        'Recall@k: of all the good apps, how many appear in the first k.',
        'NDCG@k: how well the first k are ordered; 1.000 means the best-rated apps come first.',
      ],
    );
  }
}

class _NoData extends StatelessWidget {
  const _NoData();

  @override
  Widget build(BuildContext context) {
    return const InsightBanner(
      title: 'No evaluation data available.',
      icon: AppIcons.info,
      color: AppColors.textSecondary,
      messages: ['Create a test, rate its apps, then press Compare methods.'],
    );
  }
}

/// Metric rows x methods A/B/C - identical styling for every column.
class _ConfigTable extends StatelessWidget {
  final List<(String, List<String>)> rows;
  const _ConfigTable({required this.rows});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    Widget cell(String text, {bool header = false, TextAlign align = TextAlign.end}) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Text(text, textAlign: align, style: header ? theme.textTheme.labelMedium : theme.textTheme.bodyMedium),
        );
    return Table(
      columnWidths: const {0: FlexColumnWidth(2.2), 1: FlexColumnWidth(), 2: FlexColumnWidth(), 3: FlexColumnWidth()},
      children: [
        TableRow(children: [
          cell('', header: true, align: TextAlign.start),
          for (final c in EvaluationConfig.values) Tooltip(message: EvaluationScreen.methodName(c), child: cell(c.code, header: true)),
        ]),
        for (final (label, values) in rows)
          TableRow(children: [cell(label, align: TextAlign.start), for (final v in values) cell(v)]),
      ],
    );
  }
}

/// The earlier in-app feedback metrics (from normal usage), kept separate
/// from the research dataset and clearly labeled as such.
class _InAppFeedbackSection extends StatelessWidget {
  const _InAppFeedbackSection();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final history = context.watch<HistoryRepository>().entries;
    final feedback = context.watch<FeedbackRepository>().entries;
    const engine = EvaluationEngine();
    final report = engine.evaluate(history: history, feedback: feedback);
    final coverage = engine.averageMetadataCoverage(history);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('From normal use (not part of the test data)', style: theme.textTheme.titleSmall),
        DetailRow(
          label: 'Ranking quality (all history)',
          value: report == null
              ? 'No evaluation data available.'
              : 'P@${report.k} ${report.precisionAtK.toStringAsFixed(2)} · NDCG ${report.ndcgAtK.toStringAsFixed(2)} (${report.sessionsEvaluated})',
          muted: report == null,
        ),
        DetailRow(
          label: 'Verified data coverage of shown apps',
          value: coverage == null ? 'No evaluation data available.' : '${(coverage * 100).round()}%',
          muted: coverage == null,
        ),
        DetailRow(label: 'Current scoring version', value: '${RecommendationEngine.scoringVersion}'),
      ],
    );
  }
}
