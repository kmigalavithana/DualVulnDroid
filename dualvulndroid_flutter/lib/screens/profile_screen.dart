import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/recommendation_engine.dart';
import '../models/device_profile_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/device_profile_repository.dart';
import '../repositories/history_repository.dart';
import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/adaptive_suggestion_banner.dart';
import '../widgets/device_summary_card.dart';
import '../widgets/smartapp_ui.dart';
import 'history_screen.dart';

/// "Your Smart Profile": your preferences + your device context =
/// personalized app matching. Everything shown here is read from the real
/// saved preferences, the real device profile and the engine's real
/// weights - this screen only presents them. Toggling a preference uses
/// the same PreferencesRepository.togglePreference as before.
class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final prefsRepo = context.watch<PreferencesRepository>();
    final deviceRepo = context.watch<DeviceProfileRepository>();
    final preferences = prefsRepo.preferences;
    final selected = preferences.selectedPreferences;
    final device = deviceRepo.profile;

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.lg, AppSpacing.page, AppSpacing.section),
          children: [
            // 1. Header
            Semantics(header: true, child: Text('Your Smart Profile', style: theme.textTheme.displaySmall)),
            const SizedBox(height: AppSpacing.xs),
            Text('Your preferences and device context shape every app match.', style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary)),
            const SizedBox(height: AppSpacing.lg),
            // 2. Summary
            _ProfileSummary(
              selectedCount: selected.length,
              device: device,
              deviceLoading: deviceRepo.isLoading,
              hasCustomPriorities: preferences.weightOverrides != null,
            ),
            const SizedBox(height: AppSpacing.xl),
            const AdaptiveSuggestionBanner(),
            // 3. Preferences
            SectionHeader(
              title: 'Your Preferences',
              subtitle: 'These choices influence how apps are matched to you.',
              badge: InfoPill(label: '${selected.length} selected', color: selected.isEmpty ? AppColors.textSecondary : AppColors.accent),
            ),
            _GroupedPreferences(selected: selected, onToggle: prefsRepo.togglePreference),
            const SizedBox(height: AppSpacing.md),
            // 4. Insight
            _PreferenceInsight(selected: selected),
            const SizedBox(height: AppSpacing.md),
            // 5. How matching works
            _HowMatchingWorks(weights: EngineWeights.fromMap(preferences.weightOverrides), isCustom: preferences.weightOverrides != null),
            const SizedBox(height: AppSpacing.section),
            // 6. Device
            SectionHeader(
              title: 'Your Device',
              subtitle: 'Real values reported by your phone.',
              badge: const InfoPill(label: 'Device-aware', icon: AppIcons.device, color: AppColors.accentCyan),
              actionLabel: 'Details',
              onAction: () => AppRouter.toDeviceProfile(context),
            ),
            DeviceSummaryCard(
              profile: device,
              loading: deviceRepo.isLoading,
              showHeader: false,
              onTap: () => AppRouter.toDeviceProfile(context),
            ),
            if (_deviceStatus(device) != null) ...[
              const SizedBox(height: AppSpacing.sm),
              Align(alignment: Alignment.centerLeft, child: InfoPill(label: _deviceStatus(device)!, icon: AppIcons.performance)),
            ],
            const SizedBox(height: AppSpacing.section),
            // 7. What-If
            _WhatIfCard(onTap: () => AppRouter.toWhatIfSimulator(context)),
            const SizedBox(height: AppSpacing.section),
            // 8. More
            const SectionHeader(title: 'More'),
            SmartAppCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: [
                  NavigationRow(
                    icon: AppIcons.favorites,
                    title: 'Favorites',
                    subtitle: 'Apps you saved to compare later',
                    onTap: () => AppRouter.toFavorites(context),
                  ),
                  const _RowDivider(),
                  NavigationRow(
                    icon: AppIcons.installedApps,
                    title: 'Installed Apps',
                    subtitle: 'Find alternatives to apps on this phone',
                    onTap: () => AppRouter.toInstalledApps(context),
                  ),
                  const _RowDivider(),
                  NavigationRow(
                    icon: AppIcons.history,
                    title: 'History',
                    subtitle: 'Your past recommendations',
                    onTap: () => AppRouter.toHistory(context),
                  ),
                  const _RowDivider(),
                  NavigationRow(
                    icon: AppIcons.evaluation,
                    title: 'Evaluation',
                    subtitle: 'Ranking quality from your own feedback',
                    onTap: () => AppRouter.toEvaluation(context),
                  ),
                  const _RowDivider(),
                  NavigationRow(
                    icon: AppIcons.delete,
                    iconColor: AppColors.error,
                    title: 'Clear recommendation history',
                    subtitle: 'Remove local history from this device',
                    onTap: () => confirmClearHistory(context, context.read<HistoryRepository>()),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            Text(
              'SmartApp matches apps with a transparent scoring model that combines your preferences, your device, '
              'privacy, performance and rating. Everything stays on this device.',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  /// A friendly, derived label for the device's resource profile - only
  /// when the device actually reported enough to classify it.
  static String? _deviceStatus(DeviceProfileModel device) => switch (device.resourceProfileLabel) {
        'Constrained Resource Device' => 'Resource-constrained device',
        'Moderate Resource Device' => 'Mid-range device',
        'High-End Resource Device' => 'High-end device',
        _ => null,
      };
}

class _RowDivider extends StatelessWidget {
  const _RowDivider();

  @override
  Widget build(BuildContext context) => const Divider(indent: 70, endIndent: AppSpacing.lg);
}

/// "SMART PROFILE": three real facts about what drives the user's matches.
class _ProfileSummary extends StatelessWidget {
  final int selectedCount;
  final DeviceProfileModel device;
  final bool deviceLoading;
  final bool hasCustomPriorities;

  const _ProfileSummary({
    required this.selectedCount,
    required this.device,
    required this.deviceLoading,
    required this.hasCustomPriorities,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final deviceDetected = device.hasAnyData;
    final rows = <(IconData, String, Color)>[
      (
        AppIcons.preferences,
        selectedCount == 0 ? 'No preferences selected yet' : '$selectedCount preference${selectedCount == 1 ? '' : 's'} selected',
        selectedCount == 0 ? AppColors.textMuted : AppColors.accent,
      ),
      (
        AppIcons.device,
        deviceLoading ? 'Detecting your device…' : (deviceDetected ? 'Device profile detected' : 'Device profile unavailable'),
        deviceDetected ? AppColors.success : AppColors.textMuted,
      ),
      (
        AppIcons.recommendations,
        hasCustomPriorities ? 'Personalized matching · custom priorities' : 'Personalized matching enabled',
        AppColors.accentCyan,
      ),
    ];

    return SmartAppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const IconBadge(icon: AppIcons.profileFilled, size: 48),
          const SizedBox(width: AppSpacing.lg),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Overline('Smart profile'),
                const SizedBox(height: AppSpacing.xs),
                for (final (icon, text, color) in rows)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 3),
                    child: Row(
                      children: [
                        Icon(icon, size: 17, color: color),
                        const SizedBox(width: AppSpacing.sm),
                        Expanded(child: Text(text, style: theme.textTheme.bodyMedium)),
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Purely visual grouping of the existing [AppPreference] values - the
/// preference model and toggling are unchanged. Any value not listed in a
/// group still appears (under "Other"), so nothing can silently disappear.
class _GroupedPreferences extends StatelessWidget {
  final Set<AppPreference> selected;
  final ValueChanged<AppPreference> onToggle;

  const _GroupedPreferences({required this.selected, required this.onToggle});

  static const _groups = <(String, List<AppPreference>)>[
    ('App experience', [AppPreference.lightweight, AppPreference.lowStorageUsage, AppPreference.offlineSupport]),
    ('Trust & privacy', [AppPreference.privacyFriendly, AppPreference.noAds, AppPreference.openSource]),
    ('Access', [AppPreference.free]),
  ];

  @override
  Widget build(BuildContext context) {
    final grouped = _groups.expand((g) => g.$2).toSet();
    final others = AppPreference.values.where((p) => !grouped.contains(p)).toList();
    final groups = [..._groups, if (others.isNotEmpty) ('Other', others)];

    return SmartAppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var i = 0; i < groups.length; i++) ...[
            if (i > 0) const SizedBox(height: AppSpacing.lg),
            Overline(groups[i].$1),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                for (final preference in groups[i].$2)
                  PreferenceChip(
                    label: preference.label,
                    icon: AppIcons.forPreference(preference),
                    selected: selected.contains(preference),
                    onSelected: (_) => onToggle(preference),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// A one-sentence summary built only from the preferences actually selected.
class _PreferenceInsight extends StatelessWidget {
  final Set<AppPreference> selected;
  const _PreferenceInsight({required this.selected});

  static const _adjectives = {
    AppPreference.lightweight: 'lightweight',
    AppPreference.privacyFriendly: 'privacy-friendly',
    AppPreference.noAds: 'ad-free',
    AppPreference.offlineSupport: 'offline-capable',
    AppPreference.free: 'free',
    AppPreference.openSource: 'open-source',
    AppPreference.lowStorageUsage: 'storage-light',
  };

  static String _join(List<String> words) {
    if (words.length <= 1) return words.join();
    return '${words.sublist(0, words.length - 1).join(', ')} and ${words.last}';
  }

  static String messageFor(Set<AppPreference> selected) {
    if (selected.isEmpty) {
      return 'No preferences selected yet. Choose a few above and your matches will be personalized to them.';
    }
    // Keep the enum's own order so the sentence is stable.
    final ordered = AppPreference.values.where(selected.contains).toList();
    final experience = {AppPreference.lightweight, AppPreference.lowStorageUsage, AppPreference.offlineSupport};
    final trust = {AppPreference.privacyFriendly, AppPreference.noAds, AppPreference.openSource};
    if (selected.containsAll(experience) && selected.containsAll(trust)) {
      final free = selected.contains(AppPreference.free) ? ', free' : '';
      return 'Your profile strongly favors lightweight, private$free apps that also work offline.';
    }
    final shown = ordered.take(3).map((p) => _adjectives[p]!).toList();
    final extra = ordered.length - shown.length;
    final more = extra > 0 ? ', plus $extra more preference${extra == 1 ? '' : 's'}' : '';
    return 'Your profile prioritizes ${_join(shown)} apps$more.';
  }

  @override
  Widget build(BuildContext context) {
    return InsightBanner(
      title: 'Smart insight',
      icon: AppIcons.recommendations,
      messages: [messageFor(selected)],
      footer: const InfoPill(label: 'Based on your profile', icon: AppIcons.profile),
    );
  }
}

/// Expandable, plain-language explanation of the real weights the engine
/// uses for this user (defaults, or the priorities saved from What-If).
class _HowMatchingWorks extends StatelessWidget {
  final EngineWeights weights;
  final bool isCustom;
  const _HowMatchingWorks({required this.weights, required this.isCustom});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final factors = <(IconData, String, double)>[
      (AppIcons.preferences, 'Preferences', weights.preference),
      (AppIcons.device, 'Device', weights.device),
      (AppIcons.privacy, 'Privacy', weights.privacy),
      (AppIcons.performance, 'Performance', weights.resource),
      (AppIcons.rating, 'Rating', weights.rating),
    ];
    return SmartAppCard(
      padding: EdgeInsets.zero,
      child: Theme(
        data: theme.copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          tilePadding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.xxs),
          childrenPadding: const EdgeInsets.fromLTRB(AppSpacing.lg, 0, AppSpacing.lg, AppSpacing.lg),
          iconColor: AppColors.textSecondary,
          collapsedIconColor: AppColors.textSecondary,
          leading: const IconBadge(icon: AppIcons.evaluation, color: AppColors.textSecondary, size: 38),
          title: Text('How your matches are calculated', style: theme.textTheme.titleSmall),
          subtitle: Text(isCustom ? 'Using your saved What-If priorities' : 'Five factors make up your match score', style: theme.textTheme.bodySmall),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final (icon, label, weight) in factors)
              Semantics(
                label: '$label: ${(weight * 100).round()} percent of your match score',
                excludeSemantics: true,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: AppSpacing.md),
                  child: Row(
                    children: [
                      Icon(icon, size: 18, color: AppColors.textSecondary),
                      const SizedBox(width: AppSpacing.sm),
                      SizedBox(width: 104, child: Text(label, style: theme.textTheme.bodyMedium)),
                      Expanded(
                        child: ClipRRect(
                          borderRadius: AppRadius.pillAll,
                          child: LinearProgressIndicator(value: weight, minHeight: 6),
                        ),
                      ),
                      SizedBox(
                        width: 48,
                        child: Text('${(weight * 100).round()}%', textAlign: TextAlign.end, style: theme.textTheme.titleSmall),
                      ),
                    ],
                  ),
                ),
              ),
            Text(
              'These factors combine into your match score - an estimate of how well an app fits your current profile and device. '
              'It is not a rating of the app\'s overall quality. When a factor can\'t be verified for an app, it is left out and '
              'its weight is shared by the verified factors, so unknown data never counts for or against an app.',
              style: theme.textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _WhatIfCard extends StatelessWidget {
  final VoidCallback onTap;
  const _WhatIfCard({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      onTap: onTap,
      semanticLabel: 'Explore What-If. See how changing your priorities changes your matches',
      child: Row(
        children: [
          const IconBadge(icon: AppIcons.whatIf, size: 44),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Overline('Explore What-If'),
                const SizedBox(height: AppSpacing.xxs),
                Text('See how changing your priorities changes your matches.', style: theme.textTheme.bodyMedium),
                const SizedBox(height: AppSpacing.sm),
                const InfoPill(label: 'Try different priorities', icon: AppIcons.whatIf, color: AppColors.accent),
              ],
            ),
          ),
          const Icon(AppIcons.chevron, color: AppColors.textMuted),
        ],
      ),
    );
  }
}
