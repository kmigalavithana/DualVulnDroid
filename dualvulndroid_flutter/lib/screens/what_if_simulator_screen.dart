import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/constraint_engine.dart';
import '../engines/recommendation_engine.dart';
import '../models/app_info_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/app_repository.dart';
import '../repositories/device_profile_repository.dart';
import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/app_result_card.dart';
import '../widgets/category_icons.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

/// Explore What-If: temporarily change scoring priorities and/or hard
/// constraints and see LIVE Google Play results for a category re-rank
/// immediately, with the same availability-aware scoring as everywhere
/// else. Nothing is saved automatically - only "Apply to Profile" persists
/// the priorities; "Reset" just returns the sliders/constraints to their
/// defaults. A constraint whose data isn't verified for an app never
/// removes it - the card shows "Not verified" instead.
class WhatIfSimulatorScreen extends StatefulWidget {
  const WhatIfSimulatorScreen({super.key});

  @override
  State<WhatIfSimulatorScreen> createState() => _WhatIfSimulatorScreenState();
}

class _WhatIfSimulatorScreenState extends State<WhatIfSimulatorScreen> {
  PriorityLevel _preference = PriorityLevel.medium;
  PriorityLevel _device = PriorityLevel.medium;
  PriorityLevel _privacy = PriorityLevel.medium;
  PriorityLevel _resource = PriorityLevel.medium;
  PriorityLevel _rating = PriorityLevel.medium;

  bool _freeOnly = false;
  bool _offlineRequired = false;
  bool _noTrackers = false;
  bool _noAds = false;
  bool _openSourceOnly = false;
  bool _lowStorage = false;

  AppCategory? _category;
  List<AppInfo>? _liveApps;
  bool _loading = false;
  bool _failed = false;
  int _requestId = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_category == null) {
      _category = context.read<PreferencesRepository>().preferences.selectedCategory ?? AppCategory.productivity;
      _load();
    }
  }

  Future<void> _load() async {
    final category = _category!;
    final requestId = ++_requestId;
    setState(() {
      _loading = true;
      _failed = false;
    });
    try {
      final apps = await context.read<AppRepository>().searchApps(category: category.label, limit: 25);
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _liveApps = apps;
        _loading = false;
      });
    } catch (_) {
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _loading = false;
        _failed = true;
      });
    }
  }

  bool get _isModified =>
      _preference != PriorityLevel.medium ||
      _device != PriorityLevel.medium ||
      _privacy != PriorityLevel.medium ||
      _resource != PriorityLevel.medium ||
      _rating != PriorityLevel.medium ||
      _freeOnly ||
      _offlineRequired ||
      _noTrackers ||
      _noAds ||
      _openSourceOnly ||
      _lowStorage;

  void _reset() => setState(() {
        _preference = _device = _privacy = _resource = _rating = PriorityLevel.medium;
        _freeOnly = _offlineRequired = _noTrackers = _noAds = _openSourceOnly = _lowStorage = false;
      });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final prefsRepo = context.watch<PreferencesRepository>();
    final preferences = prefsRepo.preferences;
    final device = context.watch<DeviceProfileRepository>().profile;
    const engine = RecommendationEngine();

    final weights = EngineWeightsPriorities.fromPriorities(
      preference: _preference,
      device: _device,
      privacy: _privacy,
      resource: _resource,
      rating: _rating,
    );
    final constraints = HardConstraints(
      freeOnly: _freeOnly,
      offlineRequired: _offlineRequired,
      noTrackers: _noTrackers,
      noAds: _noAds,
      openSourceOnly: _openSourceOnly,
      maxSizeMb: _lowStorage ? 30 : null,
    );
    final live = _liveApps ?? const <AppInfo>[];
    final eligible = engine.rank(apps: live, preferences: preferences, device: device, weights: weights, constraints: constraints);
    final ranked = eligible.take(10).toList();
    final excluded = live.length - eligible.length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('What-If'),
        actions: [
          if (preferences.weightOverrides != null)
            PopupMenuButton<String>(
              tooltip: 'More options',
              onSelected: (_) {
                prefsRepo.clearWeightOverrides();
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Saved priorities cleared - back to defaults.')),
                );
              },
              itemBuilder: (_) => const [PopupMenuItem(value: 'clear', child: Text('Clear saved priorities'))],
            ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.xl),
              children: [
                Semantics(header: true, child: Text('Explore What-If', style: theme.textTheme.headlineSmall)),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'See how changing priorities changes your recommendations. Nothing is saved unless you tap "Apply to Profile".',
                  style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: AppSpacing.xl),
                SmartAppCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Overline('How much each factor matters'),
                      const SizedBox(height: AppSpacing.sm),
                      _PrioritySlider(label: 'Preferences', icon: AppIcons.preferences, value: _preference, onChanged: (v) => setState(() => _preference = v)),
                      _PrioritySlider(label: 'Device', icon: AppIcons.device, value: _device, onChanged: (v) => setState(() => _device = v)),
                      _PrioritySlider(label: 'Privacy', icon: AppIcons.privacy, value: _privacy, onChanged: (v) => setState(() => _privacy = v)),
                      _PrioritySlider(label: 'Performance', icon: AppIcons.performance, value: _resource, onChanged: (v) => setState(() => _resource = v)),
                      _PrioritySlider(label: 'Rating', icon: AppIcons.rating, value: _rating, onChanged: (v) => setState(() => _rating = v)),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                SmartAppCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Overline('Hard constraints'),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        'Apps that verifiably fail a constraint are left out. When the data isn\'t verified, the app stays and is marked "Not verified". For exploring only - not saved.',
                        style: theme.textTheme.bodySmall,
                      ),
                      const SizedBox(height: AppSpacing.md),
                      Wrap(
                        spacing: AppSpacing.sm,
                        runSpacing: AppSpacing.sm,
                        children: [
                          PreferenceChip(label: 'Free only', icon: Icons.money_off_rounded, selected: _freeOnly, onSelected: (v) => setState(() => _freeOnly = v)),
                          PreferenceChip(label: 'Works offline', icon: AppIcons.offline, selected: _offlineRequired, onSelected: (v) => setState(() => _offlineRequired = v)),
                          PreferenceChip(label: 'No trackers', icon: AppIcons.privacy, selected: _noTrackers, onSelected: (v) => setState(() => _noTrackers = v)),
                          PreferenceChip(label: 'No ads', icon: Icons.block_rounded, selected: _noAds, onSelected: (v) => setState(() => _noAds = v)),
                          PreferenceChip(label: 'Open source', icon: Icons.code_rounded, selected: _openSourceOnly, onSelected: (v) => setState(() => _openSourceOnly = v)),
                          PreferenceChip(label: 'Low storage (≤30 MB)', icon: AppIcons.storage, selected: _lowStorage, onSelected: (v) => setState(() => _lowStorage = v)),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.section),
                SectionHeader(
                  title: 'Updated matches',
                  subtitle: _isModified ? 'Recalculated with your changed priorities.' : 'Using default priorities.',
                ),
                SizedBox(
                  height: 44,
                  child: ListView.separated(
                    scrollDirection: Axis.horizontal,
                    itemCount: AppCategory.values.length - 1,
                    separatorBuilder: (_, _) => const SizedBox(width: AppSpacing.sm),
                    itemBuilder: (context, index) {
                      final category = AppCategory.values.where((c) => c != AppCategory.other).elementAt(index);
                      return ChoiceChip(
                        avatar: Icon(resolveIconKey(category.iconKey), size: 18, color: category == _category ? AppColors.accent : AppColors.textSecondary),
                        label: Text(category.label),
                        selected: category == _category,
                        onSelected: (_) {
                          if (category == _category) return;
                          setState(() => _category = category);
                          _load();
                        },
                      );
                    },
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                if (_liveApps != null && !_loading && !_failed)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.md),
                    child: Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.sm,
                      children: [
                        const InfoPill(label: 'Live Google Play data', icon: AppIcons.liveData, color: AppColors.accentCyan),
                        if (excluded > 0) InfoPill(label: '$excluded excluded by a verified constraint', icon: Icons.filter_alt_outlined),
                      ],
                    ),
                  ),
                if (_loading)
                  const SkeletonList(count: 3, semanticLabel: 'Loading live apps')
                else if (_failed)
                  ErrorStateView(
                    title: 'Unable to load live app data.',
                    message: 'Check your connection and try again.',
                    onRetry: _load,
                  )
                else if (ranked.isEmpty)
                  EmptyStateView(
                    icon: Icons.filter_alt_off_outlined,
                    title: live.isEmpty ? 'No live apps found' : 'No apps pass these constraints',
                    message: live.isEmpty
                        ? 'Google Play returned no apps for ${_category!.label}.'
                        : 'Every app verifiably fails an enabled constraint. Turn one off to see matches again.',
                  )
                else
                  for (final result in ranked)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.md),
                      child: AppResultCard(
                        result: result,
                        isBestMatch: result == ranked.first,
                        onTap: () => AppRouter.toAppDetail(context, result.app),
                      ),
                    ),
              ],
            ),
          ),
          Container(
            decoration: const BoxDecoration(
              color: AppColors.surface,
              border: Border(top: BorderSide(color: AppColors.border)),
            ),
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.md, AppSpacing.page, AppSpacing.md),
                child: Row(
                  children: [
                    Expanded(child: SecondaryButton(label: 'Reset', icon: AppIcons.refresh, onPressed: _isModified ? _reset : null)),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      flex: 2,
                      child: PrimaryButton(
                        label: 'Apply to Profile',
                        onPressed: !_isModified
                            ? null
                            : () {
                                prefsRepo.setWeightOverrides(weights.toMap());
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(content: Text('Priorities applied to your profile.')),
                                );
                              },
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// A three-step slider (Low / Medium / High) over the engine's existing
/// [PriorityLevel]s - the underlying weighting logic is unchanged.
class _PrioritySlider extends StatelessWidget {
  final String label;
  final IconData icon;
  final PriorityLevel value;
  final ValueChanged<PriorityLevel> onChanged;

  const _PrioritySlider({required this.label, required this.icon, required this.value, required this.onChanged});

  static const _levels = [PriorityLevel.low, PriorityLevel.medium, PriorityLevel.high];
  static const _names = ['Low', 'Medium', 'High'];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final index = _levels.indexOf(value);
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.sm),
      child: Column(
        children: [
          Row(
            children: [
              Icon(icon, size: 18, color: AppColors.textSecondary),
              const SizedBox(width: AppSpacing.sm),
              Expanded(child: Text(label, style: theme.textTheme.titleSmall)),
              Text(
                _names[index],
                style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13, color: index == 1 ? AppColors.textSecondary : AppColors.accent),
              ),
            ],
          ),
          Slider(
            value: index.toDouble(),
            min: 0,
            max: 2,
            divisions: 2,
            label: _names[index],
            semanticFormatterCallback: (v) => '$label priority ${_names[v.round()]}',
            onChanged: (v) => onChanged(_levels[v.round()]),
          ),
        ],
      ),
    );
  }
}
