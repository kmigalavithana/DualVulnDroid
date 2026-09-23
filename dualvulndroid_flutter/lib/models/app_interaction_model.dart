import 'app_snapshot_model.dart';

/// One real, locally-recorded "the user opened this app's details"
/// event (Part 10's "apps opened" adaptive signal). Written only when the
/// user actually navigates to an app's detail screen - never fabricated.
/// Carries a real [AppSnapshot] (not just an id) so it can still be
/// resolved/displayed later even for a real Google Play app with no
/// local catalog entry to look the id back up against.
class AppOpenEvent {
  final AppSnapshot snapshot;
  final DateTime timestamp;

  const AppOpenEvent({required this.snapshot, required this.timestamp});

  String get appId => snapshot.packageName;

  Map<String, dynamic> toJson() => {
        'snapshot': snapshot.toJson(),
        'timestamp': timestamp.toIso8601String(),
      };

  static AppOpenEvent? fromJson(Map<String, dynamic> json) {
    final rawSnapshot = json['snapshot'] as Map<String, dynamic>?;
    if (rawSnapshot == null) return null;
    return AppOpenEvent(
      snapshot: AppSnapshot.fromJson(rawSnapshot),
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
