import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/app_interaction_repository.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/alternative_finder_screen.dart';
import 'package:dualvulndroid_flutter/screens/app_detail_screen.dart';
import 'package:dualvulndroid_flutter/services/installed_apps_service.dart';
import 'package:dualvulndroid_flutter/services/play_store_launcher.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

/// Find Alternatives keeps the current app and its REAL category in view,
/// searches that category through the existing live flow, and never shows
/// a category no source returned.

const _current = 'com.socialnmobile.dictapps.notepad.color.note';

/// Every /search request's `category` parameter, in order.
final List<String?> _searchedCategories = [];

Map<String, dynamic> _json(String pkg, String name, {String? category, double? rating}) => {
      'id': pkg,
      'name': name,
      'packageName': pkg,
      'category': ?category,
      'rating': ?rating,
      'developer': 'Dev of $name',
      'playStoreUrl': 'https://play.google.com/store/apps/details?id=$pkg',
      'realData': true,
      'source': 'google_play',
    };

http.Client _backend() => MockClient((request) async {
      if (request.url.path.contains('/smartapp/apps/search')) {
        _searchedCategories.add(request.url.queryParameters['category']);
        return http.Response(
          jsonEncode({
            'apps': [
              _json(_current, 'ColorNote Notepad Notes', category: 'Productivity', rating: 4.9),
              _json('com.example.alpha', 'Alpha Notes', category: 'Productivity', rating: 4.6),
              _json('com.example.beta', 'Beta Pad', category: 'Productivity', rating: 4.1),
            ],
            'source': 'google_play',
            'isLiveData': true,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response('{"detail":"not found"}', 404); // details re-fetch: keep what we have
    });

class _NoopLauncher extends PlayStoreLauncher {
  @override
  Future<bool> open(String url) async => true;
}

Widget _wrap(Widget home) => MultiProvider(
      providers: [
        Provider(create: (_) => AppsRepository()),
        Provider(create: (_) => AppRepository(client: _backend(), baseUrl: 'http://test.invalid')),
        Provider(create: (_) => const RecommendationEngine()),
        Provider(create: (_) => InstalledAppsService()),
        Provider<PlayStoreLauncher>(create: (_) => _NoopLauncher()),
        ChangeNotifierProvider(create: (_) => PreferencesRepository()),
        ChangeNotifierProvider(
          create: (_) => DeviceProfileRepository(
            service: const FakeDeviceInfoService(),
            batteryService: const FakeBatteryService(),
            connectivityService: const FakeConnectivityService(),
          ),
        ),
        ChangeNotifierProvider(create: (_) => HistoryRepository()),
        ChangeNotifierProvider(create: (_) => FavoritesRepository()),
        ChangeNotifierProvider(create: (_) => FeedbackRepository()),
        ChangeNotifierProvider(create: (_) => AppInteractionRepository()),
      ],
      child: MaterialApp(theme: AppTheme.light, home: home),
    );

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pumpAndSettle();
}

AppInfo _app(String pkg, String name, {String? category}) =>
    AppInfo.fromSmartAppJson(_json(pkg, name, category: category, rating: 4.9));

/// The category chip's text in the "Alternatives for" card.
Finder _chip(String label) => find.descendant(of: find.byType(AlternativeFinderScreen), matching: find.text(label));

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    _searchedCategories.clear();
  });

  testWidgets('1+2+3+8. App Details -> Find Alternatives shows the app and its real category; Back returns', (tester) async {
    final app = _app(_current, 'ColorNote Notepad Notes', category: 'Productivity');
    await tester.pumpWidget(_wrap(AppDetailScreen(app: app)));
    await _settle(tester);

    await tester.tap(find.text('Find Alternatives'));
    await _settle(tester);

    expect(find.text('Find Better Matches'), findsOneWidget);
    expect(find.text('ALTERNATIVES FOR'), findsOneWidget);
    expect(find.descendant(of: find.byType(AlternativeFinderScreen), matching: find.text('ColorNote Notepad Notes')), findsOneWidget);
    expect(_chip('Productivity'), findsOneWidget, reason: 'the category Google Play returned for this app');
    expect(find.text('Real alternatives based on this category and your current profile.'), findsOneWidget);
    expect(_searchedCategories, ['Productivity'], reason: 'the existing live flow searches that category');

    await tester.pageBack();
    await _settle(tester);
    expect(find.text('App Details'), findsOneWidget);
    expect(find.byType(AlternativeFinderScreen), findsNothing);
  });

  testWidgets('4+9. the category is whatever the source returned - never hardcoded or guessed', (tester) async {
    // An unmapped Play category is shown as-is and searched as-is (not "Other").
    await tester.pumpWidget(_wrap(AlternativeFinderScreen(initialApp: _app('com.fit', 'FitTrack', category: 'Health & Fitness'))));
    await _settle(tester);
    expect(_chip('Health & Fitness'), findsOneWidget);
    expect(_chip('Other'), findsNothing);
    expect(_chip('Notes'), findsNothing);
    expect(_searchedCategories.last, 'Health & Fitness');
  });

  testWidgets('A mapped Play category ("Tools") is shown as returned and searched via its SmartApp category', (tester) async {
    await tester.pumpWidget(_wrap(AlternativeFinderScreen(initialApp: _app('com.tool', 'Toolbox', category: 'Tools'))));
    await _settle(tester);
    expect(_chip('Tools'), findsOneWidget);
    expect(_searchedCategories.last, AppCategory.utilities.label);
  });

  testWidgets('5. missing category shows "Not verified" and search continues with the existing fallback', (tester) async {
    await tester.pumpWidget(_wrap(AlternativeFinderScreen(initialApp: _app('com.nocat', 'NoCat App'))));
    await _settle(tester);
    expect(find.text('Not verified'), findsOneWidget);
    expect(_chip('Other'), findsNothing, reason: 'SmartApp\'s internal fallback is never shown as a real category');
    expect(find.textContaining('didn\'t return a category'), findsOneWidget);
    expect(_searchedCategories.last, AppCategory.other.label, reason: 'existing fallback search behavior');
  });

  testWidgets('6+7. alternatives are the live results (current app excluded) with unchanged engine scores', (tester) async {
    await tester.pumpWidget(_wrap(AlternativeFinderScreen(initialApp: _app(_current, 'ColorNote Notepad Notes', category: 'Productivity'))));
    await _settle(tester);

    expect(find.text('2 alternatives'), findsOneWidget);
    expect(find.text('Alpha Notes'), findsOneWidget);
    await tester.ensureVisible(find.text('Beta Pad'));
    expect(find.text('Beta Pad'), findsOneWidget);

    const engine = RecommendationEngine();
    for (final (pkg, name, rating) in [('com.example.alpha', 'Alpha Notes', 4.6), ('com.example.beta', 'Beta Pad', 4.1)]) {
      final expected = engine.score(
        app: AppInfo.fromSmartAppJson(_json(pkg, name, category: 'Productivity', rating: rating)),
        preferences: const UserPreferencesModel(),
        device: const FakeDeviceInfoService().profile,
      );
      expect(
        find.textContaining('${expected.matchPercent}% match for your current profile'),
        findsWidgets,
        reason: '$name keeps its engine-calculated match',
      );
    }
  });
}
