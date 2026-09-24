import '../data/sample_apps_data.dart';
import '../models/app_info_model.dart';
import '../models/user_preferences_model.dart';

/// Read-only access to the app catalog (Part 7). Backed by the curated
/// demo dataset today; every method signature is dataset-agnostic so a
/// future verified/live data source can replace [kSampleApps] without
/// changing any caller (screens only ever go through this repository,
/// never import sample_apps_data.dart directly).
class AppsRepository {
  List<AppInfo> get all => kSampleApps;

  List<AppInfo> byCategory(AppCategory category) => kSampleApps.where((a) => a.category == category).toList();

  AppInfo? byId(String id) {
    for (final app in kSampleApps) {
      if (app.id == id) return app;
    }
    return null;
  }

  /// Resolves by whichever identifier the caller actually has: this
  /// catalog's own short `id`, OR the app's `packageName` - a real Google
  /// Play package name (which is what Favorites/AppInteraction now key
  /// on, since it's the only stable id a live app has) can still match a
  /// curated demo entry whose id and packageName happen to differ.
  AppInfo? byIdOrPackageName(String identifier) {
    for (final app in kSampleApps) {
      if (app.id == identifier || app.packageName == identifier) return app;
    }
    return null;
  }

  /// Free-text search across name/description/category label (Part 13's
  /// "Search apps or describe what you need…"). Deliberately simple
  /// substring matching, not an LLM (Part 13: "Do not implement an LLM
  /// unless actually necessary").
  List<AppInfo> search(String query) {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return const [];
    return kSampleApps.where((a) {
      return a.name.toLowerCase().contains(q) ||
          (a.description ?? '').toLowerCase().contains(q) ||
          a.category.label.toLowerCase().contains(q);
    }).toList();
  }

  List<AppInfo> lightweight() => kSampleApps.where((a) => a.satisfies(AppPreference.lightweight)).toList();

  List<AppInfo> privacyFriendly() => kSampleApps.where((a) => a.satisfies(AppPreference.privacyFriendly)).toList();

  List<AppInfo> offlineCapable() => kSampleApps.where((a) => a.satisfies(AppPreference.offlineSupport)).toList();

  List<AppInfo> openSource() => kSampleApps.where((a) => a.satisfies(AppPreference.openSource)).toList();

  List<AppInfo> lowStorage() => kSampleApps.where((a) => a.satisfies(AppPreference.lowStorageUsage)).toList();

  /// Other apps in the same category as [app] (for the Alternative
  /// Finder, Part 11), excluding [app] itself.
  List<AppInfo> alternativesTo(AppInfo app) => kSampleApps.where((a) => a.category == app.category && a.id != app.id).toList();

  /// Best-effort lookup by a free-typed "current app" name (Alternative
  /// Finder without a real installed-apps match) - case-insensitive
  /// exact or substring match against the catalog; `null` if nothing
  /// resembles it closely enough to be useful.
  AppInfo? findByName(String name) {
    final q = name.trim().toLowerCase();
    if (q.isEmpty) return null;
    for (final app in kSampleApps) {
      if (app.name.toLowerCase() == q) return app;
    }
    for (final app in kSampleApps) {
      if (app.name.toLowerCase().contains(q) || q.contains(app.name.toLowerCase())) return app;
    }
    return null;
  }
}
