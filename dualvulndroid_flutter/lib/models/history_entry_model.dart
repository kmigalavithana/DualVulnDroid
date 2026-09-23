import 'device_profile_model.dart';
import 'user_preferences_model.dart';

/// A real, minimal snapshot of the device context at the moment a
/// recommendation session ran (Part 12: "device context summary") - only
/// the fields that were actually available are carried; nothing here is
/// re-derived or guessed later.
class DeviceContextSummary {
  final int? ramTotalMb;
  final String? androidRelease;
  final ConnectivityStatus? connectivityStatus;
  final int? batteryLevel;

  const DeviceContextSummary({this.ramTotalMb, this.androidRelease, this.connectivityStatus, this.batteryLevel});

  factory DeviceContextSummary.fromDevice(DeviceProfileModel device) => DeviceContextSummary(
        ramTotalMb: device.ramTotalMb,
        androidRelease: device.androidRelease,
        connectivityStatus: device.connectivityStatus,
        batteryLevel: device.batteryLevel,
      );

  bool get isEmpty => ramTotalMb == null && androidRelease == null && connectivityStatus == null && batteryLevel == null;

  Map<String, dynamic> toJson() => {
        if (ramTotalMb != null) 'ramTotalMb': ramTotalMb,
        if (androidRelease != null) 'androidRelease': androidRelease,
        if (connectivityStatus != null) 'connectivityStatus': connectivityStatus!.name,
        if (batteryLevel != null) 'batteryLevel': batteryLevel,
      };

  static DeviceContextSummary fromJson(Map<String, dynamic>? json) {
    if (json == null) return const DeviceContextSummary();
    ConnectivityStatus? connectivity;
    final connectivityName = json['connectivityStatus'] as String?;
    if (connectivityName != null) {
      for (final c in ConnectivityStatus.values) {
        if (c.name == connectivityName) {
          connectivity = c;
          break;
        }
      }
    }
    return DeviceContextSummary(
      ramTotalMb: json['ramTotalMb'] as int?,
      androidRelease: json['androidRelease'] as String?,
      connectivityStatus: connectivity,
      batteryLevel: json['batteryLevel'] as int?,
    );
  }
}

/// One real recommended app as it actually appeared in a discovery
/// session (Part 16: "actual recommended package name, actual app name,
/// recommendation score") - stored directly, rather than just an id to
/// resolve later, since a real Google Play app has no static local
/// catalog to resolve an id back against.
class RecommendedAppEntry {
  final String packageName;
  final String name;
  final int score;
  final String? dataSource;

  /// The app's verified-data coverage (0-1) when it was recommended - a
  /// descriptive data-completeness figure, not an accuracy metric. `null`
  /// for entries recorded before coverage existed.
  final double? metadataCoverage;

  const RecommendedAppEntry({
    required this.packageName,
    required this.name,
    required this.score,
    this.dataSource,
    this.metadataCoverage,
  });

  Map<String, dynamic> toJson() => {
        'packageName': packageName,
        'name': name,
        'score': score,
        if (dataSource != null) 'dataSource': dataSource,
        if (metadataCoverage != null) 'metadataCoverage': metadataCoverage,
      };

  static RecommendedAppEntry? fromJson(Map<String, dynamic> json) {
    final packageName = json['packageName'] as String?;
    final name = json['name'] as String?;
    if (packageName == null || name == null) return null;
    return RecommendedAppEntry(
      packageName: packageName,
      name: name,
      score: json['score'] as int? ?? 0,
      dataSource: json['dataSource'] as String?,
      metadataCoverage: (json['metadataCoverage'] as num?)?.toDouble(),
    );
  }
}

/// One real, locally-recorded discovery run (Part 14) - written only when
/// the user actually views a set of recommendation results, never
/// fabricated or pre-seeded. Grouped/displayed by [category] on the
/// History screen ("PDF Reader — 3 recommendations"). Carries the actual
/// top recommended apps (name + score, not just an id) and a device-
/// context snapshot so both the History screen and a later evaluation
/// pass (Part 14's Evaluation Mode) can use real, already-known data
/// rather than re-resolving or guessing.
class HistoryEntry {
  final String id;
  final AppCategory? category;
  final Set<AppPreference> preferences;
  final int resultCount;
  final DateTime timestamp;
  final List<RecommendedAppEntry> recommendedApps;
  final DeviceContextSummary deviceContext;

  /// Which scoring method produced this entry: 1 = before
  /// availability-aware scoring (entries saved without the field), 2 =
  /// availability-aware scoring with verified-metadata enrichment. Lets
  /// Evaluation compare the two on real feedback.
  final int scoringVersion;

  const HistoryEntry({
    required this.id,
    required this.category,
    required this.preferences,
    required this.resultCount,
    required this.timestamp,
    this.recommendedApps = const [],
    this.deviceContext = const DeviceContextSummary(),
    this.scoringVersion = 1,
  });

  /// Backward/forward-compat convenience for callers (e.g.
  /// EvaluationEngine) that only need the package names.
  List<String> get recommendedAppIds => recommendedApps.map((a) => a.packageName).toList();

  Map<String, dynamic> toJson() => {
        'id': id,
        if (category != null) 'category': category!.name,
        'preferences': preferences.map((p) => p.name).toList(),
        'resultCount': resultCount,
        'timestamp': timestamp.toIso8601String(),
        'recommendedApps': recommendedApps.map((a) => a.toJson()).toList(),
        if (!deviceContext.isEmpty) 'deviceContext': deviceContext.toJson(),
        'scoringVersion': scoringVersion,
      };

  factory HistoryEntry.fromJson(Map<String, dynamic> json) {
    final categoryName = json['category'] as String?;
    AppCategory? category;
    if (categoryName != null) {
      for (final c in AppCategory.values) {
        if (c.name == categoryName) {
          category = c;
          break;
        }
      }
    }
    final rawPrefs = (json['preferences'] as List?) ?? const [];
    final prefs = <AppPreference>{};
    for (final name in rawPrefs.whereType<String>()) {
      for (final p in AppPreference.values) {
        if (p.name == name) {
          prefs.add(p);
          break;
        }
      }
    }
    final rawApps = (json['recommendedApps'] as List?) ?? const [];
    return HistoryEntry(
      id: json['id'] as String,
      category: category,
      preferences: prefs,
      resultCount: json['resultCount'] as int? ?? 0,
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ?? DateTime.now(),
      recommendedApps: rawApps.whereType<Map<String, dynamic>>().map(RecommendedAppEntry.fromJson).whereType<RecommendedAppEntry>().toList(),
      deviceContext: DeviceContextSummary.fromJson(json['deviceContext'] as Map<String, dynamic>?),
      scoringVersion: json['scoringVersion'] as int? ?? 1,
    );
  }
}
