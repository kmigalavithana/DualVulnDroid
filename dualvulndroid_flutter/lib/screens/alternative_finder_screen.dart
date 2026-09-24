import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/recommendation_engine.dart';
import '../models/app_info_model.dart';
import '../models/recommendation_result_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/app_repository.dart';
import '../repositories/device_profile_repository.dart';
import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/app_icon.dart';
import '../widgets/app_result_card.dart';
import '../widgets/category_icons.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

enum _Status { idle, loading, success, error }

/// "Find Better Matches". The user picks a current app (or, if none is
/// identified, a category) and gets REAL Google Play apps in that
/// category - fetched live via [AppRepository], never a local catalog -
/// ranked by the existing [RecommendationEngine]. With a current app, each
/// alternative is compared against it using only calculated scores and
/// verified attributes. Always phrased as a better match for THIS user,
/// never as an objective "best app" claim.
class AlternativeFinderScreen extends StatefulWidget {
  final AppInfo? initialApp;
  final String? initialAppName;

  const AlternativeFinderScreen({super.key, this.initialApp, this.initialAppName});

  @override
  State<AlternativeFinderScreen> createState() => _AlternativeFinderScreenState();
}

class _AlternativeFinderScreenState extends State<AlternativeFinderScreen> {
  AppInfo? _currentApp;
  AppCategory? _fallbackCategory;
  bool _started = false;

  _Status _status = _Status.idle;
  List<RecommendationResult> _alternatives = const [];

  @override
  void initState() {
    super.initState();
    _currentApp = widget.initialApp;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (_currentApp != null) {
      _search();
    } else if (widget.initialAppName != null) {
      _resolveInitialAppByName(widget.initialAppName!);
    }
  }

  /// Installed Apps only has a real app NAME (from PackageManager), not a
  /// package/category - a best-effort live search by that name is the only
  /// honest way to find its real category, never a guess.
  Future<void> _resolveInitialAppByName(String name) async {
    setState(() => _status = _Status.loading);
    try {
      final results = await context.read<AppRepository>().searchApps(query: name, limit: 5);
      if (!mounted) return;
      final match = results.where((a) => a.name.toLowerCase() == name.toLowerCase()).firstOrNull ?? results.firstOrNull;
      setState(() {
        _currentApp = match;
        _status = _Status.idle;
      });
      if (match != null) _search();
    } catch (_) {
      if (mounted) setState(() => _status = _Status.idle);
    }
  }

  /// The category the alternatives are searched in: the current app's
  /// SmartApp category when it maps to one, otherwise the exact category
  /// Google Play returned for it, otherwise the existing fallback (the
  /// mapped value) - or the category the user picked when there is no
  /// current app.
  String? get _searchCategory {
    final app = _currentApp;
    if (app == null) return _fallbackCategory?.label;
    if (app.category != AppCategory.other) return app.category.label;
    return app.sourceCategory ?? app.category.label;
  }

  Future<void> _search() async {
    final category = _searchCategory;
    if (category == null) {
      setState(() => _status = _Status.idle);
      return;
    }
    setState(() => _status = _Status.loading);
    try {
      final results = await context.read<AppRepository>().searchApps(category: category, limit: 25);
      if (!mounted) return;
      final currentPackage = _currentApp?.packageName;
      final candidates = currentPackage == null ? results : results.where((a) => a.packageName != currentPackage).toList();

      final preferences = context.read<PreferencesRepository>().preferences;
      final device = context.read<DeviceProfileRepository>().profile;
      const engine = RecommendationEngine();
      final weights = EngineWeights.fromMap(preferences.weightOverrides);
      final ranked = engine.rank(apps: candidates, preferences: preferences, device: device, weights: weights);

      setState(() {
        _status = _Status.success;
        _alternatives = ranked;
      });
    } catch (_) {
      if (mounted) setState(() => _status = _Status.error);
    }
  }

  void _changeApp() => setState(() {
        _currentApp = null;
        _status = _Status.idle;
        _alternatives = const [];
      });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final currentApp = _currentApp;
    RecommendationResult? currentResult;
    if (currentApp != null) {
      final preferences = context.watch<PreferencesRepository>().preferences;
      final device = context.watch<DeviceProfileRepository>().profile;
      currentResult = const RecommendationEngine().score(
        app: currentApp,
        preferences: preferences,
        device: device,
        weights: EngineWeights.fromMap(preferences.weightOverrides),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Alternatives')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
        children: [
          Semantics(header: true, child: Text('Find Better Matches', style: theme.textTheme.headlineSmall)),
          const SizedBox(height: AppSpacing.xs),
          Text('Explore apps that may fit your preferences and device better.', style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary)),
          const SizedBox(height: AppSpacing.xl),
          if (currentApp != null && currentResult != null)
            _CurrentAppCard(app: currentApp, result: currentResult, onChange: _changeApp, categoryLabel: verifiedCategoryLabel(currentApp))
          else
            _CategoryPicker(
              selected: _fallbackCategory,
              onSelected: (category) {
                setState(() => _fallbackCategory = category);
                _search();
              },
            ),
          if (currentApp != null && _status != _Status.idle) ...[
            const SizedBox(height: AppSpacing.md),
            const Row(
              children: [
                Expanded(child: Divider()),
                Padding(
                  padding: EdgeInsets.symmetric(horizontal: AppSpacing.md),
                  child: Overline('versus'),
                ),
                Expanded(child: Divider()),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
          ] else
            const SizedBox(height: AppSpacing.xl),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 200),
            child: KeyedSubtree(
              key: ValueKey(_status),
              child: switch (_status) {
                _Status.idle => const EmptyStateView(
                    icon: AppIcons.alternatives,
                    title: 'Pick a category',
                    message: 'Choose a category above, or open an app\'s details and tap "Find Alternatives" to compare a specific app.',
                  ),
                _Status.loading => const SkeletonList(count: 4, semanticLabel: 'Finding alternatives'),
                _Status.error => ErrorStateView(
                    title: 'Unable to load live app data.',
                    message: 'Check your connection and try again.',
                    onRetry: _search,
                  ),
                _Status.success => _alternatives.isEmpty
                    ? const EmptyStateView(
                        icon: Icons.search_off_rounded,
                        title: 'No alternatives found',
                        message: 'Google Play returned no other apps in this category.',
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SectionHeader(
                            title: '${_alternatives.length} alternative${_alternatives.length == 1 ? '' : 's'}',
                            subtitle: currentApp != null && verifiedCategoryLabel(currentApp) != null
                                ? 'Real Google Play apps in ${verifiedCategoryLabel(currentApp)}, ranked by how well they match you - not a claim that any app is objectively the best.'
                                : 'Ranked by how well they match you - not a claim that any app is objectively the best.',
                          ),
                          for (final result in _alternatives)
                            Padding(
                              padding: const EdgeInsets.only(bottom: AppSpacing.md),
                              child: AppResultCard(
                                result: result,
                                isBestMatch: result == _alternatives.first,
                                highlights: currentResult == null ? const [] : comparisonReasons(current: currentResult, alternative: result),
                                onTap: () => AppRouter.toAppDetail(context, result.app),
                              ),
                            ),
                        ],
                      ),
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// Why an alternative appears, compared with the current app - derived
/// only from calculated scores and attributes the data source verified.
List<String> comparisonReasons({required RecommendationResult current, required RecommendationResult alternative}) {
  final reasons = <String>[];
  if (alternative.matchPercent > current.matchPercent) reasons.add('Better overall match');
  if (alternative.preferenceScore > current.preferenceScore + 0.5) reasons.add('Better preference match');
  if (alternative.deviceScore > current.deviceScore + 0.5) reasons.add('Better fit for your device');
  final altLevel = alternative.app.resourceLevel;
  final curLevel = current.app.resourceLevel;
  if (altLevel != null && curLevel != null && altLevel.index < curLevel.index) reasons.add('Lower resource requirement');
  if (alternative.app.trackerCount != null && current.app.trackerCount == null) reasons.add('More privacy information available');
  final altRating = alternative.app.rating;
  final curRating = current.app.rating;
  if (altRating != null && curRating != null && altRating > curRating) reasons.add('Higher rating');
  return reasons;
}

/// The category to show for [app]: exactly what the live source returned,
/// or - for curated demo data only - its curated category. `null` means no
/// source verified one, and the UI says "Category not verified" rather
/// than showing SmartApp's internal "Other" fallback as if it were real.
String? verifiedCategoryLabel(AppInfo app) {
  final source = app.sourceCategory;
  if (source != null) return source;
  if (app.isCuratedSample) return app.category.label;
  return null;
}

/// Compact "Alternatives for [app] + category chip" context at the top.
class _CurrentAppCard extends StatelessWidget {
  final AppInfo app;
  final RecommendationResult result;
  final VoidCallback onChange;
  final String? categoryLabel;
  const _CurrentAppCard({required this.app, required this.result, required this.onChange, required this.categoryLabel});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final category = categoryLabel;
    return SmartAppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(child: Overline('Alternatives for')),
              TextButton.icon(onPressed: onChange, icon: const Icon(Icons.edit_outlined, size: 18), label: const Text('Change')),
            ],
          ),
          Row(
            children: [
              AppIcon(iconUrl: app.iconUrl, iconKey: app.iconKey, size: 48),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(app.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleMedium),
                    if (app.rating != null) ...[
                      const SizedBox(height: AppSpacing.xxs),
                      RatingLabel(rating: app.rating),
                    ],
                  ],
                ),
              ),
              if (result.hasVerifiedFactors) MatchIndicator(percent: result.matchPercent),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              Text('Category', style: theme.textTheme.bodySmall),
              const SizedBox(width: AppSpacing.sm),
              Flexible(
                child: Semantics(
                  label: category == null ? 'Category not verified' : 'Category: $category',
                  excludeSemantics: true,
                  child: category == null
                      ? const InfoPill(label: 'Not verified', icon: Icons.help_outline_rounded)
                      : InfoPill(
                          label: category,
                          icon: resolveIconKey(app.category.iconKey),
                          color: AppColors.accent,
                        ),
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            category == null
                ? 'Google Play didn\'t return a category for this app, so alternatives use SmartApp\'s general fallback search.'
                : 'Real alternatives based on this category and your current profile.',
            style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0, height: 1.4),
          ),
        ],
      ),
    );
  }
}

class _CategoryPicker extends StatelessWidget {
  final AppCategory? selected;
  final ValueChanged<AppCategory> onSelected;
  const _CategoryPicker({required this.selected, required this.onSelected});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SectionHeader(title: 'Choose a category'),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            for (final category in AppCategory.values.where((c) => c != AppCategory.other))
              ChoiceChip(
                avatar: Icon(resolveIconKey(category.iconKey), size: 18, color: selected == category ? AppColors.accent : AppColors.textSecondary),
                label: Text(category.label),
                selected: selected == category,
                onSelected: (_) => onSelected(category),
              ),
          ],
        ),
      ],
    );
  }
}
