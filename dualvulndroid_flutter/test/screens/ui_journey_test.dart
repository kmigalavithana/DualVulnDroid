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
import 'package:dualvulndroid_flutter/repositories/evaluation_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/app_detail_screen.dart';
import 'package:dualvulndroid_flutter/screens/evaluation_screen.dart';
import 'package:dualvulndroid_flutter/services/installed_apps_service.dart';
import 'package:dualvulndroid_flutter/services/play_store_launcher.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';
import 'package:dualvulndroid_flutter/widgets/app_shell.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

/// End-to-end UI journeys through the redesigned app, driven against a
/// MockClient that returns the real backend response shape (never a real
/// network call, never a local fake catalog standing in for live data).

const _playUrl = 'https://play.google.com/store/apps/details?id=com.example.noteflow';

Map<String, dynamic> _app(String id, String name, {double? rating, String? url}) => {
      'id': id,
      'name': name,
      'packageName': id,
      'category': 'Notes',
      'developer': 'Example Dev',
      'rating': ?rating,
      'playStoreUrl': ?url,
      'realData': true,
      'source': 'google_play',
    };

http.Client _backend({bool fail = false}) => MockClient((request) async {
      if (fail) return http.Response('{"detail":"Google Play provider error"}', 502);
      if (request.url.path.contains('/smartapp/apps/search')) {
        return http.Response(
          jsonEncode({
            'apps': [
              _app('com.example.noteflow', 'NoteFlow', rating: 4.6, url: _playUrl),
              _app('com.example.jotter', 'Jotter', rating: 4.1),
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

class _RecordingLauncher extends PlayStoreLauncher {
  final List<String> opened = [];
  @override
  Future<bool> open(String url) async {
    opened.add(url);
    return true;
  }
}

Widget _wrap(Widget child, {http.Client? client, PlayStoreLauncher? launcher, PreferencesRepository? prefs}) {
  return MultiProvider(
    providers: [
      Provider(create: (_) => AppsRepository()),
      Provider(create: (_) => AppRepository(client: client ?? _backend(), baseUrl: 'http://test.invalid')),
      Provider(create: (_) => const RecommendationEngine()),
      Provider(create: (_) => InstalledAppsService()),
      Provider<PlayStoreLauncher>(create: (_) => launcher ?? _RecordingLauncher()),
      ChangeNotifierProvider(create: (_) => prefs ?? PreferencesRepository()),
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
      ChangeNotifierProvider(create: (_) => EvaluationRepository()),
    ],
    child: MaterialApp(theme: AppTheme.light, home: child),
  );
}

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pumpAndSettle();
}

Future<void> _tapVisible(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isEmpty) {
    // Lazily-built list: scroll the page's vertical list until it's built.
    final vertical = find.byWidgetPredicate((w) => w is Scrollable && w.axisDirection == AxisDirection.down).hitTestable().first;
    await tester.scrollUntilVisible(finder, 150, scrollable: vertical);
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await _settle(tester);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('Home -> Find Apps -> Discover -> live search -> Your Matches -> App Details -> Open in Google Play', (tester) async {
    final launcher = _RecordingLauncher();
    await tester.pumpWidget(_wrap(const AppShell(), launcher: launcher));
    await _settle(tester);

    await tester.tap(find.text('Find Apps'));
    await _settle(tester);
    expect(find.widgetWithText(TextField, 'Search apps'), findsOneWidget, reason: 'Find Apps switches to the Discover tab');

    await tester.enterText(find.byType(TextField), 'note');
    await tester.pump(const Duration(milliseconds: 500)); // debounce
    await _settle(tester);
    expect(find.text('NoteFlow'), findsOneWidget);
    expect(find.textContaining('% match'), findsWidgets, reason: 'each live result shows its calculated match');

    await tester.tap(find.text('See your matches'));
    await _settle(tester);
    expect(find.text('Your Matches'), findsOneWidget);
    expect(find.text('Based on your preferences and device.'), findsOneWidget);
    expect(find.text('Best match for you'), findsOneWidget);

    await tester.tap(find.text('NoteFlow'));
    await _settle(tester);
    expect(find.text('App Details'), findsOneWidget);
    expect(find.text('Live Google Play data'), findsOneWidget);

    await tester.tap(find.text('Open in Google Play'));
    await _settle(tester);
    expect(launcher.opened, [_playUrl], reason: 'only the URL the backend returned is opened');

    await tester.ensureVisible(find.text('Why this app?'));
    expect(tester.takeException(), isNull);
  });

  testWidgets('Why this app? shows exactly the engine\'s calculated factor points', (tester) async {
    final app = AppInfo.fromSmartAppJson(_app('com.example.noteflow', 'NoteFlow', rating: 4.6, url: _playUrl));
    await tester.pumpWidget(_wrap(AppDetailScreen(app: app)));
    await _settle(tester);
    await tester.ensureVisible(find.text('Why this app?'));

    final prefs = tester.element(find.byType(AppDetailScreen)).read<PreferencesRepository>().preferences;
    final device = tester.element(find.byType(AppDetailScreen)).read<DeviceProfileRepository>().profile;
    final result = const RecommendationEngine().score(app: app, preferences: prefs, device: device);
    for (final factor in result.explanationFactors.where((f) => f.available)) {
      expect(find.text('+${factor.earnedPoints}'), findsWidgets, reason: '${factor.label} must show its real points');
      expect(find.text(' / ${factor.maxPoints}'), findsWidgets);
    }
    final unavailable = result.explanationFactors.where((f) => !f.available).length;
    expect(find.text('Not enough verified data'), findsNWidgets(unavailable),
        reason: 'unverified factors say so instead of showing points');
    expect(find.text('Based on ${result.availableFactorCount} of 5 factors'), findsOneWidget);
    expect(find.text('${result.matchPercent}% match for your current profile'), findsOneWidget);
  });

  testWidgets('Open in Google Play is disabled with an explanation when there is no URL and no verified package', (tester) async {
    final launcher = _RecordingLauncher();
    final app = AppInfo.fromSmartAppJson({'id': 'jotter', 'name': 'Jotter', 'realData': true, 'source': 'google_play'});
    await tester.pumpWidget(_wrap(AppDetailScreen(app: app), launcher: launcher));
    await _settle(tester);

    final button = tester.widget<FilledButton>(find.ancestor(of: find.text('Open in Google Play'), matching: find.byWidgetPredicate((w) => w is FilledButton)));
    expect(button.onPressed, isNull);
    expect(find.text('No verified Play Store link available.'), findsOneWidget);
    expect(launcher.opened, isEmpty);
  });

  testWidgets('Home -> Explore Alternatives -> category -> live alternatives -> App Details', (tester) async {
    await tester.pumpWidget(_wrap(const AppShell()));
    await _settle(tester);

    await _tapVisible(tester, find.text('Explore Alternatives'));
    expect(find.text('Find Better Matches'), findsOneWidget);

    await tester.tap(find.widgetWithText(ChoiceChip, AppCategory.notes.label));
    await _settle(tester);
    expect(find.text('2 alternatives'), findsOneWidget);

    await _tapVisible(tester, find.text('Jotter'));
    expect(find.text('App Details'), findsOneWidget);
  });

  testWidgets('Alternatives for a specific app are compared against it and exclude it', (tester) async {
    final current = AppInfo.fromSmartAppJson(_app('com.example.noteflow', 'NoteFlow', rating: 4.6, url: _playUrl));
    await tester.pumpWidget(_wrap(AppDetailScreen(app: current)));
    await _settle(tester);

    await tester.tap(find.text('Find Alternatives'));
    await _settle(tester);
    expect(find.text('ALTERNATIVES FOR'), findsOneWidget);
    expect(find.text('1 alternative'), findsOneWidget, reason: 'the current app itself is never listed');
    expect(find.text('Jotter'), findsOneWidget);
  });

  testWidgets('Profile -> Explore What-If: nothing is saved until Apply to Profile', (tester) async {
    final prefs = PreferencesRepository();
    await tester.pumpWidget(_wrap(const AppShell(), prefs: prefs));
    await _settle(tester);

    await tester.tap(find.text('Profile'));
    await _settle(tester);
    expect(find.text('Your Preferences'), findsOneWidget);
    await _tapVisible(tester, find.text('EXPLORE WHAT-IF'));
    expect(find.text('Explore What-If'), findsOneWidget);

    FilledButton applyButton() => tester.widget<FilledButton>(
        find.ancestor(of: find.text('Apply to Profile'), matching: find.byWidgetPredicate((w) => w is FilledButton)));
    expect(applyButton().onPressed, isNull, reason: 'nothing to apply before a change');

    final slider = find.byType(Slider).first;
    final box = tester.getRect(slider);
    await tester.tapAt(Offset(box.right - 12, box.center.dy)); // Preferences -> High
    await _settle(tester);
    expect(find.text('High'), findsOneWidget);
    expect(prefs.preferences.weightOverrides, isNull, reason: 'moving a slider must not save anything');

    await tester.tap(find.text('Apply to Profile'));
    await _settle(tester);
    expect(prefs.preferences.weightOverrides, isNotNull, reason: 'only the explicit Apply persists priorities');
  });

  testWidgets('Favorites empty state leads back to Discover', (tester) async {
    await tester.pumpWidget(_wrap(const AppShell()));
    await _settle(tester);

    await _tapVisible(tester, find.text('Favorites'));
    expect(find.text('Save apps you want to compare later.'), findsOneWidget);

    await tester.tap(find.text('Discover Apps'));
    await _settle(tester);
    expect(find.widgetWithText(TextField, 'Search apps'), findsOneWidget);
  });

  testWidgets('Discover shows a clear error with Retry when live data can\'t load', (tester) async {
    await tester.pumpWidget(_wrap(const AppShell(), client: _backend(fail: true)));
    await _settle(tester);
    await tester.tap(find.text('Discover'));
    await _settle(tester);

    await tester.enterText(find.byType(TextField), 'note');
    await tester.pump(const Duration(milliseconds: 500));
    await _settle(tester);
    expect(find.text('Unable to load live app data.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
    expect(find.text('NoteFlow'), findsNothing, reason: 'no fake content on error');
  });

  testWidgets('Evaluation shows "No evaluation data available." instead of fake metrics', (tester) async {
    await tester.pumpWidget(_wrap(const EvaluationScreen()));
    await _settle(tester);
    expect(find.text('No evaluation data available.'), findsWidgets);
    expect(find.textContaining('Precision@'), findsNothing);
  });

  for (final size in const [Size(320, 568), Size(360, 800), Size(390, 844)]) {
    testWidgets('Home, Discover, History, Profile and App Details fit ${size.width.toInt()}x${size.height.toInt()} without overflow', (tester) async {
      tester.view.physicalSize = size * 2;
      tester.view.devicePixelRatio = 2;
      addTearDown(tester.view.reset);

      await tester.pumpWidget(_wrap(const AppShell()));
      await _settle(tester);
      expect(tester.takeException(), isNull);
      for (final tab in ['Discover', 'History', 'Profile']) {
        await tester.tap(find.text(tab).last);
        await _settle(tester);
        expect(tester.takeException(), isNull, reason: '$tab overflowed');
      }

      final app = AppInfo.fromSmartAppJson(_app('com.example.noteflow', 'NoteFlow with a very long application name', rating: 4.6, url: _playUrl));
      await tester.pumpWidget(_wrap(AppDetailScreen(app: app)));
      await _settle(tester);
      expect(tester.takeException(), isNull);
    });
  }
}
