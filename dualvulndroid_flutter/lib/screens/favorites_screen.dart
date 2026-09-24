import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/app_info_model.dart';
import '../models/app_snapshot_model.dart';
import '../models/user_preferences_model.dart';
import '../repositories/favorites_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../widgets/app_result_card.dart';
import '../widgets/state_views.dart';

/// The user's real, locally-favorited apps. Each row shows what was
/// actually saved (a real [AppSnapshot], not a re-derived catalog lookup).
/// Tapping opens the app's details, which re-fetches current live data
/// for a real Google Play app.
class FavoritesScreen extends StatelessWidget {
  const FavoritesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final repo = context.watch<FavoritesRepository>();
    final favorites = repo.favorites;

    return Scaffold(
      appBar: AppBar(title: const Text('Favorites')),
      body: repo.isLoading
          ? const LoadingView()
          : favorites.isEmpty
              ? EmptyStateView(
                  icon: AppIcons.favorites,
                  title: 'No favorites yet',
                  message: 'Save apps you want to compare later.',
                  actionLabel: 'Discover Apps',
                  actionIcon: AppIcons.discover,
                  onAction: () => AppRouter.toDiscover(context),
                )
              : ListView.separated(
                  padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
                  itemCount: favorites.length,
                  separatorBuilder: (_, _) => const SizedBox(height: AppSpacing.sm),
                  itemBuilder: (context, index) {
                    final snapshot = favorites[index];
                    final app = _toAppInfo(snapshot);
                    return AppListCard(
                      app: app,
                      onTap: () => AppRouter.toAppDetail(context, app),
                      trailing: IconButton(
                        tooltip: 'Remove ${snapshot.name} from favorites',
                        icon: const Icon(AppIcons.favoritesFilled, color: AppColors.error),
                        onPressed: () => repo.toggle(app),
                      ),
                    );
                  },
                ),
    );
  }

  /// A minimal, honest [AppInfo] built only from what was actually
  /// snapshotted - AppDetailScreen re-fetches current live details for a
  /// real Google Play app, so nothing here is invented to fill the gap.
  AppInfo _toAppInfo(AppSnapshot snapshot) => AppInfo(
        id: snapshot.packageName,
        name: snapshot.name,
        packageName: snapshot.packageName,
        category: snapshot.category ?? AppCategory.other,
        iconKey: snapshot.iconKey ?? 'apps_outlined',
        iconUrl: snapshot.iconUrl,
        isCuratedSample: false,
        isLiveData: snapshot.isLiveData,
        dataSource: snapshot.isLiveData ? 'google_play' : null,
      );
}
