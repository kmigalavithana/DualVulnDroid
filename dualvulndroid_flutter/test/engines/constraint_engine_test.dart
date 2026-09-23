import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/engines/constraint_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';

const _engine = ConstraintEngine();

AppInfo _app({
  String id = 'a',
  bool isFree = true,
  bool supportsOffline = true,
  int trackerCount = 0,
  double sizeMb = 20,
  int? minimumAndroidSdk,
}) {
  return AppInfo(
    id: id,
    name: 'App $id',
    category: AppCategory.utilities,
    description: 'A test app.',
    iconKey: 'apps_outlined',
    sizeMb: sizeMb,
    hasAds: false,
    trackerCount: trackerCount,
    isOpenSource: true,
    supportsOffline: supportsOffline,
    isFree: isFree,
    minimumAndroidSdk: minimumAndroidSdk,
    resourceLevel: ResourceLevel.light,
    rating: 4.5,
  );
}

void main() {
  group('Constraint filtering', () {
    test('an app passes when no constraint is enabled', () {
      final app = _app(isFree: false, supportsOffline: false, trackerCount: 9);
      expect(_engine.passes(app, const HardConstraints(enforceAndroidCompatibility: false), null), isTrue);
    });

    test('freeOnly excludes paid apps and keeps free ones', () {
      final free = _app(id: 'free', isFree: true);
      final paid = _app(id: 'paid', isFree: false);
      final result = _engine.filter(apps: [free, paid], constraints: const HardConstraints(freeOnly: true));
      expect(result.map((a) => a.id), [free.id]);
    });

    test('offlineRequired excludes apps that need internet', () {
      final offline = _app(id: 'offline', supportsOffline: true);
      final online = _app(id: 'online', supportsOffline: false);
      final result = _engine.filter(apps: [offline, online], constraints: const HardConstraints(offlineRequired: true));
      expect(result.map((a) => a.id), [offline.id]);
    });

    test('noTrackers excludes any app with at least one tracker', () {
      final clean = _app(id: 'clean', trackerCount: 0);
      final tracked = _app(id: 'tracked', trackerCount: 1);
      final result = _engine.filter(apps: [clean, tracked], constraints: const HardConstraints(noTrackers: true));
      expect(result.map((a) => a.id), [clean.id]);
    });

    test('maxSizeMb excludes apps larger than the limit', () {
      final small = _app(id: 'small', sizeMb: 10);
      final large = _app(id: 'large', sizeMb: 200);
      final result = _engine.filter(apps: [small, large], constraints: const HardConstraints(maxSizeMb: 50));
      expect(result.map((a) => a.id), [small.id]);
    });

    test('Android compatibility is enforced by default even with no other constraint set', () {
      final compatible = _app(id: 'ok', minimumAndroidSdk: 21);
      final incompatible = _app(id: 'new', minimumAndroidSdk: 33);
      const device = DeviceProfileModel(androidSdkInt: 24);
      final result = _engine.filter(apps: [compatible, incompatible], constraints: const HardConstraints(), device: device);
      expect(result.map((a) => a.id), [compatible.id]);
    });

    test('Android compatibility is skipped when the device SDK is unknown, never guessed', () {
      final incompatible = _app(id: 'new', minimumAndroidSdk: 33);
      final result = _engine.filter(apps: [incompatible], constraints: const HardConstraints(), device: null);
      expect(result.map((a) => a.id), [incompatible.id]);
    });

    test('enforceAndroidCompatibility: false disables the compatibility filter for What-If exploration', () {
      final incompatible = _app(id: 'new', minimumAndroidSdk: 33);
      const device = DeviceProfileModel(androidSdkInt: 21);
      final result = _engine.filter(
        apps: [incompatible],
        constraints: const HardConstraints(enforceAndroidCompatibility: false),
        device: device,
      );
      expect(result.map((a) => a.id), [incompatible.id]);
    });

    test('multiple constraints all apply (AND, not OR)', () {
      final passesAll = _app(id: 'passes', isFree: true, supportsOffline: true, trackerCount: 0);
      final failsOne = _app(id: 'fails', isFree: true, supportsOffline: false, trackerCount: 0);
      final result = _engine.filter(
        apps: [passesAll, failsOne],
        constraints: const HardConstraints(freeOnly: true, offlineRequired: true, noTrackers: true),
      );
      expect(result.map((a) => a.id), [passesAll.id]);
    });

    test('failedConstraints explains exactly why an app was excluded', () {
      final app = _app(id: 'x', isFree: false, supportsOffline: false);
      final failed = _engine.failedConstraints(app, const HardConstraints(freeOnly: true, offlineRequired: true), null);
      expect(failed, containsAll(['Not free', 'Requires internet']));
    });

    test('an empty HardConstraints is reported as empty (ignoring the always-on compatibility flag)', () {
      expect(const HardConstraints().isEmpty, isTrue);
      expect(const HardConstraints(freeOnly: true).isEmpty, isFalse);
    });
  });
}
