/// One entry from the device's own launcher-visible app list (Part 12),
/// read via the platform channel in InstalledAppsService. Only
/// `appName`/`packageName` are sourced this way - never anything from
/// another app's private storage, source, or protected files.
class InstalledAppInfo {
  final String appName;
  final String packageName;

  const InstalledAppInfo({required this.appName, required this.packageName});

  factory InstalledAppInfo.fromMap(Map<dynamic, dynamic> map) {
    return InstalledAppInfo(
      appName: (map['appName'] as String?)?.trim().isNotEmpty == true ? map['appName'] as String : (map['packageName'] as String? ?? 'Unknown app'),
      packageName: map['packageName'] as String? ?? '',
    );
  }
}
