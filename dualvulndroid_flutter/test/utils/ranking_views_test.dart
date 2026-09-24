import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/recommendation_result_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/recommendation_results_screen.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';
import 'package:dualvulndroid_flutter/utils/ranking_views.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

Map<String, dynamic> _json(String pkg, {double? rating, int? reviews, bool? isFree, bool? hasAds}) => {
      'id': pkg,
      'name': pkg,
      'packageName': pkg,
      'category': 'Productivity',
      'rating': ?rating,
      'reviewCount': ?reviews,
      'isFree': ?isFree,
      'hasAds': ?hasAds,
      'realData': true,
      'source': 'google_play',
    };

// "top.rated" has the best rating but shows ads; "free.noads" is rated lower
// but meets the user's verified preferences.
final _apps = [
  _json('top.rated', rating: 4.9, reviews: 900, isFree: false, hasAds: true),
  _json('free.noads', rating: 4.2, reviews: 50, isFree: true),
  _json('mid', rating: 4.5, reviews: 300),
  _json('unrated'),
];

const _prefs = UserPreferencesModel(selectedPreferences: {AppPreference.free, AppPreference.noAds});
const _device = DeviceProfileModel(androidSdkInt: 36, ramTotalMb: 4096);

List<RecommendationResult> _forYou() =>
    const RecommendationEngine().rank(apps: _apps.map(AppInfo.fromSmartAppJson).toList(), preferences: _prefs, device: _device);

void main() {
  group('popularOrder / positionShifts', () {
    test('Popular = Google Play rating, then review count; unrated last; no SmartApp score used', () {
      final popular = popularOrder(_forYou()).map((r) => r.app.packageName).toList();
      expect(popular, ['top.rated', 'mid', 'free.noads', 'unrated']);
    });

    test('ties on rating fall back to review count, then name', () {
      final results = const RecommendationEngine().rank(
        apps: [_json('b', rating: 4.0, reviews: 10), _json('a', rating: 4.0, reviews: 10), _json('c', rating: 4.0, reviews: 99)]
            .map(AppInfo.fromSmartAppJson)
            .toList(),
        preferences: const UserPreferencesModel(),
        device: _device,
      );
      expect(popularOrder(results).map((r) => r.app.packageName), ['c', 'a', 'b']);
    });

    test('shift = popular position - personalized position (positive = higher for you)', () {
      final forYou = _forYou();
      final shifts = positionShifts(forYou);
      final popular = popularOrder(forYou);
      for (var i = 0; i < forYou.length; i++) {
        final key = shiftKey(forYou[i]);
        expect(shifts[key], popular.indexWhere((r) => shiftKey(r) == key) - i);
      }
      expect(shifts['free.noads'], greaterThan(0), reason: 'verified free + no-ads fit lifts it above its popularity');
      expect(shifts.values.fold<int>(0, (a, b) => a + b), 0);
    });
  });

  group('Your Matches: For you / Popular toggle', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    testWidgets('switching views reorders the same apps, keeps each match %, and records history once', (tester) async {
      final prefs = PreferencesRepository();
      await tester.runAsync(() async {
        while (prefs.isLoading) {
          await Future<void>.delayed(const Duration(milliseconds: 5));
        }
        await prefs.setPreferences(_prefs.selectedPreferences);
      });
      final history = HistoryRepository();
      final candidates = _apps.map(AppInfo.fromSmartAppJson).toList();
      await tester.pumpWidget(MultiProvider(
        providers: [
          Provider(create: (_) => AppRepository(client: MockClient((_) async => http.Response(jsonEncode({'apps': []}), 200)), baseUrl: 'http://t')),
          ChangeNotifierProvider.value(value: prefs),
          ChangeNotifierProvider(
            create: (_) => DeviceProfileRepository(
              service: const FakeDeviceInfoService(profile: _device),
              batteryService: const FakeBatteryService(),
              connectivityService: const FakeConnectivityService(),
            ),
          ),
          ChangeNotifierProvider.value(value: history),
          ChangeNotifierProvider(create: (_) => FavoritesRepository()),
        ],
        child: MaterialApp(theme: AppTheme.light, home: RecommendationResultsScreen(candidates: candidates, searchLabel: '"notes"')),
      ));
      await tester.pumpAndSettle();

      double top(String name) => tester.getTopLeft(find.text(name)).dy;
      Future<void> reveal(String name) => tester.scrollUntilVisible(find.text(name), 150, scrollable: find.byType(Scrollable).first);

      // For you: the verified free, ad-free app beats the higher-rated one.
      expect(find.text('Best match for you'), findsOneWidget);
      expect(find.textContaining('apps moved when ranked for you'), findsOneWidget);
      await reveal('top.rated');
      expect(top('free.noads'), lessThan(top('top.rated')));
      final forYouPercents = {for (final r in _forYou()) r.app.packageName!: r.matchPercent};

      await tester.drag(find.byType(Scrollable).first, const Offset(0, 2000));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Popular'));
      await tester.pumpAndSettle();

      expect(find.text('Highest rated on Google Play'), findsOneWidget);
      expect(find.textContaining('ranked by Google Play rating only'), findsOneWidget);
      await reveal('free.noads');
      expect(top('top.rated'), lessThan(top('free.noads')));
      expect(find.textContaining('for you'), findsWidgets, reason: 'each card shows its personalized position');
      // Scores are unchanged - only the order differs.
      expect(find.textContaining('${forYouPercents['free.noads']}% match for your current profile'), findsWidgets);

      expect(history.entries, hasLength(1), reason: 'toggling views never records extra history');
      expect(history.entries.single.recommendedApps.first.packageName, _forYou().first.app.packageName,
          reason: 'history keeps the personalized order');
    });
  });
}
