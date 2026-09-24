import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/engines/constraint_engine.dart';
import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';

/// Availability-aware scoring over verified metadata: unknown data is
/// never scored as good or bad, unavailable factors' weights are
/// redistributed proportionally, and hard constraints are tri-state.

const _engine = RecommendationEngine();
const _device = DeviceProfileModel(androidSdkInt: 36, androidRelease: '16', ramTotalMb: 1946, isLowRamDevice: false);

AppInfo _live({
  String id = 'com.example.app',
  double? rating = 4.5,
  bool? isFree,
  bool? hasAds,
  int? trackerCount,
  bool? isOpenSource,
  double? sizeMb,
  String? privacyDataSource,
}) =>
    AppInfo(
      id: id,
      name: id,
      packageName: id,
      category: AppCategory.notes,
      iconKey: 'apps_outlined',
      rating: rating,
      isFree: isFree,
      hasAds: hasAds,
      trackerCount: trackerCount,
      isOpenSource: isOpenSource,
      sizeMb: sizeMb,
      privacyDataSource: privacyDataSource,
      isCuratedSample: false,
      isLiveData: true,
      dataSource: 'google_play',
    );

UserPreferencesModel _prefs(Set<AppPreference> p) => UserPreferencesModel(selectedPreferences: p);

void main() {
  group('12. Availability-aware normalization', () {
    test('unavailable factors are dropped and the rest keep their relative weights, summing to 1', () {
      final result = _engine.score(app: _live(isFree: true), preferences: _prefs({AppPreference.free}), device: _device);
      final b = result.breakdown;
      expect(b.available, [true, false, false, false, true], reason: 'preferences + rating verified; device/privacy/resource not');
      expect(b.effectiveWeights.fold<double>(0, (a, w) => a + w), closeTo(1, 1e-9));
      // Preferences 30 : Rating 10 is preserved -> 0.75 / 0.25.
      expect(b.effectiveWeights[0], closeTo(0.30 / 0.40, 1e-9));
      expect(b.effectiveWeights[4], closeTo(0.10 / 0.40, 1e-9));
      expect(b.effectiveWeights[0] / b.effectiveWeights[4], closeTo(3, 1e-9));
      // 100 (free verified) * 0.75 + 90 (4.5 stars) * 0.25.
      expect(result.finalScore, closeTo(100 * 0.75 + 90 * 0.25, 1e-9));
    });

    test('a fully known app keeps the exact 30/25/20/15/10 weights', () {
      final app = AppInfo(
        id: 'demo',
        name: 'Demo',
        category: AppCategory.notes,
        iconKey: 'apps_outlined',
        rating: 4.0,
        trackerCount: 0,
        resourceLevel: ResourceLevel.light,
        isFree: true,
      );
      final b = _engine.score(app: app, preferences: _prefs({AppPreference.free}), device: _device).breakdown;
      expect(b.available, everyElement(isTrue));
      expect(b.effectiveWeights, [0.30, 0.25, 0.20, 0.15, 0.10].map((w) => closeTo(w, 1e-9)).toList());
    });

    test('unknown preferences are left out, not counted as failures', () {
      // 7 preferences selected, only "free" verifiable (true) -> 100%, not 1/7.
      final result = _engine.score(app: _live(isFree: true), preferences: _prefs(AppPreference.values.toSet()), device: _device);
      expect(result.breakdown.preference / result.breakdown.effectiveWeights[0], closeTo(100, 1e-9));
      expect(result.breakdown.evidence[0], 'Based on 1 of your 7 preferences - the rest aren\'t verified');
    });

    test('a verified "no" still counts against the app', () {
      final paid = _engine.score(app: _live(isFree: false), preferences: _prefs({AppPreference.free}), device: _device);
      expect(paid.breakdown.preference, 0);
      expect(paid.breakdown.available[0], isTrue);
      expect(paid.reasons.any((r) => !r.isPositive && r.text.contains('free')), isTrue);
    });

    test('verified evidence differentiates apps that neutral fallbacks used to tie', () {
      final prefs = _prefs({AppPreference.free, AppPreference.noAds, AppPreference.openSource});
      final plain = _engine.score(app: _live(), preferences: prefs, device: _device);
      final open = _engine.score(app: _live(isFree: true, isOpenSource: true), preferences: prefs, device: _device);
      final withAds = _engine.score(app: _live(isFree: true, hasAds: true), preferences: prefs, device: _device);
      expect(open.finalScore, greaterThan(withAds.finalScore));
      expect(plain.availableFactorCount, 1, reason: 'rating only');
    });

    test('nothing verified -> no score is invented', () {
      final result = _engine.score(app: _live(rating: null), preferences: _prefs({}), device: const DeviceProfileModel());
      expect(result.hasVerifiedFactors, isFalse);
      expect(result.matchPercent, 0);
      expect(result.breakdown.context, 0);
    });

    test('ranking puts verified-evidence results in order and unscorable apps last', () {
      final ranked = _engine.rank(
        apps: [_live(id: 'none', rating: null), _live(id: 'good', rating: 4.8), _live(id: 'ok', rating: 3.0)],
        preferences: _prefs({}),
        device: _device,
      );
      expect(ranked.map((r) => r.app.id), ['good', 'ok', 'none']);
    });
  });

  group('13-15. Hard constraints are tri-state', () {
    const engine = ConstraintEngine();
    const noAds = HardConstraints(noAds: true, openSourceOnly: true);

    test('verified pass keeps the app with nothing unverified', () {
      final app = _live(hasAds: false, isOpenSource: true);
      expect(engine.passes(app, noAds, _device), isTrue);
      expect(engine.unverifiedConstraints(app, noAds), isEmpty);
    });

    test('verified fail excludes the app', () {
      final app = _live(hasAds: true, isOpenSource: true);
      expect(engine.passes(app, noAds, _device), isFalse);
      expect(engine.failedConstraints(app, noAds, _device), ['Contains ads']);
    });

    test('unknown keeps the app and reports "not verified" - never treated as false', () {
      final app = _live(isOpenSource: true); // hasAds unknown
      expect(engine.passes(app, noAds, _device), isTrue);
      expect(engine.unverifiedConstraints(app, noAds), ['No ads']);
      final ranked = _engine.rank(apps: [app], preferences: _prefs({}), device: _device, constraints: noAds);
      expect(ranked.single.unverifiedConstraints, ['No ads']);
    });

    test('low storage uses a real size only', () {
      const low = HardConstraints(maxSizeMb: 30);
      expect(engine.passes(_live(sizeMb: 12), low, _device), isTrue);
      expect(engine.passes(_live(sizeMb: 80), low, _device), isFalse);
      expect(engine.unverifiedConstraints(_live(), low), ['Low storage']);
    });
  });

  group('16. Explanations show verified / unverified state', () {
    test('Exodus-verified privacy is attributed; unavailable factors have no points', () {
      final result = _engine.score(
        app: _live(trackerCount: 0, privacyDataSource: 'exodus'),
        preferences: _prefs({}),
        device: _device,
      );
      final factors = result.explanationFactors;
      expect(factors[2].available, isTrue);
      expect(factors[2].evidence, 'Verified by εxodus');
      expect(factors[4].evidence, 'Google Play rating');
      for (final f in factors.where((f) => !f.available)) {
        expect(f.earnedPoints, 0);
        expect(f.maxPoints, 0);
      }
      final available = factors.where((f) => f.available);
      expect(available.fold<int>(0, (a, f) => a + f.maxPoints), 100);
      expect(available.fold<int>(0, (a, f) => a + f.earnedPoints) + result.contextAdjustmentPoints, result.matchPercent);
    });
  });

  group('11. Metadata coverage + parsing', () {
    test('coverage counts only verified attributes (7)', () {
      expect(_live().metadataCoverage, closeTo(1 / 7, 1e-9));
      expect(_live(isFree: true, hasAds: true, trackerCount: 3).metadataCoverage, closeTo(4 / 7, 1e-9));
    });

    test('backend JSON: verified fields parsed, missing ones stay null', () {
      final app = AppInfo.fromSmartAppJson({
        'id': 'com.x',
        'name': 'X',
        'packageName': 'com.x',
        'rating': 4.1,
        'isFree': false,
        'price': r'$2.99',
        'hasAds': null,
        'trackerCount': 2,
        'trackerNames': ['AppsFlyer'],
        'privacyDataSource': 'exodus',
        'isOpenSource': true,
        'license': 'MIT',
        'antiFeatures': ['NonFreeNet'],
        'fdroidAvailable': true,
        'metadataSources': ['google_play', 'exodus', 'fdroid'],
        'realData': true,
        'source': 'google_play',
      });
      expect(app.isFree, isFalse);
      expect(app.price, r'$2.99');
      expect(app.hasAds, isNull);
      expect(app.supportsOffline, isNull);
      expect(app.sizeMb, isNull);
      expect(app.trackerNames, ['AppsFlyer']);
      expect(app.license, 'MIT');
      expect(app.metadataSources, ['google_play', 'exodus', 'fdroid']);
      expect(app.preferenceStatus(AppPreference.noAds), isNull);
      expect(app.preferenceStatus(AppPreference.free), isFalse);
    });

    test('a refreshed copy keeps verified metadata the search result had', () {
      final search = _live(trackerCount: 1, privacyDataSource: 'exodus', isFree: true);
      final refreshed = _live(rating: 4.7);
      final merged = refreshed.mergedWith(search);
      expect(merged.trackerCount, 1);
      expect(merged.isFree, isTrue);
      expect(merged.rating, 4.7);
    });
  });
}
