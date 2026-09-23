import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/repositories/app_interaction_repository.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/services/installed_apps_service.dart';
import 'package:dualvulndroid_flutter/services/play_store_launcher.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';
import 'package:dualvulndroid_flutter/widgets/app_shell.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

/// Back navigation: app-bar back and the Android system back button must
/// return to the previous screen/tab, never exit the app from a non-Home
/// tab, and never reset the tab the user returns to.

http.Client _backend() => MockClient((request) async {
      if (request.url.path.contains('/smartapp/apps/search')) {
        return http.Response(
          jsonEncode({
            'apps': [
              {
                'id': 'com.example.noteflow',
                'name': 'NoteFlow',
                'packageName': 'com.example.noteflow',
                'category': 'Notes',
                'rating': 4.6,
                'playStoreUrl': 'https://play.google.com/store/apps/details?id=com.example.noteflow',
                'realData': true,
                'source': 'google_play',
              },
            ],
            'source': 'google_play',
            'isLiveData': true,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response('{"detail":"not found"}', 404);
    });

class _NoopLauncher extends PlayStoreLauncher {
  @override
  Future<bool> open(String url) async => true;
}

Widget _app() => MultiProvider(
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
      child: MaterialApp(theme: AppTheme.light, home: const AppShell()),
    );

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pumpAndSettle();
}

/// The Android system back button.
Future<bool> _systemBack(WidgetTester tester) async {
  final handled = await tester.binding.handlePopRoute();
  await _settle(tester);
  return handled;
}

Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isEmpty) {
    final vertical = find.byWidgetPredicate((w) => w is Scrollable && w.axisDirection == AxisDirection.down).hitTestable().first;
    await tester.scrollUntilVisible(finder, 150, scrollable: vertical);
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await _settle(tester);
}

Finder get _homeHero => find.text('Discover apps that fit you');
Finder get _discoverSearch => find.widgetWithText(TextField, 'Search apps');

Future<void> _search(WidgetTester tester, String query) async {
  await tester.enterText(_discoverSearch, query);
  await tester.pump(const Duration(milliseconds: 500));
  await _settle(tester);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('1+2. Home -> Discover, then the app-bar back arrow returns Home', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);

    await tester.tap(find.text('Find Apps'));
    await _settle(tester);
    expect(_discoverSearch, findsOneWidget);
    expect(find.byType(BackButton), findsOneWidget, reason: '"<- Discover" when reached from Home');

    await tester.tap(find.byType(BackButton));
    await _settle(tester);
    expect(_homeHero, findsOneWidget);
    expect(_discoverSearch, findsNothing);
  });

  testWidgets('7. Android system back on Discover returns Home (does not exit); on Home it exits', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);
    await tester.tap(find.text('Discover'));
    await _settle(tester);

    expect(await _systemBack(tester), isTrue, reason: 'the shell handles back instead of closing the app');
    expect(_homeHero, findsOneWidget);

    expect(await _systemBack(tester), isFalse, reason: 'back on Home is left to Android (leave the app)');
  });

  testWidgets('3. Discover -> Your Matches -> Back returns to Discover with the search intact', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);
    await tester.tap(find.text('Discover'));
    await _settle(tester);
    await _search(tester, 'note');

    await tester.tap(find.text('See your matches'));
    await _settle(tester);
    expect(find.text('Your Matches'), findsOneWidget);

    await tester.pageBack();
    await _settle(tester);
    expect(find.text('Your Matches'), findsNothing);
    expect(find.text('Results for "note"'), findsOneWidget, reason: 'Discover keeps its state');
  });

  testWidgets('4. Your Matches -> App Details -> Back (system) returns to Your Matches', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);
    await tester.tap(find.text('Discover'));
    await _settle(tester);
    await _search(tester, 'note');
    await tester.tap(find.text('See your matches'));
    await _settle(tester);

    await tester.tap(find.text('NoteFlow'));
    await _settle(tester);
    expect(find.text('App Details'), findsOneWidget);

    expect(await _systemBack(tester), isTrue);
    expect(find.text('App Details'), findsNothing);
    expect(find.text('Your Matches'), findsOneWidget);

    expect(await _systemBack(tester), isTrue);
    expect(_discoverSearch, findsOneWidget);
  });

  testWidgets('5. Profile -> What-If -> Back returns to Profile', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);
    await tester.tap(find.text('Profile'));
    await _settle(tester);

    await _tapVisible(tester, find.text('EXPLORE WHAT-IF'));
    expect(find.text('Explore What-If'), findsOneWidget);

    await tester.pageBack();
    await _settle(tester);
    expect(find.text('Explore What-If'), findsNothing);
    expect(find.text('EXPLORE WHAT-IF'), findsOneWidget, reason: 'back on Profile, at the same scroll position');
  });

  testWidgets('6. Home -> Alternatives -> Back returns Home', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);
    await _tapVisible(tester, find.text('Explore Alternatives'));
    expect(find.text('Find Better Matches'), findsOneWidget);

    expect(await _systemBack(tester), isTrue);
    expect(_homeHero, findsOneWidget);
  });

  testWidgets('8. bottom navigation still works, and Back walks the tabs you visited', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);

    await tester.tap(find.text('Discover'));
    await _settle(tester);
    await _search(tester, 'note');
    await tester.tap(find.text('History'));
    await _settle(tester);
    expect(find.text('Recommendation History'), findsOneWidget);
    await tester.tap(find.text('Profile'));
    await _settle(tester);
    expect(find.text('Your Smart Profile'), findsOneWidget);

    expect(await _systemBack(tester), isTrue);
    expect(find.text('Recommendation History'), findsOneWidget);
    expect(await _systemBack(tester), isTrue);
    expect(find.text('Results for "note"'), findsOneWidget, reason: 'returning to a tab never resets it');
    expect(await _systemBack(tester), isTrue);
    expect(_homeHero, findsOneWidget);
    expect(await _systemBack(tester), isFalse);
  });

  testWidgets('Home has no back arrow; Discover opened directly from the nav bar gets one back to Home', (tester) async {
    await tester.pumpWidget(_app());
    await _settle(tester);
    expect(find.byType(BackButton), findsNothing);

    await tester.tap(find.text('Discover'));
    await _settle(tester);
    expect(find.byType(BackButton), findsOneWidget);
  });
}
