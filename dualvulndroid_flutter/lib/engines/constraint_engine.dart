import '../models/app_info_model.dart';
import '../models/device_profile_model.dart';

/// User-chosen hard filters (What-If). Every constraint is checked against
/// VERIFIED data only and has three outcomes:
///   * verified pass  -> app kept
///   * verified fail  -> app excluded
///   * not verified   -> app kept, and the constraint is reported as
///                       "Not verified" for it (unknown is never treated
///                       as a pass or as a fail)
class HardConstraints {
  final bool freeOnly;
  final bool offlineRequired;
  final bool noTrackers;
  final bool noAds;
  final bool openSourceOnly;
  final double? maxSizeMb;
  final bool enforceAndroidCompatibility;

  const HardConstraints({
    this.freeOnly = false,
    this.offlineRequired = false,
    this.noTrackers = false,
    this.noAds = false,
    this.openSourceOnly = false,
    this.maxSizeMb,
    this.enforceAndroidCompatibility = true,
  });

  bool get isEmpty => !freeOnly && !offlineRequired && !noTrackers && !noAds && !openSourceOnly && maxSizeMb == null;

  HardConstraints copyWith({
    bool? freeOnly,
    bool? offlineRequired,
    bool? noTrackers,
    bool? noAds,
    bool? openSourceOnly,
    double? maxSizeMb,
    bool clearMaxSizeMb = false,
    bool? enforceAndroidCompatibility,
  }) {
    return HardConstraints(
      freeOnly: freeOnly ?? this.freeOnly,
      offlineRequired: offlineRequired ?? this.offlineRequired,
      noTrackers: noTrackers ?? this.noTrackers,
      noAds: noAds ?? this.noAds,
      openSourceOnly: openSourceOnly ?? this.openSourceOnly,
      maxSizeMb: clearMaxSizeMb ? null : (maxSizeMb ?? this.maxSizeMb),
      enforceAndroidCompatibility: enforceAndroidCompatibility ?? this.enforceAndroidCompatibility,
    );
  }
}

/// One active constraint's outcome for one app: `true` verified pass,
/// `false` verified fail, `null` not verified.
class ConstraintCheck {
  final String label;
  final bool? passed;
  final String failureReason;

  const ConstraintCheck(this.label, this.passed, this.failureReason);
}

class ConstraintEngine {
  const ConstraintEngine();

  /// Keeps every app that has no VERIFIED failure. Apps whose data can't
  /// be verified stay in (see [unverifiedConstraints]).
  List<AppInfo> filter({
    required List<AppInfo> apps,
    required HardConstraints constraints,
    DeviceProfileModel? device,
  }) {
    return apps.where((app) => passes(app, constraints, device)).toList();
  }

  bool passes(AppInfo app, HardConstraints constraints, DeviceProfileModel? device) {
    return failedConstraints(app, constraints, device).isEmpty;
  }

  /// Every active constraint's tri-state outcome for [app].
  List<ConstraintCheck> evaluate(AppInfo app, HardConstraints constraints, DeviceProfileModel? device) {
    final checks = <ConstraintCheck>[];
    if (constraints.freeOnly) {
      checks.add(ConstraintCheck('Free only', app.isFree, 'Not free'));
    }
    if (constraints.offlineRequired) {
      checks.add(ConstraintCheck('Works offline', app.supportsOffline, 'Requires internet'));
    }
    if (constraints.noTrackers) {
      final trackers = app.trackerCount;
      checks.add(ConstraintCheck('No trackers', trackers == null ? null : trackers == 0, 'Has trackers'));
    }
    if (constraints.noAds) {
      final ads = app.hasAds;
      checks.add(ConstraintCheck('No ads', ads == null ? null : !ads, 'Contains ads'));
    }
    if (constraints.openSourceOnly) {
      checks.add(ConstraintCheck('Open source', app.isOpenSource, 'Not open source'));
    }
    final maxSize = constraints.maxSizeMb;
    if (maxSize != null) {
      final size = app.sizeMb;
      checks.add(ConstraintCheck('Low storage', size == null ? null : size <= maxSize, 'Larger than ${maxSize.round()} MB'));
    }
    final sdk = device?.androidSdkInt;
    final minSdk = app.minimumAndroidSdk;
    if (constraints.enforceAndroidCompatibility && sdk != null && minSdk != null) {
      // Only checked when both are known; an unknown requirement is not
      // reported (it applies to every live app and isn't user-selected).
      checks.add(ConstraintCheck('Android compatible', sdk >= minSdk, 'Requires Android $minSdk or newer'));
    }
    return checks;
  }

  /// Reasons for VERIFIED failures only.
  List<String> failedConstraints(AppInfo app, HardConstraints constraints, DeviceProfileModel? device) =>
      evaluate(app, constraints, device).where((c) => c.passed == false).map((c) => c.failureReason).toList();

  /// Labels of active constraints that can't be checked for [app] because
  /// the data isn't verified.
  List<String> unverifiedConstraints(AppInfo app, HardConstraints constraints, [DeviceProfileModel? device]) =>
      evaluate(app, constraints, device).where((c) => c.passed == null).map((c) => c.label).toList();
}
