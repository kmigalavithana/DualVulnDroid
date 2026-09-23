import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/engines/context_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/context_effect_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';

const _engine = ContextEngine();

AppInfo _app({
  double sizeMb = 20,
  ResourceLevel resourceLevel = ResourceLevel.moderate,
  bool supportsOffline = true,
}) {
  return AppInfo(
    id: 'a',
    name: 'App',
    category: AppCategory.utilities,
    description: 'A test app.',
    iconKey: 'apps_outlined',
    sizeMb: sizeMb,
    hasAds: false,
    trackerCount: 0,
    isOpenSource: true,
    supportsOffline: supportsOffline,
    isFree: true,
    resourceLevel: resourceLevel,
    rating: 4.5,
  );
}

void main() {
  group('Context effect detection', () {
    test('no effects are active when every device signal is unavailable', () {
      expect(_engine.evaluate(const DeviceProfileModel()), isEmpty);
    });

    test('low free storage triggers the lowStorage effect', () {
      const device = DeviceProfileModel(storageFreeBytes: 500 * 1024 * 1024); // 500 MB
      final effects = _engine.evaluate(device);
      expect(effects.map((e) => e.type), contains(ContextEffectType.lowStorage));
    });

    test('ample free storage does not trigger the lowStorage effect', () {
      const device = DeviceProfileModel(storageFreeBytes: 20 * 1024 * 1024 * 1024); // 20 GB
      expect(_engine.evaluate(device).map((e) => e.type), isNot(contains(ContextEffectType.lowStorage)));
    });

    test('a low total-RAM device triggers the lowRam effect even without the OS low-RAM flag', () {
      const device = DeviceProfileModel(ramTotalMb: 2048);
      expect(_engine.evaluate(device).map((e) => e.type), contains(ContextEffectType.lowRam));
    });

    test('the OS-reported low-RAM flag triggers the lowRam effect regardless of the RAM number', () {
      const device = DeviceProfileModel(ramTotalMb: 8192, isLowRamDevice: true);
      expect(_engine.evaluate(device).map((e) => e.type), contains(ContextEffectType.lowRam));
    });

    test('battery at or below the low-battery threshold triggers the lowBattery effect', () {
      const device = DeviceProfileModel(batteryLevel: 20);
      expect(_engine.evaluate(device).map((e) => e.type), contains(ContextEffectType.lowBattery));
    });

    test('battery above the threshold does not trigger the lowBattery effect', () {
      const device = DeviceProfileModel(batteryLevel: 50);
      expect(_engine.evaluate(device).map((e) => e.type), isNot(contains(ContextEffectType.lowBattery)));
    });

    test('offline connectivity triggers the offline effect', () {
      const device = DeviceProfileModel(connectivityStatus: ConnectivityStatus.offline);
      expect(_engine.evaluate(device).map((e) => e.type), contains(ContextEffectType.offline));
    });

    test('unavailable connectivity is never treated as offline', () {
      const device = DeviceProfileModel(connectivityStatus: ConnectivityStatus.unavailable);
      expect(_engine.evaluate(device).map((e) => e.type), isNot(contains(ContextEffectType.offline)));
    });

    test('multiple simultaneous conditions produce multiple effects', () {
      const device = DeviceProfileModel(
        ramTotalMb: 1024,
        storageFreeBytes: 100 * 1024 * 1024,
        batteryLevel: 5,
        connectivityStatus: ConnectivityStatus.offline,
      );
      expect(_engine.evaluate(device).length, 4);
    });
  });

  group('Context score adjustment', () {
    test('a light app is boosted when RAM is low', () {
      final app = _app(resourceLevel: ResourceLevel.light);
      const effect = ContextEffect(ContextEffectType.lowRam, 'x');
      expect(_engine.contextScoreFor(app, const [effect]), greaterThan(0));
    });

    test('a heavy app is penalized when RAM is low', () {
      final app = _app(resourceLevel: ResourceLevel.heavy);
      const effect = ContextEffect(ContextEffectType.lowRam, 'x');
      expect(_engine.contextScoreFor(app, const [effect]), lessThan(0));
    });

    test('an offline-capable app is boosted when the device is offline', () {
      final app = _app(supportsOffline: true);
      const effect = ContextEffect(ContextEffectType.offline, 'x');
      expect(_engine.contextScoreFor(app, const [effect]), greaterThan(0));
    });

    test('an app requiring internet is penalized when the device is offline', () {
      final app = _app(supportsOffline: false);
      const effect = ContextEffect(ContextEffectType.offline, 'x');
      expect(_engine.contextScoreFor(app, const [effect]), lessThan(0));
    });

    test('no active effects means no context adjustment at all', () {
      final app = _app();
      expect(_engine.contextScoreFor(app, const []), 0);
    });

    test('the adjustment is always bounded to ±10 regardless of how many effects stack', () {
      final app = _app(resourceLevel: ResourceLevel.heavy, supportsOffline: false, sizeMb: 400);
      const effects = [
        ContextEffect(ContextEffectType.lowStorage, 'x'),
        ContextEffect(ContextEffectType.lowRam, 'x'),
        ContextEffect(ContextEffectType.lowBattery, 'x'),
        ContextEffect(ContextEffectType.offline, 'x'),
      ];
      final score = _engine.contextScoreFor(app, effects);
      expect(score, inInclusiveRange(-10, 10));
    });
  });
}
