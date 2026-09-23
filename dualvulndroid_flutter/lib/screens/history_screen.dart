import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/app_info_model.dart';
import '../models/history_entry_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/history_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/app_shell.dart';
import '../widgets/category_icons.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

/// "Recommendation History" - real local history only. Each entry shows
/// the top apps actually recommended (with the match they had at the
/// time), when, and the device snapshot. Tapping an app opens its details
/// (live data re-fetched); "Rank again" re-runs a fresh discovery for that
/// category against CURRENT preferences - no stale result set is replayed.
class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final repo = context.watch<HistoryRepository>();
    final entries = repo.entries;

    return Scaffold(
      appBar: AppBar(
        leading: ShellScope.backButtonFor(context, ShellTab.history),
        title: const Text('Recommendation History'),
        actions: [
          if (entries.isNotEmpty)
            IconButton(
              tooltip: 'Clear history',
              icon: const Icon(AppIcons.delete),
              onPressed: () => confirmClearHistory(context, repo),
            ),
        ],
      ),
      body: repo.isLoading
          ? const LoadingView()
          : entries.isEmpty
              ? EmptyStateView(
                  icon: AppIcons.history,
                  title: 'No recommendations yet',
                  message: 'Search or browse a category and your matches will be saved here.',
                  actionLabel: 'Find Apps',
                  actionIcon: AppIcons.search,
                  onAction: () => AppRouter.toDiscover(context),
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
                  itemCount: entries.length,
                  separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.md),
                  itemBuilder: (context, index) => _HistoryCard(entry: entries[index]),
                ),
    );
  }
}

/// Shared "Clear history?" confirmation (History and Profile).
Future<void> confirmClearHistory(BuildContext context, HistoryRepository repo) async {
  final confirmed = await showDialog<bool>(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('Clear history?'),
      content: const Text('This removes your local recommendation history from this device.'),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        TextButton(
          style: TextButton.styleFrom(foregroundColor: AppColors.error),
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Clear'),
        ),
      ],
    ),
  );
  if (confirmed == true) await repo.clear();
}

class _HistoryCard extends StatelessWidget {
  final HistoryEntry entry;
  const _HistoryCard({required this.entry});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final category = entry.category;
    final deviceSummary = _deviceSummary(entry.deviceContext);

    return SmartAppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              IconBadge(icon: category != null ? resolveIconKey(category.iconKey) : AppIcons.search),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(category?.label ?? 'Search results', style: theme.textTheme.titleMedium),
                    const SizedBox(height: 2),
                    Text(
                      '${entry.resultCount} match${entry.resultCount == 1 ? '' : 'es'} · ${_formatDate(entry.timestamp)}',
                      style: theme.textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (entry.recommendedApps.isNotEmpty) ...[
            const SizedBox(height: AppSpacing.md),
            for (final app in entry.recommendedApps)
              InkWell(
                borderRadius: AppRadius.smAll,
                onTap: () => AppRouter.toAppDetail(context, _toAppInfo(app, category)),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm, horizontal: AppSpacing.xxs),
                  child: Row(
                    children: [
                      Expanded(child: Text(app.name, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodyMedium)),
                      MatchPill(percent: app.score),
                      const Icon(AppIcons.chevron, color: AppColors.textMuted, size: 20),
                    ],
                  ),
                ),
              ),
          ],
          if (deviceSummary != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Row(
              children: [
                const Icon(AppIcons.device, size: 15, color: AppColors.textMuted),
                const SizedBox(width: AppSpacing.xs),
                Expanded(child: Text(deviceSummary, style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0))),
              ],
            ),
          ],
          if (category != null) ...[
            const SizedBox(height: AppSpacing.sm),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs)),
                onPressed: () => AppRouter.toResultsForCategory(context, category),
                icon: const Icon(AppIcons.refresh, size: 18),
                label: const Text('Rank again with current profile'),
              ),
            ),
          ],
        ],
      ),
    );
  }

  /// Only what history actually stored - App Details re-fetches live data.
  AppInfo _toAppInfo(RecommendedAppEntry app, AppCategory? category) {
    final isLive = app.dataSource == 'google_play';
    return AppInfo(
      id: app.packageName,
      name: app.name,
      packageName: app.packageName,
      category: category ?? AppCategory.other,
      iconKey: category?.iconKey ?? 'apps_outlined',
      isCuratedSample: !isLive,
      isLiveData: isLive,
      dataSource: app.dataSource,
    );
  }

  String? _deviceSummary(DeviceContextSummary summary) {
    if (summary.isEmpty) return null;
    final parts = <String>[];
    if (summary.ramTotalMb != null) parts.add('${(summary.ramTotalMb! / 1024).toStringAsFixed(1)} GB RAM');
    if (summary.androidRelease != null) parts.add('Android ${summary.androidRelease}');
    if (summary.connectivityStatus != null) parts.add(summary.connectivityStatus!.label);
    if (summary.batteryLevel != null) parts.add('${summary.batteryLevel}% battery');
    return parts.isEmpty ? null : parts.join(' · ');
  }

  String _formatDate(DateTime time) {
    final diff = DateTime.now().difference(time);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
    if (diff.inHours < 24) return '${diff.inHours} h ago';
    if (diff.inDays < 7) return '${diff.inDays} d ago';
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return '${time.day} ${months[time.month - 1]} ${time.year}';
  }
}
