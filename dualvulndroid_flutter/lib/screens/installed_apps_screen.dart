import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/installed_app_model.dart';
import '../routing/app_router.dart';
import '../services/installed_apps_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/smartapp_ui.dart';
import '../widgets/state_views.dart';

/// Installed Apps. Uses only the launcher-visible package list Android's
/// own PackageManager legitimately exposes (see InstalledAppsService /
/// MainActivity.kt) - never another app's private data, and never a
/// fabricated list. If enumeration is restricted on this device, the
/// screen explains why and points to Discover instead.
class InstalledAppsScreen extends StatefulWidget {
  const InstalledAppsScreen({super.key});

  @override
  State<InstalledAppsScreen> createState() => _InstalledAppsScreenState();
}

class _InstalledAppsScreenState extends State<InstalledAppsScreen> {
  late Future<InstalledAppsResult> _future;
  String _filter = '';

  @override
  void initState() {
    super.initState();
    _future = context.read<InstalledAppsService>().getInstalledApps();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Installed Apps')),
      body: FutureBuilder<InstalledAppsResult>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const LoadingView(message: 'Reading installed apps…');
          }
          final result = snapshot.data;
          if (result is! InstalledAppsAvailable) {
            return EmptyStateView(
              icon: Icons.lock_outline_rounded,
              title: 'Installed apps unavailable',
              message: 'Android doesn\'t let SmartApp list installed apps on this device or Android version. '
                  'You can still search any app in Discover and compare alternatives from its details.',
              actionLabel: 'Go to Discover',
              actionIcon: AppIcons.discover,
              onAction: () => AppRouter.toDiscover(context),
            );
          }
          if (result.apps.isEmpty) {
            return const EmptyStateView(
              icon: AppIcons.installedApps,
              title: 'No apps found',
              message: 'No launcher-visible apps were reported by Android.',
            );
          }
          final query = _filter.toLowerCase();
          final apps = query.isEmpty
              ? result.apps
              : result.apps.where((a) => a.appName.toLowerCase().contains(query) || a.packageName.toLowerCase().contains(query)).toList();
          return ListView(
            padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
            children: [
              Text(
                '${result.apps.length} apps on this device. Pick one to find apps that may fit you better.',
                style: theme.textTheme.bodySmall,
              ),
              const SizedBox(height: AppSpacing.md),
              TextField(
                onChanged: (value) => setState(() => _filter = value.trim()),
                decoration: const InputDecoration(hintText: 'Filter installed apps…', prefixIcon: Icon(AppIcons.search)),
              ),
              const SizedBox(height: AppSpacing.md),
              if (apps.isEmpty)
                EmptyStateView(icon: Icons.search_off_rounded, message: 'No installed app matches "$_filter".')
              else
                for (final app in apps)
                  Padding(
                    padding: const EdgeInsets.only(bottom: AppSpacing.sm),
                    child: _InstalledAppTile(app: app),
                  ),
            ],
          );
        },
      ),
    );
  }
}

class _InstalledAppTile extends StatelessWidget {
  final InstalledAppInfo app;
  const _InstalledAppTile({required this.app});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SmartAppCard(
      padding: const EdgeInsets.fromLTRB(AppSpacing.lg, AppSpacing.md, AppSpacing.sm, AppSpacing.md),
      child: Row(
        children: [
          const IconBadge(icon: AppIcons.android, color: AppColors.success, size: 44),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(app.appName, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.titleSmall),
                const SizedBox(height: 2),
                Text(app.packageName, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0)),
              ],
            ),
          ),
          TextButton.icon(
            onPressed: () => AppRouter.toAlternativeFinder(context, initialAppName: app.appName),
            icon: const Icon(AppIcons.alternatives, size: 18),
            label: const Text('Alternatives'),
            style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm)),
          ),
        ],
      ),
    );
  }
}
