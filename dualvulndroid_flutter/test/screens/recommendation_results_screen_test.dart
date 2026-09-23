import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/recommendation_results_screen.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

/// A MockClient standing in for SmartApp's backend (never a real network
/// call in tests) - returns two real-shaped normalized apps for any
/// /smartapp/apps/search request, matching the actual backend response
/// contract (see backend/smartapp/models.py).
http.Client _fakeBackendClient() {
  return MockClient((request) async {
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
              'reviewCount': 9100,
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
}

Widget _wrap(Widget child) {
  return MultiProvider(
    providers: [
      Provider(create: (_) => AppRepository(client: _fakeBackendClient(), baseUrl: 'http://test.invalid')),
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
    ],
    child: MaterialApp(theme: AppTheme.light, home: child),
  );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  group('8. Empty recommendation state', () {
    testWidgets('an empty candidate list shows the honest empty state, never a fabricated card', (tester) async {
      await tester.pumpWidget(_wrap(const RecommendationResultsScreen(candidates: <AppInfo>[], searchLabel: '"nonexistent app"')));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No matches found'), findsOneWidget);
      expect(find.text('Back to Discover'), findsOneWidget);
      // No result card content should be rendered.
      expect(find.text('View App'), findsNothing);
    });

    testWidgets('a non-empty category shows ranked result cards', (tester) async {
      await tester.pumpWidget(_wrap(const RecommendationResultsScreen(category: AppCategory.notes)));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No matches found'), findsNothing);
      expect(find.textContaining('% match for your current profile'), findsWidgets);
    });
  });
}
