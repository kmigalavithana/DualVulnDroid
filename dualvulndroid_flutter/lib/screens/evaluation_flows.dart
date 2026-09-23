import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../evaluation/evaluation_export.dart';
import '../evaluation/evaluation_models.dart';
import '../models/app_info_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/app_repository.dart';
import '../repositories/device_profile_repository.dart';
import '../repositories/evaluation_repository.dart';
import '../repositories/preferences_repository.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../utils/byte_format.dart';
import '../widgets/app_icon.dart';
import '../widgets/category_icons.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

/// Evaluation Mode sub-flows: create a task over a frozen snapshot, judge
/// candidates blind (no SmartApp scores shown), fill in the survey, and
/// export/import the dataset.

// ---------------------------------------------------------------------------
// New task
// ---------------------------------------------------------------------------

class EvaluationTaskScreen extends StatefulWidget {
  const EvaluationTaskScreen({super.key});

  /// How many live candidates a new snapshot captures.
  static const candidateLimit = 10;

  @override
  State<EvaluationTaskScreen> createState() => _EvaluationTaskScreenState();
}

class _EvaluationTaskScreenState extends State<EvaluationTaskScreen> {
  final _participant = TextEditingController();
  AppCategory _category = AppCategory.productivity;
  late Set<AppPreference> _preferences;
  String? _snapshotId; // null = capture a new snapshot
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _preferences = {...context.read<PreferencesRepository>().preferences.selectedPreferences};
  }

  @override
  void dispose() {
    _participant.dispose();
    super.dispose();
  }

  Future<void> _create() async {
    final participant = _participant.text.trim();
    if (participant.isEmpty) {
      setState(() => _error = 'Enter a participant ID.');
      return;
    }
    final repo = context.read<EvaluationRepository>();
    final device = context.read<DeviceProfileRepository>().profile;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      CandidateSnapshot snapshot;
      final existing = repo.data.snapshots.where((s) => s.snapshotId == _snapshotId).firstOrNull;
      if (existing != null) {
        snapshot = existing;
      } else {
        final apps = await context.read<AppRepository>().searchApps(category: _category.label, limit: EvaluationTaskScreen.candidateLimit);
        if (apps.isEmpty) throw StateError('Google Play returned no apps for ${_category.label}.');
        snapshot = await repo.freezeSnapshot(category: _category.label, apps: apps);
      }
      final task = await repo.createTask(participantId: participant, preferences: _preferences, device: device, snapshot: snapshot);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => RelevanceJudgingScreen(taskId: task.taskId)));
    } catch (e) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = e is StateError ? e.message : 'Unable to load live app data for the snapshot.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final device = context.watch<DeviceProfileRepository>().profile;
    final snapshots = context.watch<EvaluationRepository>().data.snapshots.where((s) => s.category == _category.label).toList();

    return Scaffold(
      appBar: AppBar(title: const Text('New evaluation task')),
      body: ListView(
        padding: AppSpacing.pagePadding,
        children: [
          TextField(
            controller: _participant,
            decoration: const InputDecoration(labelText: 'Participant ID', hintText: 'e.g. P01'),
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Category'),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              for (final c in AppCategory.values.where((c) => c != AppCategory.other))
                ChoiceChip(
                  avatar: Icon(resolveIconKey(c.iconKey), size: 18),
                  label: Text(c.label),
                  selected: c == _category,
                  onSelected: (_) => setState(() {
                    _category = c;
                    _snapshotId = null;
                  }),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Candidates', subtitle: 'Frozen once and reused unchanged by every configuration.'),
          RadioGroup<String?>(
            groupValue: _snapshotId,
            onChanged: (v) => setState(() => _snapshotId = v),
            child: Column(
              children: [
                RadioListTile<String?>(
                  value: null,
                  title: Text('Capture a new snapshot (up to ${EvaluationTaskScreen.candidateLimit} live apps)'),
                  contentPadding: EdgeInsets.zero,
                ),
                for (final s in snapshots)
                  RadioListTile<String?>(
                    value: s.snapshotId,
                    title: Text('Reuse snapshot · ${s.apps.length} apps'),
                    subtitle: Text('Collected ${s.collectedAt.toLocal()}'),
                    contentPadding: EdgeInsets.zero,
                  ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          const SectionHeader(title: 'Participant preferences'),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              for (final p in AppPreference.values)
                PreferenceChip(
                  label: p.label,
                  icon: AppIcons.forPreference(p),
                  selected: _preferences.contains(p),
                  onSelected: (v) => setState(() => v ? _preferences.add(p) : _preferences.remove(p)),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Device snapshot', subtitle: 'This device\'s real values, stored with the task.'),
          Text(
            'RAM ${formatMb(device.ramTotalMb)} · Android ${device.androidRelease ?? 'Unavailable'} · Storage ${formatBytes(device.storageFreeBytes)}',
            style: theme.textTheme.bodyMedium,
          ),
          if (_error != null) ...[
            const SizedBox(height: AppSpacing.lg),
            Text(_error!, style: theme.textTheme.bodySmall?.copyWith(color: AppColors.error)),
          ],
          const SizedBox(height: AppSpacing.xxl),
          PrimaryButton(label: _busy ? 'Creating…' : 'Create task & start judging', onPressed: _busy ? null : _create),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Relevance judging (blind, randomized)
// ---------------------------------------------------------------------------

class RelevanceJudgingScreen extends StatefulWidget {
  final String taskId;
  const RelevanceJudgingScreen({super.key, required this.taskId});

  @override
  State<RelevanceJudgingScreen> createState() => _RelevanceJudgingScreenState();
}

class _RelevanceJudgingScreenState extends State<RelevanceJudgingScreen> {
  EvaluationTask? _task;
  final Map<String, int> _grades = {};

  @override
  void initState() {
    super.initState();
    _prepare();
  }

  Future<void> _prepare() async {
    final repo = context.read<EvaluationRepository>();
    final task = repo.data.tasks.firstWhere((t) => t.taskId == widget.taskId);
    final ordered = await repo.ensurePresentationOrder(task);
    final existing = repo.data.labels.where((l) => l.taskId == task.taskId).toList()
      ..sort((a, b) => a.labeledAt.compareTo(b.labeledAt));
    if (!mounted) return;
    setState(() {
      _task = ordered;
      for (final l in existing) {
        _grades[l.packageName] = l.grade;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final task = _task;
    final theme = Theme.of(context);
    if (task == null) return const Scaffold(body: LoadingView());
    final snapshot = context.watch<EvaluationRepository>().data.snapshots.firstWhere((s) => s.snapshotId == task.snapshotId);
    final byPackage = {for (final a in snapshot.apps) (a['packageName'] ?? a['id']) as String: AppInfo.fromSmartAppJson(a)};
    final complete = task.candidateAppIds.every(_grades.containsKey);

    return Scaffold(
      appBar: AppBar(title: Text('Judge · ${task.participantId}')),
      body: ListView(
        padding: AppSpacing.pagePadding,
        children: [
          Text(
            'Rate how suitable each app is for this participant. Apps are in a random order and no SmartApp score is shown.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.lg),
          for (final id in task.presentationOrder)
            if (byPackage[id] != null)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.md),
                child: _JudgeCard(
                  app: byPackage[id]!,
                  grade: _grades[id],
                  onGrade: (g) => setState(() => _grades[id] = g),
                ),
              ),
          const SizedBox(height: AppSpacing.md),
          Text('${_grades.length} of ${task.candidateAppIds.length} rated', style: theme.textTheme.bodySmall),
          const SizedBox(height: AppSpacing.sm),
          PrimaryButton(
            label: complete ? 'Save labels' : 'Save progress',
            onPressed: _grades.isEmpty
                ? null
                : () async {
                    await context.read<EvaluationRepository>().saveLabels(task, Map.of(_grades));
                    if (context.mounted) Navigator.of(context).pop();
                  },
          ),
        ],
      ),
    );
  }
}

class _JudgeCard extends StatelessWidget {
  final AppInfo app;
  final int? grade;
  final ValueChanged<int> onGrade;
  const _JudgeCard({required this.app, required this.grade, required this.onGrade});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              AppIcon(iconUrl: app.iconUrl, iconKey: app.iconKey, size: 44),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(app.name, style: theme.textTheme.titleSmall),
                    Text(
                      [app.sourceCategory ?? 'Category not verified', if (app.developer != null) app.developer!].join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall,
                    ),
                    if (app.rating != null) RatingLabel(rating: app.rating),
                  ],
                ),
              ),
            ],
          ),
          if (app.description != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Text(app.description!, maxLines: 3, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall),
          ],
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: [
              for (var g = 0; g <= 3; g++)
                ChoiceChip(
                  label: Text('$g · ${RelevanceLabel.gradeNames[g]}'),
                  selected: grade == g,
                  onSelected: (_) => onGrade(g),
                ),
            ],
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Survey
// ---------------------------------------------------------------------------

class EvaluationSurveyScreen extends StatefulWidget {
  const EvaluationSurveyScreen({super.key});

  @override
  State<EvaluationSurveyScreen> createState() => _EvaluationSurveyScreenState();
}

class _EvaluationSurveyScreenState extends State<EvaluationSurveyScreen> {
  final _participant = TextEditingController();
  final Map<int, int> _answers = {};

  @override
  void dispose() {
    _participant.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final canSubmit = _participant.text.trim().isNotEmpty && _answers.isNotEmpty;
    return Scaffold(
      appBar: AppBar(title: const Text('Experience survey')),
      body: ListView(
        padding: AppSpacing.pagePadding,
        children: [
          Text('Optional. Stored only as evaluation data on this device.', style: theme.textTheme.bodySmall),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _participant,
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(labelText: 'Participant ID'),
          ),
          const SizedBox(height: AppSpacing.xl),
          for (var i = 0; i < SurveyResponse.statements.length; i++) ...[
            Text(SurveyResponse.statements[i], style: theme.textTheme.titleSmall),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.xs,
              runSpacing: AppSpacing.xs,
              children: [
                for (var score = 1; score <= 5; score++)
                  ChoiceChip(
                    label: Text('$score'),
                    tooltip: SurveyResponse.scaleLabels[score - 1],
                    selected: _answers[i] == score,
                    onSelected: (_) => setState(() => _answers[i] = score),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),
          ],
          Text('1 = Strongly disagree · 3 = Neutral · 5 = Strongly agree', style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0)),
          const SizedBox(height: AppSpacing.lg),
          PrimaryButton(
            label: 'Submit',
            onPressed: !canSubmit
                ? null
                : () async {
                    await context.read<EvaluationRepository>().saveSurvey(
                          SurveyResponse(participantId: _participant.text.trim(), answers: Map.of(_answers), submittedAt: DateTime.now()),
                        );
                    if (context.mounted) Navigator.of(context).pop();
                  },
          ),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Export / import
// ---------------------------------------------------------------------------

Future<void> showEvaluationExportSheet(BuildContext context) {
  final repo = context.read<EvaluationRepository>();
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (sheetContext) {
      final theme = Theme.of(sheetContext);
      Future<void> copy(String what, String text) async {
        await Clipboard.setData(ClipboardData(text: text));
        if (sheetContext.mounted) {
          ScaffoldMessenger.of(sheetContext).showSnackBar(SnackBar(content: Text('$what copied (${text.length} characters).')));
        }
      }

      final csv = repo.data.allCsv();
      return SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.fromLTRB(AppSpacing.xxl, 0, AppSpacing.xxl, AppSpacing.xxl),
          children: [
            Text('Export / import', style: theme.textTheme.titleLarge),
            const SizedBox(height: AppSpacing.sm),
            Text('Copies to the clipboard - paste into a .json / .csv file.', style: theme.textTheme.bodySmall),
            const SizedBox(height: AppSpacing.lg),
            SecondaryButton(label: 'Copy full dataset (JSON)', icon: Icons.data_object_rounded, onPressed: () => copy('JSON dataset', repo.data.toJsonString())),
            for (final entry in csv.entries) ...[
              const SizedBox(height: AppSpacing.sm),
              SecondaryButton(label: 'Copy ${entry.key}', icon: Icons.table_chart_outlined, onPressed: () => copy(entry.key, entry.value)),
            ],
            const SizedBox(height: AppSpacing.lg),
            PrimaryButton(
              label: 'Import JSON from clipboard',
              icon: Icons.download_rounded,
              onPressed: () async {
                final text = (await Clipboard.getData(Clipboard.kTextPlain))?.text;
                if (text == null || text.trim().isEmpty) return;
                try {
                  final dataset = EvaluationDataset.fromJsonString(text);
                  await repo.importDataset(dataset);
                  if (sheetContext.mounted) Navigator.of(sheetContext).pop();
                } on Object {
                  if (sheetContext.mounted) {
                    ScaffoldMessenger.of(sheetContext).showSnackBar(const SnackBar(content: Text('Clipboard does not contain a SmartApp evaluation export.')));
                  }
                }
              },
            ),
          ],
        ),
      );
    },
  );
}
