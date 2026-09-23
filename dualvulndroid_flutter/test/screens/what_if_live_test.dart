import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/repositories/app_interaction_repository.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/what_if_simulator_screen.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

/// What-If ranks LIVE category results (backend response shape, mocked
/// transport) with availability-aware scoring and tri-state constraints,
/// and never changes the saved profile on its own.

int _searches = 0;

http.Client _backend() => MockClient((request) async {
      if (request.url.path.contains('/smartapp/apps/search')) {
        _searches++;
        return http.Response(
          jsonEncode({
            'apps': [
              {'id': 'com.ads', 'name': 'AdsApp', 'packageName': 'com.ads', 'rating': 4.9, 'hasAds': true, 'realData': true, 'source': 'google_play'},
              {'id': 'com.unknown', 'name': 'UnknownApp', 'packageName': 'com.unknown', 'rating': 4.2, 'realData': true, 'source': 'google_play'},
            ],
            'source': 'google_play',
            'isLiveData': true,
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      }
      return http.Response('{}', 404);
    });

Future<void> _settle(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
  await tester.pumpAndSettle();
}

Future<void> _reveal(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(finder, 150, scrollable: find.byType(Scrollable).first);
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    _searches = 0;
  });

  testWidgets('20. constraints use verified data only and What-If never mutates the profile', (tester) async {
    final prefs = PreferencesRepository();
    await tester.pumpWidget(MultiProvider(
      providers: [
        Provider(create: (_) => AppsRepository()),
        Provider(create: (_) => AppRepository(client: _backend(), baseUrl: 'http://test.invalid')),
        ChangeNotifierProvider.value(value: prefs),
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
      child: MaterialApp(theme: AppTheme.light, home: const WhatIfSimulatorScreen()),
    ));
    await _settle(tester);
    expect(_searches, 1, reason: 'live category results, not the demo catalog');
    final savedBefore = prefs.preferences.selectedPreferences;

    await _reveal(tester, find.widgetWithText(FilterChip, 'No ads'));
    await tester.tap(find.widgetWithText(FilterChip, 'No ads'));
    await _settle(tester);

    await _reveal(tester, find.text('UnknownApp'));
    expect(find.text('AdsApp'), findsNothing, reason: 'verified "Contains ads" is excluded');
    expect(find.text('UnknownApp'), findsOneWidget, reason: 'unknown ads status is kept');
    expect(find.text('Not verified: No ads'), findsOneWidget);
    expect(find.text('1 excluded by a verified constraint'), findsOneWidget);

    expect(prefs.preferences.weightOverrides, isNull, reason: 'nothing saved without Apply to Profile');
    expect(prefs.preferences.selectedPreferences, savedBefore);
  });
}
