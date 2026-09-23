import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/app_info_model.dart';
import '../models/app_snapshot_model.dart';
import '../repositories/app_interaction_repository.dart';
import '../repositories/app_repository.dart';
import '../repositories/device_profile_repository.dart';
import '../repositories/favorites_repository.dart';
import '../repositories/feedback_repository.dart';
import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../services/play_store_launcher.dart';
import '../engines/recommendation_engine.dart';
import '../models/recommendation_result_model.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/app_icon.dart';
import '../widgets/category_icons.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/context_banner.dart';
import '../widgets/feedback_buttons.dart';
import '../utils/byte_format.dart';
import '../utils/play_store_link.dart';

/// App details + "Why this app?" (Part 7/10/13) - the score is always
/// recomputed live from the user's CURRENT preferences/device profile via
/// [RecommendationEngine], so this screen can never show a stale or
/// hardcoded percentage, however the user navigated here (a results
/// card, Discover, Favorites, Installed Apps). Records exactly one real
/// "app opened" interaction per visit (Part 10's adaptive signal).
///
/// For a real Google Play app ([AppInfo.isLiveData]), this screen
/// additionally re-fetches full current details (version, screenshots,
/// release/update dates - fields a search result alone doesn't carry) in
/// the background via [AppRepository.getAppDetails]. The score/details
/// initially shown come from whatever [AppInfo] the caller already had
/// (e.g. a search result) - if the live re-fetch fails (offline, app
/// removed from the store, etc.) this screen simply keeps showing that,
/// never a fabricated fallback.
class AppDetailScreen extends StatefulWidget {
  final AppInfo app;

  const AppDetailScreen({super.key, required this.app});

  @override
  State<AppDetailScreen> createState() => _AppDetailScreenState();
}

class _AppDetailScreenState extends State<AppDetailScreen> {
  bool _recorded = false;
  AppInfo? _refreshedApp;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_recorded) {
      _recorded = true;
      context.read<AppInteractionRepository>().recordOpen(AppSnapshot.fromApp(widget.app));
      _refreshLiveDetails();
    }
  }

  Future<void> _refreshLiveDetails() async {
    final app = widget.app;
    final packageName = app.packageName;
    if (!app.isLiveData || packageName == null) return;
    try {
      final details = await context.read<AppRepository>().getAppDetails(packageName);
      if (mounted && details != null) setState(() => _refreshedApp = details.mergedWith(app));
    } catch (_) {
      // Offline, backend unavailable, or the app is no longer listed -
      // keep showing what we already have rather than an error for a
      // screen whose primary content already rendered successfully.
    }
  }

  @override
  Widget build(BuildContext context) {
    final app = _refreshedApp ?? widget.app;
    final theme = Theme.of(context);
    final preferences = context.watch<PreferencesRepository>().preferences;
    final device = context.watch<DeviceProfileRepository>().profile;
    const engine = RecommendationEngine();
    final weights = EngineWeights.fromMap(preferences.weightOverrides);
    final result = engine.score(app: app, preferences: preferences, device: device, weights: weights);
    final favorites = context.watch<FavoritesRepository>();
    final isFavorite = favorites.isFavorite(app);

    return Scaffold(
      appBar: AppBar(
        title: const Text('App Details'),
        actions: [
          IconButton(
            tooltip: isFavorite ? 'Remove from favorites' : 'Save to favorites',
            icon: Icon(isFavorite ? AppIcons.favoritesFilled : AppIcons.favorites, color: isFavorite ? AppColors.error : null),
            onPressed: () => favorites.toggle(app),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.sm, AppSpacing.page, AppSpacing.section),
        children: [
          _AppHeader(app: app),
          if (app.privacyDataSource == 'exodus' || app.fdroidAvailable == true) ...[
            const SizedBox(height: AppSpacing.md),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: [
                if (app.privacyDataSource == 'exodus')
                  const InfoPill(label: 'Privacy data verified · Source: εxodus', icon: AppIcons.privacy, color: AppColors.accentCyan),
                if (app.fdroidAvailable == true)
                  const InfoPill(label: 'Open-source metadata verified · Source: F-Droid', icon: Icons.code_rounded, color: AppColors.accentCyan),
              ],
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
          _PlayStoreButton(app: app),
          const SizedBox(height: AppSpacing.sm),
          SecondaryButton(
            label: 'Find Alternatives',
            icon: AppIcons.alternatives,
            onPressed: () => AppRouter.toAlternativeFinder(context, initialApp: app),
          ),
          const SizedBox(height: AppSpacing.section),
          _WhyThisApp(result: result),
          if (result.activeContextEffects.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            ContextBanner(effects: result.activeContextEffects),
          ],
          const SizedBox(height: AppSpacing.section),
          const SectionHeader(title: 'About this app'),
          _ExpandableText(text: app.description ?? 'No description available.'),
          if (app.isCuratedSample) ...[
            const SizedBox(height: AppSpacing.md),
            const InsightBanner(
              title: 'Demo dataset',
              icon: AppIcons.demoData,
              color: AppColors.textSecondary,
              messages: ['This app\'s metadata is curated for this prototype - it is not verified live Google Play data.'],
            ),
          ],
          if (app.screenshots.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.xl),
            SizedBox(
              height: 200,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: app.screenshots.length,
                separatorBuilder: (_, _) => const SizedBox(width: AppSpacing.sm),
                itemBuilder: (context, index) => Semantics(
                  image: true,
                  label: 'Screenshot ${index + 1} of ${app.screenshots.length}',
                  child: ClipRRect(
                    borderRadius: AppRadius.mdAll,
                    child: Image.network(
                      app.screenshots[index],
                      height: 200,
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) => const SizedBox.shrink(),
                    ),
                  ),
                ),
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.section),
          const SectionHeader(title: 'Details', subtitle: 'Only what the data source actually reports.'),
          SmartAppCard(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
            child: Column(
              children: [
                DetailRow(label: 'Category', value: app.category.label, icon: resolveIconKey(app.category.iconKey)),
                if (app.developer != null) DetailRow(label: 'Developer', value: app.developer!, icon: Icons.business_outlined),
                if (app.version != null) DetailRow(label: 'Version', value: app.version!, icon: Icons.new_releases_outlined),
                if (app.updatedOn != null) DetailRow(label: 'Updated', value: app.updatedOn!, icon: AppIcons.calendar),
                if (app.releaseDate != null) DetailRow(label: 'Released', value: app.releaseDate!, icon: AppIcons.calendar),
                if (app.minimumAndroidSdk != null) DetailRow(label: 'Minimum Android', value: 'API ${app.minimumAndroidSdk}', icon: AppIcons.android),
                _verified(
                  'Price',
                  app.isFree == null ? null : (app.isFree! ? 'Free' : (app.price ?? 'Paid')),
                  Icons.sell_outlined,
                ),
                _verified('Ads', app.hasAds == null ? null : (app.hasAds! ? 'Contains ads' : 'No ads'), Icons.campaign_outlined),
                if (app.inAppPurchases == true) const DetailRow(label: 'In-app purchases', value: 'Yes', icon: Icons.shopping_bag_outlined),
                _verified(
                  'Trackers',
                  app.trackerCount == null
                      ? null
                      : (app.trackerCount == 0 ? 'None detected' : '${app.trackerCount} detected') +
                          (app.privacyDataSource == 'exodus' ? ' (εxodus)' : ''),
                  AppIcons.privacy,
                ),
                if (app.trackerNames.isNotEmpty) DetailRow(label: 'Tracker names', value: app.trackerNames.join(', '), icon: AppIcons.privacy),
                if (app.permissions != null) DetailRow(label: 'Permissions', value: '${app.permissions!.length}', icon: Icons.key_outlined),
                _verified(
                  'Open source',
                  app.isOpenSource == true ? (app.license != null ? 'Yes · ${app.license}' : 'Yes (F-Droid)') : null,
                  Icons.code_rounded,
                ),
                if (app.antiFeatures.isNotEmpty) DetailRow(label: 'F-Droid anti-features', value: app.antiFeatures.join(', '), icon: AppIcons.info),
                if (app.fdroidSourceUrl != null) DetailRow(label: 'Source code', value: app.fdroidSourceUrl!, icon: Icons.link_rounded),
                _verified('Size', app.sizeMb == null ? null : formatAppSizeMb(app.sizeMb), AppIcons.storage),
                _verified(
                  'Offline support',
                  app.supportsOffline == null ? null : (app.supportsOffline! ? 'Works offline' : 'Requires internet'),
                  AppIcons.offline,
                ),
              ],
            ),
          ),
          if (app.dataSafety.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.section),
            const SectionHeader(title: 'Data safety', subtitle: 'Declared by the developer on Google Play - not independently verified.'),
            SmartAppCard(
              padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
              child: Column(
                children: [
                  for (final statement in app.dataSafety)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Icon(Icons.policy_outlined, size: 17, color: AppColors.textMuted),
                          const SizedBox(width: AppSpacing.sm),
                          Expanded(child: Text(statement, style: theme.textTheme.bodySmall?.copyWith(color: AppColors.textPrimary))),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.section),
          const SectionHeader(title: 'Was this recommendation helpful?'),
          Builder(builder: (context) {
            final feedback = context.watch<FeedbackRepository>();
            return FeedbackButtons(
              selected: feedback.latestFor(app.packageName ?? app.id)?.type,
              onSelect: (type) => feedback.record(app.packageName ?? app.id, type),
            );
          }),
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Your feedback powers the Evaluation metrics in Profile.',
            style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0),
          ),
        ],
      ),
    );
  }

  /// A details row whose value may not be verified by the data source.
  Widget _verified(String label, String? value, IconData icon) =>
      DetailRow(label: label, value: value ?? 'Not verified', icon: icon, muted: value == null);
}

class _AppHeader extends StatelessWidget {
  final AppInfo app;
  const _AppHeader({required this.app});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AppIcon(iconUrl: app.iconUrl, iconKey: app.iconKey, size: 76),
        const SizedBox(width: AppSpacing.lg),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Semantics(header: true, child: Text(app.name, style: theme.textTheme.headlineSmall)),
              if (app.developer != null) ...[
                const SizedBox(height: 2),
                Text(app.developer!, style: theme.textTheme.bodyMedium?.copyWith(color: AppColors.accent)),
              ],
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.md,
                runSpacing: AppSpacing.xs,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  if (app.rating != null)
                    RatingLabel(rating: app.rating, reviewCount: app.reviewCount)
                  else
                    Text('No rating available', style: theme.textTheme.bodySmall),
                  _DataSourceBadge(isLiveData: app.isLiveData),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}

/// "Why this app?" - the real, calculated factor contributions from
/// [RecommendationResult], explained for a non-technical reader.
class _WhyThisApp extends StatelessWidget {
  final RecommendationResult result;
  const _WhyThisApp({required this.result});

  static const _plainLabels = ['Your preferences', 'Your device', 'Privacy', 'Performance', 'Rating'];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final percent = result.matchPercent;
    final factors = result.explanationFactors;
    final reasons = [...result.reasons.where((r) => r.isPositive), ...result.reasons.where((r) => !r.isPositive)];

    return SmartAppCard(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (result.hasVerifiedFactors)
                MatchIndicator(percent: percent, size: 68)
              else
                const IconBadge(icon: AppIcons.info, color: AppColors.textSecondary, size: 68),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Semantics(header: true, child: Text('Why this app?', style: theme.textTheme.titleLarge)),
                    const SizedBox(height: AppSpacing.xxs),
                    Text(
                      result.hasVerifiedFactors ? '$percent% match for your current profile' : 'Not enough verified data to score this app',
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: [
              InfoPill(label: 'Based on ${result.availableFactorCount} of 5 factors', icon: AppIcons.evaluation),
              InfoPill(
                label: 'Verified data coverage: ${(result.app.metadataCoverage * 100).round()}%',
                icon: AppIcons.check,
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          for (var i = 0; i < factors.length; i++)
            _FactorBar(
              icon: AppIcons.factorIcons[i],
              label: _plainLabels[i],
              earned: factors[i].earnedPoints,
              max: factors[i].maxPoints,
              available: factors[i].available,
              evidence: factors[i].evidence,
            ),
          if (result.availableFactorCount < 5)
            Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.sm),
              child: Text(
                'Factors without verified data are left out, and their weight is shared by the verified ones - unknown is never counted for or against the app.',
                style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0, height: 1.4),
              ),
            ),
          if (result.contextAdjustmentPoints != 0)
            Padding(
              padding: const EdgeInsets.only(top: AppSpacing.xs),
              child: Row(
                children: [
                  const Icon(AppIcons.device, size: 18, color: AppColors.textSecondary),
                  const SizedBox(width: AppSpacing.sm),
                  Expanded(child: Text('Adjusted for your device right now', style: theme.textTheme.bodySmall)),
                  Text(
                    '${result.contextAdjustmentPoints > 0 ? '+' : ''}${result.contextAdjustmentPoints}',
                    style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: result.contextAdjustmentPoints > 0 ? AppColors.success : AppColors.error,
                    ),
                  ),
                ],
              ),
            ),
          if (reasons.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.lg),
            const Divider(),
            const SizedBox(height: AppSpacing.md),
            for (final reason in reasons)
              Padding(
                padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      reason.isPositive ? AppIcons.check : AppIcons.info,
                      size: 18,
                      color: reason.isPositive ? AppColors.success : AppColors.warning,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(child: Text(reason.text, style: theme.textTheme.bodyMedium)),
                  ],
                ),
              ),
          ],
          const SizedBox(height: AppSpacing.sm),
          Text(
            'Confidence ${(result.confidence * 100).round()}% - how much of this score used real data rather than neutral defaults. '
            'This is a match for you, not a claim that the app is objectively the best.',
            style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0, height: 1.4),
          ),
        ],
      ),
    );
  }
}

class _FactorBar extends StatelessWidget {
  final IconData icon;
  final String label;
  final int earned;
  final int max;
  final bool available;
  final String? evidence;
  const _FactorBar({
    required this.icon,
    required this.label,
    required this.earned,
    required this.max,
    this.available = true,
    this.evidence,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: available ? '$label: $earned of $max points' : '$label: not enough verified data',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 18, color: available ? AppColors.textSecondary : AppColors.textMuted),
                const SizedBox(width: AppSpacing.sm),
                Expanded(
                  child: Text(label, style: theme.textTheme.bodyMedium?.copyWith(color: available ? null : AppColors.textMuted)),
                ),
                if (available) ...[
                  Text('+$earned', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                  Text(' / $max', style: theme.textTheme.bodySmall),
                ],
              ],
            ),
            if (!available) ...[
              const SizedBox(height: 3),
              Padding(
                padding: const EdgeInsets.only(left: 26),
                child: Text('Not enough verified data', style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0)),
              ),
            ],
            if (available) ...[
              const SizedBox(height: AppSpacing.xs),
              ClipRRect(
                borderRadius: AppRadius.pillAll,
                child: LinearProgressIndicator(value: max == 0 ? 0 : earned / max, minHeight: 6),
              ),
            ],
            if (evidence != null) ...[
              const SizedBox(height: 3),
              Padding(
                padding: const EdgeInsets.only(left: 26),
                child: Text(evidence!, style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0, color: AppColors.textSecondary)),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _ExpandableText extends StatefulWidget {
  final String text;
  const _ExpandableText({required this.text});

  @override
  State<_ExpandableText> createState() => _ExpandableTextState();
}

class _ExpandableTextState extends State<_ExpandableText> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textSecondary);
    final isLong = widget.text.length > 220;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AnimatedSize(
          duration: const Duration(milliseconds: 200),
          alignment: Alignment.topCenter,
          child: Text(
            widget.text,
            style: style,
            maxLines: _expanded || !isLong ? null : 5,
            overflow: _expanded || !isLong ? null : TextOverflow.ellipsis,
          ),
        ),
        if (isLong)
          TextButton(
            style: TextButton.styleFrom(padding: EdgeInsets.zero),
            onPressed: () => setState(() => _expanded = !_expanded),
            child: Text(_expanded ? 'Show less' : 'Show more'),
          ),
      ],
    );
  }
}

class _DataSourceBadge extends StatelessWidget {
  final bool isLiveData;
  const _DataSourceBadge({required this.isLiveData});

  @override
  Widget build(BuildContext context) {
    return isLiveData
        ? const InfoPill(label: 'Live Google Play data', icon: AppIcons.liveData, color: AppColors.accentCyan)
        : const InfoPill(label: 'Demo data', icon: AppIcons.demoData);
  }
}

class _PlayStoreButton extends StatefulWidget {
  final AppInfo app;
  const _PlayStoreButton({required this.app});

  @override
  State<_PlayStoreButton> createState() => _PlayStoreButtonState();
}

class _PlayStoreButtonState extends State<_PlayStoreButton> {
  bool _failed = false;

  @override
  Widget build(BuildContext context) {
    // The provider's own URL, or the standard package URL for a verified
    // live Google Play package - never guessed (see resolvePlayStoreUrl).
    // Without either, the button is disabled and says why.
    final url = resolvePlayStoreUrl(widget.app);
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        PrimaryButton(
          label: 'Open in Google Play',
          icon: AppIcons.playStore,
          onPressed: url == null
              ? null
              : () async {
                  final launcher = context.read<PlayStoreLauncher>();
                  final ok = await launcher.open(url);
                  if (mounted) setState(() => _failed = !ok);
                },
        ),
        if (url == null) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            widget.app.isLiveData
                ? 'No verified Play Store link available.'
                : 'Demo apps have no Google Play listing.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall,
          ),
        ],
        if (_failed) ...[
          const SizedBox(height: AppSpacing.xs),
          Text(
            'Couldn\'t open the store link on this device.',
            textAlign: TextAlign.center,
            style: theme.textTheme.bodySmall?.copyWith(color: AppColors.error),
          ),
        ],
      ],
    );
  }
}
