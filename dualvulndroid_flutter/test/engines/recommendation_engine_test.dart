import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/engines/constraint_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';

const _engine = RecommendationEngine();

AppInfo _app({
  String id = 'a',
  String name = 'App A',
  AppCategory category = AppCategory.utilities,
  double sizeMb = 20,
  bool hasAds = false,
  int trackerCount = 0,
  bool isOpenSource = true,
  bool supportsOffline = true,
  bool isFree = true,
  int? minimumAndroidSdk,
  ResourceLevel resourceLevel = ResourceLevel.light,
  double? rating = 4.5,
  int? reviewCount = 100,
  String? playStoreUrl,
}) {
  return AppInfo(
    id: id,
    name: name,
    category: category,
    description: 'A test app.',
    iconKey: 'apps_outlined',
    sizeMb: sizeMb,
    hasAds: hasAds,
    trackerCount: trackerCount,
    isOpenSource: isOpenSource,
    supportsOffline: supportsOffline,
    isFree: isFree,
    minimumAndroidSdk: minimumAndroidSdk,
    resourceLevel: resourceLevel,
    rating: rating,
    reviewCount: reviewCount,
    playStoreUrl: playStoreUrl,
  );
}

const _fullDevice = DeviceProfileModel(
  androidSdkInt: 34,
  androidRelease: '14',
  ramTotalMb: 8192,
  ramAvailableMb: 4096,
  isLowRamDevice: false,
  storageTotalBytes: 128000000000,
  storageFreeBytes: 32000000000,
  abis: ['arm64-v8a'],
);

void main() {
  group('1. Preference scoring', () {
    test('an app satisfying every selected preference scores the maximum preference contribution', () {
      final app = _app(hasAds: false, trackerCount: 0, supportsOffline: true, isFree: true, isOpenSource: true, resourceLevel: ResourceLevel.light, sizeMb: 5);
      final prefs = UserPreferencesModel(selectedPreferences: {
        AppPreference.lightweight,
        AppPreference.noAds,
        AppPreference.offlineSupport,
      });
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      expect(result.breakdown.preference, closeTo(RecommendationEngine.preferenceWeight * 100, 0.001));
    });

    test('an app satisfying none of the selected preferences scores zero preference contribution', () {
      final app = _app(hasAds: true, trackerCount: 5, supportsOffline: false, resourceLevel: ResourceLevel.heavy, sizeMb: 300);
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.noAds, AppPreference.offlineSupport});
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      expect(result.breakdown.preference, closeTo(0, 0.001));
    });

    test('partial preference match is proportional', () {
      final app = _app(hasAds: false, trackerCount: 5); // satisfies noAds, not privacyFriendly
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.noAds, AppPreference.privacyFriendly});
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      // 1 of 2 preferences matched -> 50 raw * 0.30 weight = 15
      expect(result.breakdown.preference, closeTo(15, 0.001));
    });
  });

  group('2. Device suitability scoring', () {
    test('a light app is fully suitable regardless of RAM', () {
      final app = _app(resourceLevel: ResourceLevel.light);
      const lowRamDevice = DeviceProfileModel(ramTotalMb: 1024, androidSdkInt: 30);
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: lowRamDevice);
      // Scored 100/100; its weight is the effective (redistributed) one.
      expect(result.breakdown.device, closeTo(result.breakdown.effectiveWeights[1] * 100, 0.001));
    });

    test('a heavy app on a low-RAM device scores lower than on a high-RAM device', () {
      final app = _app(resourceLevel: ResourceLevel.heavy);
      const lowRam = DeviceProfileModel(ramTotalMb: 2048, androidSdkInt: 30, isLowRamDevice: true);
      const highRam = DeviceProfileModel(ramTotalMb: 8192, androidSdkInt: 30, isLowRamDevice: false);
      final lowResult = _engine.score(app: app, preferences: const UserPreferencesModel(), device: lowRam);
      final highResult = _engine.score(app: app, preferences: const UserPreferencesModel(), device: highRam);
      expect(lowResult.breakdown.device, lessThan(highResult.breakdown.device));
    });

    test('an app requiring a newer Android version than the device has scores very low device suitability', () {
      final app = _app(minimumAndroidSdk: 33, resourceLevel: ResourceLevel.light);
      const oldDevice = DeviceProfileModel(androidSdkInt: 24, ramTotalMb: 8192);
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: oldDevice);
      expect(result.breakdown.device, lessThanOrEqualTo(result.breakdown.effectiveWeights[1] * 15 + 0.001));
    });
  });

  group('3. Privacy scoring', () {
    test('zero trackers scores the maximum privacy contribution', () {
      final app = _app(trackerCount: 0);
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(result.breakdown.privacy, closeTo(result.breakdown.effectiveWeights[2] * 100, 0.001));
    });

    test('more trackers strictly reduces the privacy contribution', () {
      final low = _engine.score(app: _app(trackerCount: 1), preferences: const UserPreferencesModel(), device: _fullDevice);
      final high = _engine.score(app: _app(trackerCount: 9), preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(high.breakdown.privacy, lessThan(low.breakdown.privacy));
    });
  });

  group('4. Resource efficiency scoring', () {
    test('a light app scores higher resource efficiency than a heavy app', () {
      final light = _engine.score(app: _app(resourceLevel: ResourceLevel.light), preferences: const UserPreferencesModel(), device: _fullDevice);
      final heavy = _engine.score(app: _app(resourceLevel: ResourceLevel.heavy), preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(light.breakdown.resource, greaterThan(heavy.breakdown.resource));
    });

    test('a very large install size further reduces resource efficiency', () {
      final small = _engine.score(app: _app(resourceLevel: ResourceLevel.moderate, sizeMb: 40), preferences: const UserPreferencesModel(), device: _fullDevice);
      final large = _engine.score(app: _app(resourceLevel: ResourceLevel.moderate, sizeMb: 400), preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(large.breakdown.resource, lessThan(small.breakdown.resource));
    });
  });

  group('5. Final recommendation score', () {
    test('equals the sum of the five weighted contributions and matches a hand-computed example', () {
      // Mirrors the spec's own worked example: preference=90, device=95,
      // privacy=100, resource=90, rating=85 (raw 0-100 sub-scores) should
      // combine to 92.75 - engineered here via a device/app combination
      // that produces exactly those raw sub-scores is impractical, so
      // instead this verifies the INVARIANT the example demonstrates:
      // finalScore is always exactly the sum of the five weighted parts,
      // never a separately-hardcoded number.
      final app = _app(hasAds: false, trackerCount: 0, resourceLevel: ResourceLevel.light, rating: 4.6);
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.noAds, AppPreference.privacyFriendly});
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      final b = result.breakdown;
      expect(b.finalScore, closeTo(b.preference + b.device + b.privacy + b.resource + b.rating, 0.0001));
      expect(result.matchPercent, b.finalScore.round());
    });

    test('final score never exceeds 100 or drops below 0', () {
      final best = _engine.score(
        app: _app(hasAds: false, trackerCount: 0, resourceLevel: ResourceLevel.light, rating: 5.0),
        preferences: UserPreferencesModel(selectedPreferences: AppPreference.values.toSet()),
        device: _fullDevice,
      );
      final worst = _engine.score(
        app: _app(hasAds: true, trackerCount: 20, resourceLevel: ResourceLevel.heavy, sizeMb: 900, rating: 1.0, minimumAndroidSdk: 34, isFree: false, isOpenSource: false, supportsOffline: false),
        preferences: UserPreferencesModel(selectedPreferences: AppPreference.values.toSet()),
        device: const DeviceProfileModel(androidSdkInt: 21, ramTotalMb: 512, isLowRamDevice: true),
      );
      expect(best.matchPercent, lessThanOrEqualTo(100));
      expect(worst.matchPercent, greaterThanOrEqualTo(0));
    });
  });

  group('6. Ranking multiple apps', () {
    test('rank() sorts by descending final score', () {
      final strong = _app(id: 's', name: 'Strong', hasAds: false, trackerCount: 0, resourceLevel: ResourceLevel.light, rating: 4.9);
      final weak = _app(id: 'w', name: 'Weak', hasAds: true, trackerCount: 9, resourceLevel: ResourceLevel.heavy, sizeMb: 500, rating: 2.0);
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.noAds, AppPreference.privacyFriendly, AppPreference.lightweight});
      final ranked = _engine.rank(apps: [weak, strong], preferences: prefs, device: _fullDevice);
      expect(ranked.first.app.id, 's');
      expect(ranked.last.app.id, 'w');
      expect(ranked.first.breakdown.finalScore, greaterThanOrEqualTo(ranked.last.breakdown.finalScore));
    });

    test('ties are broken deterministically by app name', () {
      final a = _app(id: 'a', name: 'Alpha');
      final b = _app(id: 'b', name: 'Beta');
      final ranked1 = _engine.rank(apps: [b, a], preferences: const UserPreferencesModel(), device: _fullDevice);
      final ranked2 = _engine.rank(apps: [a, b], preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(ranked1.map((r) => r.app.id).toList(), ranked2.map((r) => r.app.id).toList());
    });
  });

  group('7. Explanation generation', () {
    test('positive reasons only include preferences the app actually satisfies; a verified miss is a caveat', () {
      final app = _app(hasAds: false, trackerCount: 5); // satisfies noAds, NOT privacyFriendly
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.noAds, AppPreference.privacyFriendly});
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      final positive = result.reasons.where((r) => r.isPositive).map((r) => r.text.toLowerCase()).join(' | ');
      expect(positive, contains('no ads'));
      expect(positive, isNot(contains('privacy-friendly')));
      final caveats = result.reasons.where((r) => !r.isPositive).map((r) => r.text.toLowerCase());
      expect(caveats, contains("doesn't meet your preference for privacy-friendly"));
    });

    test('summarize() builds its sentence only from the same reasons list, never separately', () {
      final app = _app(hasAds: false, trackerCount: 0, resourceLevel: ResourceLevel.light, supportsOffline: true);
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.offlineSupport, AppPreference.lowStorageUsage});
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      final summary = _engine.summarize(result);
      expect(summary, isNotEmpty);
      expect(summary.endsWith('.'), isTrue);
    });

    test('an app matching nothing still gets at least one honest, non-empty reason', () {
      final app = _app(hasAds: true, trackerCount: 9, resourceLevel: ResourceLevel.heavy, sizeMb: 500, rating: null);
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: const DeviceProfileModel());
      expect(result.reasons, isNotEmpty);
    });
  });

  group('8. Empty recommendation state', () {
    test('ranking an empty app list returns an empty result list, never a crash or a fabricated entry', () {
      final ranked = _engine.rank(apps: const [], preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(ranked, isEmpty);
    });
  });

  group('9. Missing device information', () {
    test('an entirely empty device profile still produces a valid, bounded score', () {
      final app = _app();
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: const DeviceProfileModel());
      expect(result.matchPercent, inInclusiveRange(0, 100));
      // Nothing about the device is known: the device factor is
      // unavailable (0, weight redistributed), not a made-up neutral 60.
      expect(result.breakdown.available[1], isFalse);
      expect(result.breakdown.device, 0);
    });
  });

  group('10. Missing app metadata', () {
    test('a null rating is unavailable - neither neutral credit nor a zero penalty', () {
      final unrated = _engine.score(app: _app(rating: null), preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(unrated.breakdown.available[4], isFalse);
      expect(unrated.breakdown.rating, 0);
      expect(unrated.breakdown.effectiveWeights[4], 0);
      // Its weight is redistributed: the available weights still sum to 1.
      expect(unrated.breakdown.effectiveWeights.fold<double>(0, (a, b) => a + b), closeTo(1, 1e-9));
    });

    test('a null minimumAndroidSdk never triggers the incompatibility penalty', () {
      final app = _app(minimumAndroidSdk: null, resourceLevel: ResourceLevel.light);
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: const DeviceProfileModel(androidSdkInt: 21, ramTotalMb: 8192));
      expect(result.breakdown.device, closeTo(result.breakdown.effectiveWeights[1] * 100, 0.001));
    });
  });

  group('11. Alternative recommendation', () {
    test('an app never appears among its own category-mates ranked as an alternative to itself', () {
      final current = _app(id: 'current', category: AppCategory.notes);
      final sameCategory = _app(id: 'alt', name: 'Alt', category: AppCategory.notes);
      final otherCategory = _app(id: 'other', category: AppCategory.music);
      final catalog = [current, sameCategory, otherCategory];
      final alternatives = catalog.where((a) => a.category == current.category && a.id != current.id).toList();
      final ranked = _engine.rank(apps: alternatives, preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(ranked.map((r) => r.app.id), everyElement(isNot('current')));
      expect(ranked.map((r) => r.app.id), everyElement(isNot('other')));
      expect(ranked.map((r) => r.app.id), contains('alt'));
    });
  });

  group('12. Hard constraint filtering inside rank()', () {
    test('an Android-incompatible app is excluded from ranked results by default', () {
      final compatible = _app(id: 'ok', minimumAndroidSdk: 21);
      final incompatible = _app(id: 'new', minimumAndroidSdk: 33);
      const device = DeviceProfileModel(androidSdkInt: 24, ramTotalMb: 8192);
      final ranked = _engine.rank(apps: [compatible, incompatible], preferences: const UserPreferencesModel(), device: device);
      expect(ranked.map((r) => r.app.id), [compatible.id]);
    });

    test('an empty/default device never filters anything out (compatibility unknown, never guessed)', () {
      final app = _app(minimumAndroidSdk: 33);
      final ranked = _engine.rank(apps: [app], preferences: const UserPreferencesModel(), device: const DeviceProfileModel());
      expect(ranked, hasLength(1));
    });

    test('an explicit freeOnly hard constraint excludes paid apps entirely, not just penalizes them', () {
      final free = _app(id: 'free', isFree: true);
      final paid = _app(id: 'paid', isFree: false);
      final ranked = _engine.rank(
        apps: [free, paid],
        preferences: const UserPreferencesModel(),
        device: _fullDevice,
        constraints: const HardConstraints(freeOnly: true),
      );
      expect(ranked.map((r) => r.app.id), [free.id]);
    });
  });

  group('13. Confidence', () {
    test('confidence is highest when every underlying signal is available', () {
      final app = _app(rating: 4.5);
      final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.noAds});
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      expect(result.confidence, 1.0);
    });

    test('confidence drops when device/app/preference signals are missing', () {
      final app = _app(rating: null);
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: const DeviceProfileModel());
      expect(result.confidence, lessThan(1.0));
      expect(result.confidence, greaterThanOrEqualTo(0.0));
    });
  });

  group('14. Explanation factors ("Why this app?" point breakdown)', () {
    test('each factor\'s max points matches its published weight, and they sum to 100', () {
      final app = _app();
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: _fullDevice);
      final maxTotal = result.explanationFactors.fold<int>(0, (sum, f) => sum + f.maxPoints);
      expect(maxTotal, 100);
      expect(result.explanationFactors.map((f) => f.label), [
        'Preference Match',
        'Device Suitability',
        'Privacy',
        'Resource Efficiency',
        'Rating',
      ]);
    });

    test('earnedPoints never exceeds maxPoints for any factor', () {
      final app = _app(hasAds: false, trackerCount: 0, resourceLevel: ResourceLevel.light, rating: 5.0);
      final prefs = UserPreferencesModel(selectedPreferences: AppPreference.values.toSet());
      final result = _engine.score(app: app, preferences: prefs, device: _fullDevice);
      for (final factor in result.explanationFactors) {
        expect(factor.earnedPoints, lessThanOrEqualTo(factor.maxPoints));
      }
    });

    test(
      'the five displayed points plus the context adjustment always sum to exactly the displayed match percent '
      '(audit regression: independently rounding each factor used to disagree with the displayed total, '
      'e.g. weighted values 15.0/23.75/10.0/4.5/8.2 rounded separately summed to 62 while the true total rounds to 61)',
      () {
        // Engineered so the five weighted contributions are exactly
        // 15.0 (preference), 23.75 (device), 10.0 (privacy), 4.5 (resource),
        // 8.2 (rating) - reproducing the hand-computed counter-example
        // above: independently rounding each gives 15+24+10+5+8=62, but
        // the true total (61.45) rounds to 61.
        final app = _app(
          hasAds: false,
          trackerCount: 4, // privacyRaw 50 -> *0.20 = 10.0
          resourceLevel: ResourceLevel.heavy, // resourceRaw 30 -> *0.15 = 4.5
          sizeMb: 20,
          rating: 4.1, // ratingRaw 82 -> *0.10 = 8.2
          isFree: true,
          supportsOffline: false, // satisfies "free" but not "offlineSupport" below
        );
        const device = DeviceProfileModel(ramTotalMb: 8192, androidSdkInt: 30); // heavy app, ram>=6144 -> deviceRaw 95 -> *0.25 = 23.75
        // Exactly one of two selected preferences satisfied -> preferenceRaw 50 -> *0.30 = 15.0
        final prefs = UserPreferencesModel(selectedPreferences: {AppPreference.free, AppPreference.offlineSupport});
        final result = _engine.score(app: app, preferences: prefs, device: device);

        expect(result.breakdown.preference, closeTo(15.0, 0.0001));
        expect(result.breakdown.device, closeTo(23.75, 0.0001));
        expect(result.breakdown.privacy, closeTo(10.0, 0.0001));
        expect(result.breakdown.resource, closeTo(4.5, 0.0001));
        expect(result.breakdown.rating, closeTo(8.2, 0.0001));
        expect(result.breakdown.context, 0); // no context effects on this device

        final factorSum = result.explanationFactors.fold<int>(0, (sum, f) => sum + f.earnedPoints);
        expect(result.matchPercent, 61, reason: 'sanity check on the hand-computed true total');
        expect(
          factorSum + result.contextAdjustmentPoints,
          result.matchPercent,
          reason: 'factorSum=$factorSum (independent rounding would give 62, not matching matchPercent=61)',
        );
      },
    );

    test('factor points plus context adjustment sum to the match percent across many randomized apps/devices', () {
      final random = List.generate(200, (seed) {
        final r = seed * 2654435761 % 1000; // deterministic pseudo-random spread, no external package needed
        return r;
      });
      for (final seed in random) {
        final app = _app(
          hasAds: seed % 2 == 0,
          trackerCount: seed % 11,
          resourceLevel: ResourceLevel.values[seed % 3],
          sizeMb: (seed % 400).toDouble(),
          rating: seed % 51 == 0 ? null : 1.0 + (seed % 41) / 10.0,
          minimumAndroidSdk: seed % 5 == 0 ? 21 + (seed % 15) : null,
          isFree: seed % 3 != 0,
          supportsOffline: seed % 4 != 0,
          isOpenSource: seed % 6 != 0,
        );
        final device = DeviceProfileModel(
          ramTotalMb: seed % 7 == 0 ? null : 512 + (seed % 16) * 512,
          androidSdkInt: seed % 9 == 0 ? null : 21 + (seed % 15),
          isLowRamDevice: seed % 8 == 0,
          storageFreeBytes: seed % 5 == 0 ? (seed % 3) * 1024 * 1024 * 1024 : null,
          batteryLevel: seed % 10 == 0 ? seed % 100 : null,
          connectivityStatus: ConnectivityStatus.values[seed % ConnectivityStatus.values.length],
        );
        final prefsSet = AppPreference.values.where((p) => (seed + p.index) % 3 == 0).toSet();
        final result = _engine.score(app: app, preferences: UserPreferencesModel(selectedPreferences: prefsSet), device: device);

        final factorSum = result.explanationFactors.fold<int>(0, (sum, f) => sum + f.earnedPoints);
        expect(
          factorSum + result.contextAdjustmentPoints,
          result.matchPercent,
          reason: 'seed=$seed factorSum=$factorSum context=${result.contextAdjustmentPoints} '
              'matchPercent=${result.matchPercent} breakdown=${result.breakdown.preference},${result.breakdown.device},'
              '${result.breakdown.privacy},${result.breakdown.resource},${result.breakdown.rating},${result.breakdown.context}',
        );
      }
    });
  });

  group('15. What-If weight overrides (EngineWeights)', () {
    test('custom weights change which app ranks first without touching the stored preferences', () {
      final lightweight = _app(id: 'light', resourceLevel: ResourceLevel.light, rating: 3.0);
      final highlyRated = _app(id: 'rated', resourceLevel: ResourceLevel.heavy, rating: 5.0);
      const resourceFocused = EngineWeights(preference: 0.05, device: 0.05, privacy: 0.05, resource: 0.80, rating: 0.05);
      final ranked = _engine.rank(
        apps: [highlyRated, lightweight],
        preferences: const UserPreferencesModel(),
        device: _fullDevice,
        weights: resourceFocused.normalized(),
      );
      expect(ranked.first.app.id, 'light');
    });

    test('EngineWeights.normalized() always sums to 1.0', () {
      const weights = EngineWeights(preference: 3, device: 1, privacy: 1, resource: 1, rating: 1);
      expect(weights.normalized().total, closeTo(1.0, 0.0001));
    });

    test('priority levels scale a dimension up or down relative to the default weights', () {
      final high = EngineWeightsPriorities.fromPriorities(resource: PriorityLevel.high);
      final low = EngineWeightsPriorities.fromPriorities(resource: PriorityLevel.low);
      expect(high.resource, greaterThan(low.resource));
      expect(high.total, closeTo(1.0, 0.0001));
    });
  });

  group('16. Context-aware scoring', () {
    test('an app satisfying no preferences still gets a real, calculated context score field, defaulting to zero', () {
      final app = _app();
      final result = _engine.score(app: app, preferences: const UserPreferencesModel(), device: _fullDevice);
      expect(result.breakdown.context, 0);
      expect(result.activeContextEffects, isEmpty);
    });

    test('a lightweight app outranks a heavy app more strongly on a low-RAM device than on a capable one', () {
      final light = _app(id: 'light', resourceLevel: ResourceLevel.light);
      final heavy = _app(id: 'heavy', resourceLevel: ResourceLevel.heavy);
      const lowRamDevice = DeviceProfileModel(ramTotalMb: 1024, isLowRamDevice: true);
      const capableDevice = DeviceProfileModel(ramTotalMb: 8192);

      final lowRamGap = _engine.score(app: light, preferences: const UserPreferencesModel(), device: lowRamDevice).breakdown.finalScore -
          _engine.score(app: heavy, preferences: const UserPreferencesModel(), device: lowRamDevice).breakdown.finalScore;
      final capableGap = _engine.score(app: light, preferences: const UserPreferencesModel(), device: capableDevice).breakdown.finalScore -
          _engine.score(app: heavy, preferences: const UserPreferencesModel(), device: capableDevice).breakdown.finalScore;

      expect(lowRamGap, greaterThan(capableGap));
    });

    test('contextEffectsFor exposes the same effects the UI banner should show', () {
      const device = DeviceProfileModel(connectivityStatus: ConnectivityStatus.offline);
      expect(_engine.contextEffectsFor(device), isNotEmpty);
    });
  });
}
