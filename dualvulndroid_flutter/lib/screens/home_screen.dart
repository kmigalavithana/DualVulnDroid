import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/recommendation_engine.dart';
import '../models/device_profile_model.dart';
import '../repositories/device_profile_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/smartapp_logo.dart';
import '../widgets/device_summary_card.dart';
import '../widgets/smartapp_ui.dart';

/// The SmartApp dashboard: brand, the "Discover apps that fit you" hero
/// with the two main entry points, the real device summary, a Smart
/// Insight derived only from real device data, and quick actions.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final deviceRepo = context.watch<DeviceProfileRepository>();
    final theme = Theme.of(context);

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.md, AppSpacing.page, AppSpacing.section),
          children: [
            _Header(onPreferences: () => AppRouter.toPreferences(context)),
            const SizedBox(height: AppSpacing.xxl),
            const _HeroCard(),
            const SizedBox(height: AppSpacing.xl),
            DeviceSummaryCard(
              profile: deviceRepo.profile,
              loading: deviceRepo.isLoading,
              onTap: () => AppRouter.toDeviceProfile(context),
            ),
            _SmartInsight(profile: deviceRepo.profile, loading: deviceRepo.isLoading),
            const SizedBox(height: AppSpacing.section),
            Semantics(header: true, child: Text('Quick actions', style: theme.textTheme.titleLarge)),
            const SizedBox(height: AppSpacing.md),
            ResponsiveGrid(
              children: [
                _QuickAction(
                  icon: AppIcons.discover,
                  title: 'Discover',
                  description: 'Search live Google Play apps',
                  onTap: () => AppRouter.toDiscover(context),
                ),
                _QuickAction(
                  icon: AppIcons.installedApps,
                  title: 'Installed Apps',
                  description: 'Find alternatives to your apps',
                  onTap: () => AppRouter.toInstalledApps(context),
                ),
                _QuickAction(
                  icon: AppIcons.favorites,
                  title: 'Favorites',
                  description: 'Apps you saved to compare',
                  onTap: () => AppRouter.toFavorites(context),
                ),
                _QuickAction(
                  icon: AppIcons.history,
                  title: 'History',
                  description: 'Your past recommendations',
                  onTap: () => AppRouter.toHistory(context),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final VoidCallback onPreferences;
  const _Header({required this.onPreferences});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        const SmartAppLogo(size: 44),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(header: true, child: Text('SmartApp', style: theme.textTheme.displaySmall)),
              const SizedBox(height: 2),
              Text('Find apps that fit your preferences and your device.', style: theme.textTheme.bodySmall),
            ],
          ),
        ),
        IconButton(
          tooltip: 'Edit preferences',
          icon: const Icon(AppIcons.settings),
          onPressed: onPreferences,
        ),
      ],
    );
  }
}

class _HeroCard extends StatelessWidget {
  const _HeroCard();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xxl),
      decoration: BoxDecoration(
        gradient: AppColors.heroSurfaceGradient,
        borderRadius: AppRadius.xlAll,
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Discover apps that fit you', style: theme.textTheme.headlineSmall),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'SmartApp ranks real Google Play apps by how well they match what you care about - and what your phone can run.',
            style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary),
          ),
          const SizedBox(height: AppSpacing.lg),
          const Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              InfoPill(label: 'Preferences', icon: AppIcons.preferences),
              InfoPill(label: 'Device', icon: AppIcons.device),
              InfoPill(label: 'Privacy', icon: AppIcons.privacy),
              InfoPill(label: 'Performance', icon: AppIcons.performance),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          PrimaryButton(label: 'Find Apps', icon: AppIcons.search, onPressed: () => AppRouter.toDiscover(context)),
          const SizedBox(height: AppSpacing.sm),
          SecondaryButton(
            label: 'Explore Alternatives',
            icon: AppIcons.alternatives,
            onPressed: () => AppRouter.toAlternativeFinder(context),
          ),
        ],
      ),
    );
  }
}

/// Only real, currently-active context effects (the same ones the
/// ranking engine applies) - or, when the device reported data but none
/// apply, a plain statement of that. Nothing is shown before any real
/// device data exists.
class _SmartInsight extends StatelessWidget {
  final DeviceProfileModel profile;
  final bool loading;
  const _SmartInsight({required this.profile, required this.loading});

  @override
  Widget build(BuildContext context) {
    if (loading || !profile.hasAnyData) return const SizedBox.shrink();
    final effects = const RecommendationEngine().contextEffectsFor(profile);
    final messages = effects.isEmpty
        ? ['Your device isn\'t limited right now, so apps are ranked on your preferences, privacy, resources and rating - with no device-based adjustments.']
        : [for (final effect in effects) effect.message];
    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.md),
      child: InsightBanner(title: 'Smart insight', messages: messages),
    );
  }
}

class _QuickAction extends StatelessWidget {
  final IconData icon;
  final String title;
  final String description;
  final VoidCallback onTap;
  const _QuickAction({required this.icon, required this.title, required this.description, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      onTap: onTap,
      semanticLabel: '$title. $description',
      padding: const EdgeInsets.all(AppSpacing.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          IconBadge(icon: icon),
          const SizedBox(height: AppSpacing.md),
          Text(title, style: theme.textTheme.titleSmall),
          const SizedBox(height: 2),
          Text(description, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall),
        ],
      ),
    );
  }
}
