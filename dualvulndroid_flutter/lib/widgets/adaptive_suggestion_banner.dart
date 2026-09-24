import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/adaptive_suggestion_engine.dart';
import '../models/app_info_model.dart';
import '../repositories/app_interaction_repository.dart';
import '../repositories/apps_repository.dart';
import '../repositories/favorites_repository.dart';
import '../repositories/preferences_repository.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import 'smartapp_ui.dart';

/// Surfaces one real, calculated [AdaptiveSuggestion] derived from the
/// user's own recorded behavior - shown only when a strong pattern
/// actually exists. It never changes the saved profile by itself: "Review
/// suggestion" explains it and the user must explicitly confirm; "Ignore"
/// changes nothing (the suggestion simply reappears next time the pattern
/// is still there).
///
/// Only favorited/opened apps that resolve to a known local catalog entry
/// contribute a signal - a real Google Play app's trackerCount/
/// resourceLevel/etc. are unverified (null), so it can never honestly
/// satisfy() a preference, and is correctly excluded rather than guessed at.
class AdaptiveSuggestionBanner extends StatefulWidget {
  const AdaptiveSuggestionBanner({super.key});

  @override
  State<AdaptiveSuggestionBanner> createState() => _AdaptiveSuggestionBannerState();
}

class _AdaptiveSuggestionBannerState extends State<AdaptiveSuggestionBanner> {
  static const _engine = AdaptiveSuggestionEngine();
  bool _dismissed = false;

  @override
  Widget build(BuildContext context) {
    final favorites = context.watch<FavoritesRepository>().favorites;
    final opens = context.watch<AppInteractionRepository>().events;
    final apps = context.watch<AppsRepository>();
    final prefsRepo = context.watch<PreferencesRepository>();

    final likedIds = <String>{
      ...favorites.map((s) => s.packageName),
      ...opens.map((e) => e.appId),
    };
    final likedApps = likedIds.map(apps.byIdOrPackageName).whereType<AppInfo>().toList();

    final suggestion = _engine.suggest(
      likedApps: likedApps,
      currentPreferences: prefsRepo.preferences.selectedPreferences,
    );

    if (suggestion == null || _dismissed) return const SizedBox.shrink();

    final label = suggestion.suggestedPreference.label.toLowerCase();
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xl),
      child: InsightBanner(
        title: 'A suggestion from your activity',
        icon: AppIcons.recommendations,
        color: AppColors.accent,
        messages: ['Your recent choices suggest you may prefer $label apps.'],
        footer: Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            FilledButton(onPressed: () => _review(context, suggestion, prefsRepo), child: const Text('Review Suggestion')),
            TextButton(onPressed: () => setState(() => _dismissed = true), child: const Text('Ignore')),
          ],
        ),
      ),
    );
  }

  Future<void> _review(BuildContext context, AdaptiveSuggestion suggestion, PreferencesRepository prefsRepo) async {
    final preference = suggestion.suggestedPreference;
    final percent = (suggestion.confidence * 100).round();
    final apply = await showModalBottomSheet<bool>(
      context: context,
      builder: (sheetContext) {
        final theme = Theme.of(sheetContext);
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(AppSpacing.xxl, 0, AppSpacing.xxl, AppSpacing.xxl),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    IconBadge(icon: AppIcons.forPreference(preference)),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(child: Text('Prioritize ${preference.label}?', style: theme.textTheme.titleLarge)),
                  ],
                ),
                const SizedBox(height: AppSpacing.lg),
                Text(
                  '$percent% of the apps you recently saved or opened are ${preference.label.toLowerCase()} '
                  '(${preference.description.toLowerCase()}).',
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  'Adding it to your preferences changes how future matches are ranked. '
                  'You can remove it any time from Profile.',
                  style: theme.textTheme.bodySmall,
                ),
                const SizedBox(height: AppSpacing.xxl),
                PrimaryButton(label: 'Add to my preferences', onPressed: () => Navigator.pop(sheetContext, true)),
                const SizedBox(height: AppSpacing.sm),
                SecondaryButton(label: 'Not now', onPressed: () => Navigator.pop(sheetContext, false)),
              ],
            ),
          ),
        );
      },
    );
    if (apply == true && mounted) {
      await prefsRepo.setPreferences({...prefsRepo.preferences.selectedPreferences, preference});
      if (!context.mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('${preference.label} added to your preferences.')));
    }
  }
}
