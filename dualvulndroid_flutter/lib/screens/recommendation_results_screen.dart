import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/app_info_model.dart';
import '../models/context_effect_model.dart';
import '../models/history_entry_model.dart';
import '../models/recommendation_result_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/app_repository.dart';
import '../repositories/device_profile_repository.dart';
import '../repositories/history_repository.dart';
import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../engines/recommendation_engine.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/app_result_card.dart';
import '../widgets/category_icons.dart';
import '../widgets/context_banner.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

/// "Your Matches". Ranks either every REAL app returned
/// for [category] (fetched live via [AppRepository] - SmartApp's backend,
/// which itself calls Google Play, Part 1/9) or an explicit [candidates]
/// list already fetched by the caller (Discover's search flow), against
/// the user's CURRENT preferences and device profile - always via the
/// shared [RecommendationEngine], never a screen-local re-implementation
/// of scoring, and never a hardcoded/fake app list (Part 7).
///
/// Records exactly one real HistoryEntry the first time real results are
/// computed (Part 14/16) - never on every rebuild.
class RecommendationResultsScreen extends StatefulWidget {
  final AppCategory? category;
  final List<AppInfo>? candidates;
  final String? searchLabel;

  const RecommendationResultsScreen({super.key, this.category, this.candidates, this.searchLabel})
      : assert(category != null || candidates != null, 'Either a category or a candidate list must be provided.');

  @override
  State<RecommendationResultsScreen> createState() => _RecommendationResultsScreenState();
}

enum _Status { loading, success, error }

class _RecommendationResultsScreenState extends State<RecommendationResultsScreen> {
  static const _historyTopN = 5;

  _Status _status = _Status.loading;
  List<RecommendationResult> _results = const [];
  List<ContextEffect> _contextEffects = const [];
  String _errorMessage = '';
  bool _historyRecorded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _load();
  }

  Future<void> _load() async {
    setState(() => _status = _Status.loading);

    List<AppInfo> candidates;
    if (widget.candidates != null) {
      candidates = widget.candidates!;
    } else {
      try {
        candidates = await context.read<AppRepository>().searchApps(category: widget.category!.label, limit: 25);
      } catch (_) {
        if (!mounted) return;
        setState(() {
          _status = _Status.error;
          _errorMessage = 'Unable to load live app data.';
        });
        return;
      }
    }

    if (!mounted) return;

    final preferences = context.read<PreferencesRepository>().preferences;
    final device = context.read<DeviceProfileRepository>().profile;
    const engine = RecommendationEngine();
    final weights = EngineWeights.fromMap(preferences.weightOverrides);
    final ranked = engine.rank(apps: candidates, preferences: preferences, device: device, weights: weights);
    final contextEffects = engine.contextEffectsFor(device);

    setState(() {
      _status = _Status.success;
      _results = ranked;
      _contextEffects = contextEffects;
    });

    if (!_historyRecorded) {
      _historyRecorded = true;
      context.read<HistoryRepository>().recordDiscovery(
            category: widget.category,
            preferences: preferences.selectedPreferences,
            resultCount: ranked.length,
            recommendedApps: ranked
                .take(_historyTopN)
                .map((r) => RecommendedAppEntry(
                      packageName: r.app.packageName ?? r.app.id,
                      name: r.app.name,
                      score: r.matchPercent,
                      dataSource: r.app.dataSource,
                      metadataCoverage: r.app.metadataCoverage,
                    ))
                .toList(),
            deviceContext: DeviceContextSummary.fromDevice(device),
          );
    }
  }

  @override
  Widget build(BuildContext context) {
    final title = widget.searchLabel ?? widget.category?.label ?? 'Results';
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Your Matches')),
      body: switch (_status) {
        _Status.loading => const Padding(
            padding: EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.lg, AppSpacing.page, 0),
            child: SkeletonList(semanticLabel: 'Finding real apps for you'),
          ),
        _Status.error => ErrorStateView(
            title: _errorMessage,
            message: 'Live Google Play data could not be reached. Check your connection and try again.',
            onRetry: _load,
          ),
        _Status.success => _results.isEmpty
            ? EmptyStateView(
                icon: Icons.search_off_rounded,
                title: 'No matches found',
                message: 'We couldn\'t find any apps for $title. Try a different category or search term.',
                actionLabel: 'Back to Discover',
                actionIcon: AppIcons.discover,
                onAction: () => AppRouter.toDiscover(context),
              )
            : ListView.builder(
                padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
                itemCount: _results.length + 1,
                itemBuilder: (context, index) {
                  if (index == 0) {
                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Based on your preferences and device.', style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary)),
                        const SizedBox(height: AppSpacing.md),
                        Wrap(
                          spacing: AppSpacing.sm,
                          runSpacing: AppSpacing.sm,
                          children: [
                            InfoPill(
                              label: '${_results.length} match${_results.length == 1 ? '' : 'es'} for $title',
                              icon: widget.category != null ? resolveIconKey(widget.category!.iconKey) : AppIcons.search,
                            ),
                            if (_results.any((r) => r.app.isLiveData))
                              const InfoPill(label: 'Live Google Play data', icon: AppIcons.liveData, color: AppColors.accentCyan),
                          ],
                        ),
                        const SizedBox(height: AppSpacing.lg),
                        if (_contextEffects.isNotEmpty) ...[
                          ContextBanner(effects: _contextEffects),
                          const SizedBox(height: AppSpacing.lg),
                        ],
                      ],
                    );
                  }
                  final result = _results[index - 1];
                  return Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.md),
                    child: AppResultCard(
                      result: result,
                      isBestMatch: index == 1,
                      onTap: () => AppRouter.toAppDetail(context, result.app),
                    ),
                  );
                },
              ),
      },
    );
  }
}
