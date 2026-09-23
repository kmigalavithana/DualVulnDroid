import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/recommendation_engine.dart';
import '../models/app_info_model.dart';
import '../models/recommendation_result_model.dart';
import '../repositories/favorites_repository.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import 'app_icon.dart';
import 'smartapp_ui.dart';

/// One ranked app on a results list. Every value shown - the match %, the
/// reason summary, the privacy/resource tags - comes straight from the
/// real, already-calculated [RecommendationResult] or from attributes the
/// data source actually verified; nothing is invented here. The match %
/// is always labeled as a match for the user's profile, never as an
/// overall app-quality score.
class AppResultCard extends StatelessWidget {
  final RecommendationResult result;
  final bool isBestMatch;
  final VoidCallback onTap;

  /// Extra "why it's here" tags (e.g. Alternative Finder comparisons).
  final List<String> highlights;

  const AppResultCard({
    super.key,
    required this.result,
    required this.onTap,
    this.isBestMatch = false,
    this.highlights = const [],
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final app = result.app;
    final favorites = context.watch<FavoritesRepository>();
    final isFavorite = favorites.isFavorite(app);
    final indicators = verifiedIndicators(app);

    return SmartAppCard(
      onTap: onTap,
      borderColor: isBestMatch ? AppColors.accent.withValues(alpha: 0.55) : null,
      semanticLabel: '${app.name}, ${result.matchPercent} percent match${isBestMatch ? ', best match' : ''}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (isBestMatch) ...[
            const InfoPill(label: 'Best match for you', icon: AppIcons.recommendations, color: AppColors.accent),
            const SizedBox(height: AppSpacing.md),
          ],
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppIcon(iconUrl: app.iconUrl, iconKey: app.iconKey, size: 52),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(app.name, maxLines: 2, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(
                      [app.category.label, if (app.developer != null) app.developer!].join(' · '),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall,
                    ),
                    if (app.rating != null) ...[
                      const SizedBox(height: AppSpacing.xs),
                      RatingLabel(rating: app.rating, reviewCount: app.reviewCount),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: AppSpacing.sm),
              if (result.hasVerifiedFactors)
                MatchIndicator(percent: result.matchPercent)
              else
                const IconBadge(icon: AppIcons.info, color: AppColors.textSecondary, size: 52),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            const RecommendationEngine().summarize(result),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodySmall?.copyWith(color: AppColors.textPrimary.withValues(alpha: 0.86)),
          ),
          if (result.unverifiedConstraints.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                for (final constraint in result.unverifiedConstraints)
                  InfoPill(label: 'Not verified: $constraint', icon: Icons.help_outline_rounded, color: AppColors.warning),
              ],
            ),
          ],
          if (highlights.isNotEmpty || indicators.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                for (final highlight in highlights) InfoPill(label: highlight, icon: Icons.trending_up_rounded, color: AppColors.success),
                ...indicators,
              ],
            ),
          ],
          const SizedBox(height: AppSpacing.xs),
          Row(
            children: [
              Expanded(
                child: Text(
                  result.hasVerifiedFactors
                      ? '${result.matchPercent}% match for your current profile · based on ${result.availableFactorCount} of 5 verified factors'
                      : 'Not enough verified data to score this app',
                  style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0),
                ),
              ),
              IconButton(
                tooltip: isFavorite ? 'Remove ${app.name} from favorites' : 'Save ${app.name} to favorites',
                icon: Icon(
                  isFavorite ? AppIcons.favoritesFilled : AppIcons.favorites,
                  color: isFavorite ? AppColors.error : AppColors.textSecondary,
                  size: 22,
                ),
                onPressed: () => favorites.toggle(app),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

/// Privacy/resource tags for attributes the data source actually
/// verified - an unverified (null) attribute produces no tag at all.
List<Widget> verifiedIndicators(AppInfo app) {
  final tags = <Widget>[];
  final trackers = app.trackerCount;
  if (trackers != null) {
    tags.add(InfoPill(
      label: trackers == 0 ? 'No trackers' : '$trackers tracker${trackers == 1 ? '' : 's'}',
      icon: AppIcons.privacy,
      color: trackers == 0 ? AppColors.success : AppColors.warning,
    ));
  }
  final resource = app.resourceLevel;
  if (resource != null) {
    tags.add(InfoPill(
      label: '${resource.label} resource use',
      icon: AppIcons.performance,
      color: resource == ResourceLevel.heavy ? AppColors.warning : AppColors.textSecondary,
    ));
  }
  if (app.supportsOffline == true) tags.add(const InfoPill(label: 'Works offline', icon: AppIcons.offline));
  if (app.hasAds == false) tags.add(const InfoPill(label: 'No ads', icon: Icons.block_rounded));
  if (app.hasAds == true) tags.add(const InfoPill(label: 'Contains ads', icon: Icons.campaign_outlined, color: AppColors.warning));
  if (app.isFree == true) tags.add(const InfoPill(label: 'Free', icon: Icons.sell_outlined));
  if (app.isFree == false) tags.add(InfoPill(label: app.price ?? 'Paid', icon: Icons.sell_outlined));
  if (app.isOpenSource == true) tags.add(const InfoPill(label: 'Open source', icon: Icons.code_rounded, color: AppColors.accentCyan));
  return tags;
}

/// A compact app row (Discover search results, Favorites): icon, name,
/// category/developer, rating, and - when it has been calculated - the
/// match for the user's profile.
class AppListCard extends StatelessWidget {
  final AppInfo app;
  final VoidCallback onTap;
  final int? matchPercent;
  final Widget? trailing;

  const AppListCard({super.key, required this.app, required this.onTap, this.matchPercent, this.trailing});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      onTap: onTap,
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.md),
      semanticLabel: [
        app.name,
        app.category.label,
        if (matchPercent != null) '$matchPercent percent match',
      ].join(', '),
      child: Row(
        children: [
          AppIcon(iconUrl: app.iconUrl, iconKey: app.iconKey, size: 48),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(app.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleSmall),
                const SizedBox(height: 2),
                Text(
                  [app.category.label, if (app.developer != null) app.developer!].join(' · '),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.bodySmall,
                ),
                if (app.rating != null || matchPercent != null) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Wrap(
                    spacing: AppSpacing.sm,
                    runSpacing: AppSpacing.xxs,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      if (app.rating != null) RatingLabel(rating: app.rating),
                      if (matchPercent != null) MatchPill(percent: matchPercent!),
                    ],
                  ),
                ],
              ],
            ),
          ),
          trailing ?? const Icon(AppIcons.chevron, color: AppColors.textMuted),
        ],
      ),
    );
  }
}
