import 'package:flutter/services.dart';

import '../models/installed_app_model.dart';

/// Result of an installed-apps lookup attempt - explicit success/
/// unavailable states (Part 12/19) rather than an empty list standing in
/// for both "genuinely zero apps" and "the platform refused/failed",
/// which would be indistinguishable and could mislead the UI into
/// showing a misleading empty state instead of the real fallback message.
sealed class InstalledAppsResult {
  const InstalledAppsResult();
}

class InstalledAppsAvailable extends InstalledAppsResult {
  final List<InstalledAppInfo> apps;
  const InstalledAppsAvailable(this.apps);
}

class InstalledAppsUnavailable extends InstalledAppsResult {
  const InstalledAppsUnavailable();
}

/// Bridges to a small native Android MethodChannel (see MainActivity.kt)
/// that enumerates only the launcher-visible apps on the device via
/// `PackageManager` - the same category of information any home-screen
/// launcher legitimately sees, declared via a `<queries>` manifest entry
/// rather than the restricted `QUERY_ALL_PACKAGES` permission (Part 12:
/// "Only use information that the Android platform legitimately
/// exposes" / "respect Android platform restrictions").
///
/// Never throws and never fabricates a list: a missing platform
/// implementation (non-Android), a `PlatformException`, or any other
/// failure all resolve to [InstalledAppsUnavailable] so the UI can fall
/// back to category/search-based discovery instead (Part 12/19).
class InstalledAppsService {
  static const _channel = MethodChannel('smartapp/installed_apps');

  Future<InstalledAppsResult> getInstalledApps() async {
    try {
      final result = await _channel.invokeMethod<List<Object?>>('getInstalledApps');
      if (result == null) return const InstalledAppsUnavailable();
      final apps = result
          .whereType<Map<dynamic, dynamic>>()
          .map(InstalledAppInfo.fromMap)
          .where((a) => a.packageName.isNotEmpty)
          .toList()
        ..sort((a, b) => a.appName.toLowerCase().compareTo(b.appName.toLowerCase()));
      return InstalledAppsAvailable(apps);
    } on MissingPluginException {
      return const InstalledAppsUnavailable();
    } on PlatformException {
      return const InstalledAppsUnavailable();
    } catch (_) {
      return const InstalledAppsUnavailable();
    }
  }
}
