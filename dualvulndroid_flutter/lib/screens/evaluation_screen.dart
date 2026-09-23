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

/// Research Evaluation Mode. Every number here is computed from stored
/// evaluation data: frozen candidate snapshots, human relevance labels,
/// timed ranking runs and survey answers. With no data it says "No
/// evaluation data available." - nothing is simulated. Configurations are
/// shown side by side with identical styling; none is marked as better.
class EvaluationScreen extends StatelessWidget {
  const EvaluationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final repo = context.watch<EvaluationRepository>();
    if (repo.isLoading) return const Scaffold(body: LoadingView());
    final analysis = repo.analyse();
    final data = repo.data;

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
          Text(
            'Research mode. Uses frozen candidate snapshots and human relevance labels, stored separately from your normal '
            'SmartApp data. SmartApp\'s own scores are never used as ground truth.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.xl),

          // ---- Dataset ------------------------------------------------------
          const SectionHeader(title: 'Evaluation Dataset', icon: AppIcons.evaluation),
          ResponsiveGrid(
            columns: 3,
            spacing: AppSpacing.sm,
            children: [
              MetricCard(label: 'Tasks', value: '${analysis.taskCount}'),
              MetricCard(label: 'Participants', value: '${analysis.participantCount}'),
              MetricCard(label: 'Apps', value: '${analysis.appCount}'),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text('${analysis.evaluableTaskCount} of ${analysis.taskCount} tasks fully labeled', style: theme.textTheme.bodySmall),
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              FilledButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EvaluationTaskScreen())),
                icon: const Icon(Icons.add_rounded),
                label: const Text('New task'),
              ),
              OutlinedButton.icon(
                // Metrics only use fully labeled tasks, so running earlier
                // would "succeed" and still show no results.
                onPressed: analysis.evaluableTaskCount == 0
                    ? null
                    : () async {
                        final id = await context.read<EvaluationRepository>().runEvaluation();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(content: Text('Ran A, B and C on ${analysis.evaluableTaskCount} fully labeled task(s) · $id')),
                          );
                        }
                      },
                icon: const Icon(Icons.play_arrow_rounded),
                label: const Text('Run A / B / C'),
              ),
              OutlinedButton.icon(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EvaluationSurveyScreen())),
                icon: const Icon(Icons.rate_review_outlined),
                label: const Text('Survey'),
              ),
            ],
          ),
          if (data.tasks.isNotEmpty && analysis.evaluableTaskCount == 0) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Rate every app in a task (tap it below) to enable Run A / B / C.',
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

          // ---- Ranking metrics -------------------------------------------
          const SectionHeader(
            title: 'Ranking Metrics',
            subtitle: 'Means over fully labeled tasks. Relevant = labeled Suitable (2) or Highly suitable (3).',
          ),
          if (!analysis.hasRankingData)
            const _NoData()
          else
            _ConfigTable(
              rows: [
                for (final name in TaskMetrics.names)
                  (_metricLabel(name), [for (final c in EvaluationConfig.values) formatMetric(analysis.means[c]![name])]),
              ],
            ),
          const SizedBox(height: AppSpacing.section),

          // ---- Before / after ----------------------------------------------
          const SectionHeader(
            title: 'Paired comparison',
            subtitle: 'Same participants, tasks and frozen candidates - only the ranking configuration changes.',
          ),
          if (!analysis.hasRankingData)
            const _NoData()
          else
            SmartAppCard(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
              child: Column(
                children: [
                  for (final p in analysis.paired.where((p) => p.metric.startsWith('ndcg')))
                    DetailRow(
                      label: '${p.metric.toUpperCase()}  ${p.to.code} vs ${p.from.code}',
                      value: describePaired(p) ?? 'No paired data',
                      muted: p.differences.isEmpty,
                    ),
                ],
              ),
            ),
          const SizedBox(height: AppSpacing.section),

          // ---- Coverage ---------------------------------------------------
          const SectionHeader(
            title: 'Metadata Coverage',
            subtitle: 'Share of recommendation data verified for the frozen candidates - not an accuracy figure.',
          ),
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
          const SizedBox(height: AppSpacing.section),

          // ---- Response time + explanations ---------------------------------
          const SectionHeader(title: 'Response Time', subtitle: 'Time to rank one task\'s candidates on this device.'),
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
          const SizedBox(height: AppSpacing.section),
          const SectionHeader(
            title: 'Explanation consistency',
            subtitle: 'Displayed "Why this app?" points that match the real result values.',
          ),
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
          const SizedBox(height: AppSpacing.section),

          // ---- Survey -------------------------------------------------------
          const SectionHeader(title: 'User Feedback', subtitle: 'Mean survey scores (1 = Strongly disagree, 5 = Strongly agree).'),
          if (analysis.surveyMeans.isEmpty)
            const _NoData()
          else
            SmartAppCard(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
              child: Column(
                children: [
                  for (final e in analysis.surveyMeans.entries)
                    DetailRow(label: SurveyResponse.statements[e.key], value: '${e.value.$1.toStringAsFixed(2)} (n=${e.value.$2})'),
                ],
              ),
            ),
          const SizedBox(height: AppSpacing.section),
          const _InAppFeedbackSection(),
        ],
      ),
    );
  }

  static String _labelStatus(EvaluationDataset data, EvaluationTask task) {
    final labeled = data.labels.where((l) => l.taskId == task.taskId).map((l) => l.packageName).toSet();
    final done = task.candidateAppIds.where(labeled.contains).length;
    return '$done of ${task.candidateAppIds.length} candidates labeled · tap to judge';
  }

  static String _metricLabel(String name) => name.replaceFirstMapped(RegExp(r'^\w'), (m) => m[0]!.toUpperCase()).replaceAll('Ndcg', 'NDCG');
  static String _pct(double v) => '${(v * 100).round()}%';
  static String _ms(double? micros) => micros == null ? '—' : '${(micros / 1000).toStringAsFixed(2)} ms';
}

class _NoData extends StatelessWidget {
  const _NoData();

  @override
  Widget build(BuildContext context) {
    return const InsightBanner(
      title: 'No evaluation data available.',
      icon: AppIcons.info,
      color: AppColors.textSecondary,
      messages: ['Create a task, label its candidates, then run A / B / C.'],
    );
  }
}

/// Metric rows x configurations A/B/C - identical styling for every column.
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
    return SmartAppCard(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
      child: Table(
        columnWidths: const {0: FlexColumnWidth(1.3), 1: FlexColumnWidth(), 2: FlexColumnWidth(), 3: FlexColumnWidth()},
        children: [
          TableRow(children: [
            cell('', header: true, align: TextAlign.start),
            for (final c in EvaluationConfig.values) Tooltip(message: c.label, child: cell(c.code, header: true)),
          ]),
          for (final (label, values) in rows)
            TableRow(children: [cell(label, align: TextAlign.start), for (final v in values) cell(v)]),
        ],
      ),
    );
  }
}

/// The earlier in-app feedback metrics (from normal usage), kept separate
/// from the research dataset and clearly labeled as such.
class _InAppFeedbackSection extends StatelessWidget {
  const _InAppFeedbackSection();

  @override
  Widget build(BuildContext context) {
    final history = context.watch<HistoryRepository>().entries;
    final feedback = context.watch<FeedbackRepository>().entries;
    const engine = EvaluationEngine();
    final report = engine.evaluate(history: history, feedback: feedback);
    final coverage = engine.averageMetadataCoverage(history);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(
          title: 'In-app feedback (not part of the research dataset)',
          subtitle: 'From normal use: your history plus "helpful" feedback on app details.',
        ),
        SmartAppCard(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
          child: Column(
            children: [
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
          ),
        ),
      ],
    );
  }
}

