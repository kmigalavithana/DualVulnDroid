import 'app_info_model.dart';
import 'user_preferences_model.dart';

/// A small, real, stable-enough-to-persist snapshot of one [AppInfo] -
/// just enough (packageName/name/category/icon) to display a favorited,
/// opened, or recommended app later WITHOUT depending on a static local
/// catalog lookup. This exists because real Play Store apps have no
/// local catalog entry to resolve an id back against (unlike the old
/// curated demo dataset, where every id was always in kSampleApps) - so
/// Favorites/History/AppInteraction now store what was actually shown at
/// the time, never a fabricated re-derivation.
class AppSnapshot {
  final String packageName;
  final String name;
  final AppCategory? category;
  final String? iconUrl;
  final String? iconKey;
  final bool isLiveData;

  const AppSnapshot({
    required this.packageName,
    required this.name,
    this.category,
    this.iconUrl,
    this.iconKey,
    this.isLiveData = false,
  });

  factory AppSnapshot.fromApp(AppInfo app) => AppSnapshot(
        packageName: app.packageName ?? app.id,
        name: app.name,
        category: app.category,
        iconUrl: app.iconUrl,
        iconKey: app.iconKey,
        isLiveData: app.isLiveData,
      );

  Map<String, dynamic> toJson() => {
        'packageName': packageName,
        'name': name,
        if (category != null) 'category': category!.name,
        if (iconUrl != null) 'iconUrl': iconUrl,
        if (iconKey != null) 'iconKey': iconKey,
        'isLiveData': isLiveData,
      };

  factory AppSnapshot.fromJson(Map<String, dynamic> json) {
    AppCategory? category;
    final categoryName = json['category'] as String?;
    if (categoryName != null) {
      for (final c in AppCategory.values) {
        if (c.name == categoryName) {
          category = c;
          break;
        }
      }
    }
    return AppSnapshot(
      packageName: json['packageName'] as String,
      name: json['name'] as String? ?? 'Unavailable',
      category: category,
      iconUrl: json['iconUrl'] as String?,
      iconKey: json['iconKey'] as String?,
      isLiveData: json['isLiveData'] as bool? ?? false,
    );
  }
}
