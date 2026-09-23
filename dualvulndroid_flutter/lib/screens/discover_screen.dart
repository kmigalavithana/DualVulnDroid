import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

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
import '../widgets/app_shell.dart';
import '../widgets/category_icons.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

/// Discover: live Google Play search, fetched via [AppRepository]
/// (SmartApp's own backend - never a hardcoded catalog, and never
/// SerpApi directly). Debounced as the user types, plus an explicit
/// submit. Categories open ranked results for that category; a search
/// shows the real matches (each with its calculated match for the user)
/// and "See your matches" hands them to the full Recommendation Results.
class DiscoverScreen extends StatefulWidget {
  const DiscoverScreen({super.key});

  @override
  State<DiscoverScreen> createState() => _DiscoverScreenState();
}

enum _Status { idle, loading, success, empty, error }

/// The categories offered as quick chips ("Other" is not a useful search).
final List<AppCategory> _chipCategories = AppCategory.values.where((c) => c != AppCategory.other).toList();

class _DiscoverScreenState extends State<DiscoverScreen> {
  static const _debounce = Duration(milliseconds: 450);

  final _controller = TextEditingController();
  Timer? _debounceTimer;
  int _requestId = 0;

  _Status _status = _Status.idle;
  List<AppInfo> _results = const [];
  String _lastQuery = '';

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _controller.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounceTimer?.cancel();
    setState(() {}); // refresh the clear button
    final trimmed = value.trim();
    if (trimmed.isEmpty) {
      setState(() {
        _status = _Status.idle;
        _results = const [];
      });
      return;
    }
    _debounceTimer = Timer(_debounce, () => _runSearch(trimmed));
  }

  Future<void> _runSearch(String query) async {
    final requestId = ++_requestId;
    setState(() {
      _status = _Status.loading;
      _lastQuery = query;
    });
    try {
      final results = await context.read<AppRepository>().searchApps(query: query, limit: 12);
      if (!mounted || requestId != _requestId) return;
      setState(() {
        _results = results;
        _status = results.isEmpty ? _Status.empty : _Status.success;
      });
    } catch (_) {
      if (!mounted || requestId != _requestId) return;
      setState(() => _status = _Status.error);
    }
  }

  void _submitSearch(String query) {
    final trimmed = query.trim();
    if (trimmed.isEmpty) return;
    _debounceTimer?.cancel();
    FocusScope.of(context).unfocus();
    _runSearch(trimmed);
  }

  void _clear() {
    _debounceTimer?.cancel();
    _requestId++;
    _controller.clear();
    setState(() {
      _status = _Status.idle;
      _results = const [];
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(leading: ShellScope.backButtonFor(context, ShellTab.discover), title: const Text('Discover')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        children: [
          TextField(
            controller: _controller,
            textInputAction: TextInputAction.search,
            onChanged: _onChanged,
            onSubmitted: _submitSearch,
            decoration: InputDecoration(
              hintText: 'Search apps',
              prefixIcon: const Icon(AppIcons.search),
              suffixIcon: _controller.text.isEmpty
                  ? null
                  : IconButton(tooltip: 'Clear search', icon: const Icon(AppIcons.clear), onPressed: _clear),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          SizedBox(
            height: 44,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: _chipCategories.length,
              separatorBuilder: (_, _) => const SizedBox(width: AppSpacing.sm),
              itemBuilder: (context, index) {
                final category = _chipCategories[index];
                return ActionChip(
                  avatar: Icon(resolveIconKey(category.iconKey), size: 18, color: AppColors.accent),
                  label: Text(category.label),
                  tooltip: 'Browse ${category.label} apps',
                  onPressed: () => AppRouter.toResultsForCategory(context, category),
                );
              },
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 200),
            child: KeyedSubtree(
              key: ValueKey(_status),
              child: switch (_status) {
                _Status.idle => const _IdleHint(),
                _Status.loading => const SkeletonList(count: 4, semanticLabel: 'Searching live Google Play apps'),
                _Status.error => ErrorStateView(
                    title: 'Unable to load live app data.',
                    message: 'Check your connection and try again.',
                    onRetry: () => _runSearch(_lastQuery),
                  ),
                _Status.empty => EmptyStateView(
                    icon: Icons.search_off_rounded,
                    title: 'No apps found',
                    message: 'Google Play returned no apps for "$_lastQuery". Try a different name or pick a category above.',
                  ),
                _Status.success => _SearchResults(query: _lastQuery, apps: _results, textTheme: theme.textTheme),
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _IdleHint extends StatelessWidget {
  const _IdleHint();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const IconBadge(icon: AppIcons.discover),
          const SizedBox(height: AppSpacing.md),
          Text('Search live Google Play apps', style: theme.textTheme.titleMedium),
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Type an app name, or pick a category above. Every result is ranked by how well it fits your preferences and your device.',
            style: theme.textTheme.bodySmall,
          ),
          const SizedBox(height: AppSpacing.md),
          const InfoPill(label: 'Live Google Play data', icon: AppIcons.liveData, color: AppColors.accentCyan),
        ],
      ),
    );
  }
}

class _SearchResults extends StatelessWidget {
  final String query;
  final List<AppInfo> apps;
  final TextTheme textTheme;
  const _SearchResults({required this.query, required this.apps, required this.textTheme});

  @override
  Widget build(BuildContext context) {
    final preferences = context.watch<PreferencesRepository>().preferences;
    final device = context.watch<DeviceProfileRepository>().profile;
    const engine = RecommendationEngine();
    final weights = EngineWeights.fromMap(preferences.weightOverrides);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(
          title: 'Results for "$query"',
          subtitle: '${apps.length} app${apps.length == 1 ? '' : 's'} from Google Play',
        ),
        SmartAppCard(
          onTap: () => AppRouter.toResultsForCandidates(context, apps, searchLabel: '"$query"'),
          color: AppColors.accentSoft,
          borderColor: AppColors.accent.withValues(alpha: 0.25),
          semanticLabel: 'See your matches: rank these apps for your preferences and device',
          child: Row(
            children: [
              const Icon(AppIcons.recommendations, color: AppColors.accent),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('See your matches', style: textTheme.titleSmall),
                    const SizedBox(height: 2),
                    Text('Rank these apps and see why each one fits', style: textTheme.bodySmall),
                  ],
                ),
              ),
              const Icon(AppIcons.chevron, color: AppColors.accent),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.md),
        for (final app in apps)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Builder(builder: (context) {
              final result = engine.score(app: app, preferences: preferences, device: device, weights: weights);
              return AppListCard(
                app: app,
                matchPercent: result.hasVerifiedFactors ? result.matchPercent : null,
                onTap: () => AppRouter.toAppDetail(context, app),
              );
            }),
          ),
      ],
    );
  }
}
