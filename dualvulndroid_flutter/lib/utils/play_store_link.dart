import '../models/app_info_model.dart';

/// Android application IDs: dot-separated segments that start with a
/// letter and contain only letters, digits and underscores (at least two
/// segments). Anything else is not treated as a real package name.
final RegExp _packageNamePattern = RegExp(r'^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$');

/// The Google Play link for [app], or `null` when there is no verified one.
///
/// 1. The exact URL the live provider returned, when it returned one.
/// 2. Otherwise - ONLY for a live Google Play result (not demo/curated
///    data) whose packageName came from that result - the standard
///    package URL `https://play.google.com/store/apps/details?id=PACKAGE`,
///    with the package name URL-encoded.
///
/// Never built from an app name, a guessed package, or demo data.
String? resolvePlayStoreUrl(AppInfo app) {
  final returned = app.playStoreUrl?.trim();
  if (returned != null && returned.isNotEmpty) return returned;

  final package = app.packageName?.trim();
  final isLiveGooglePlay = app.isLiveData && !app.isCuratedSample && app.dataSource == 'google_play';
  if (!isLiveGooglePlay || package == null || !_packageNamePattern.hasMatch(package)) return null;

  return Uri(
    scheme: 'https',
    host: 'play.google.com',
    path: '/store/apps/details',
    queryParameters: {'id': package},
  ).toString();
}
