import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../widgets/smartapp_logo.dart';
import '../widgets/preference_selector.dart';
import '../widgets/smartapp_ui.dart';

/// First-run preference question (and "Edit preferences" later). Stored
/// locally only - there is no account.
class OnboardingPreferencesScreen extends StatelessWidget {
  final bool isFirstRun;

  const OnboardingPreferencesScreen({super.key, this.isFirstRun = false});

  @override
  Widget build(BuildContext context) {
    final repo = context.watch<PreferencesRepository>();
    final theme = Theme.of(context);

    return Scaffold(
      appBar: isFirstRun ? null : AppBar(title: const Text('Preferences')),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xxl, AppSpacing.page, AppSpacing.lg),
                children: [
                  if (isFirstRun) ...[
                    Row(
                      children: [
                        const SmartAppLogo(size: 40),
                        const SizedBox(width: AppSpacing.md),
                        Text('SmartApp', style: theme.textTheme.titleLarge),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.xxl),
                  ],
                  Semantics(header: true, child: Text('What matters most to you?', style: theme.textTheme.headlineSmall)),
                  const SizedBox(height: AppSpacing.sm),
                  Text(
                    'Select everything that matters - we\'ll use it to rank apps for you. You can change this any time in Profile.',
                    style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: AppSpacing.xl),
                  PreferenceSelector(selected: repo.preferences.selectedPreferences, onToggle: repo.togglePreference),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.sm, AppSpacing.page, AppSpacing.lg),
              child: PrimaryButton(
                label: isFirstRun ? 'Get Started' : 'Done',
                onPressed: () {
                  if (isFirstRun) {
                    AppRouter.toHome(context);
                  } else {
                    Navigator.of(context).pop();
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
