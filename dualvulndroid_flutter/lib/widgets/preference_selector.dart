import 'package:flutter/material.dart';

import '../models/user_preferences_model.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import 'smartapp_ui.dart';

/// Multi-select of [AppPreference]s - onboarding and Profile. Purely
/// presentational: [selected]/[onToggle] are owned by the caller
/// (PreferencesRepository), so this widget has no persistence of its own.
///
/// [compact] renders icon chips (Profile); otherwise each preference is a
/// selectable row with its description (onboarding).
class PreferenceSelector extends StatelessWidget {
  final Set<AppPreference> selected;
  final ValueChanged<AppPreference> onToggle;
  final bool compact;

  const PreferenceSelector({super.key, required this.selected, required this.onToggle, this.compact = false});

  @override
  Widget build(BuildContext context) {
    if (compact) {
      return Wrap(
        spacing: AppSpacing.sm,
        runSpacing: AppSpacing.sm,
        children: [
          for (final preference in AppPreference.values)
            PreferenceChip(
              label: preference.label,
              icon: AppIcons.forPreference(preference),
              selected: selected.contains(preference),
              onSelected: (_) => onToggle(preference),
            ),
        ],
      );
    }

    final theme = Theme.of(context);
    return Column(
      children: [
        for (final preference in AppPreference.values)
          Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.sm),
            child: Builder(builder: (context) {
              final isSelected = selected.contains(preference);
              return Semantics(
                checked: isSelected,
                child: SmartAppCard(
                  onTap: () => onToggle(preference),
                  color: isSelected ? AppColors.accentSoft : null,
                  borderColor: isSelected ? AppColors.accent.withValues(alpha: 0.7) : null,
                  padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.md),
                  child: Row(
                    children: [
                      IconBadge(icon: AppIcons.forPreference(preference), color: isSelected ? AppColors.accent : AppColors.textSecondary, size: 38),
                      const SizedBox(width: AppSpacing.md),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(preference.label, style: theme.textTheme.titleSmall),
                            const SizedBox(height: 2),
                            Text(preference.description, style: theme.textTheme.bodySmall),
                          ],
                        ),
                      ),
                      Icon(
                        isSelected ? Icons.check_circle_rounded : Icons.radio_button_unchecked_rounded,
                        color: isSelected ? AppColors.accent : AppColors.textMuted,
                      ),
                    ],
                  ),
                ),
              );
            }),
          ),
      ],
    );
  }
}
