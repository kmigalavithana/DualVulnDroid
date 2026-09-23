import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/app_interaction_repository.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/profile_screen.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

/// Profile ("Your Smart Profile") presents real saved preferences, the
/// real device profile and the engine's real weights - these tests pin
/// that nothing shown there is invented and that the controls still work.

Widget _wrap({PreferencesRepository? prefs, DeviceProfileModel? device}) {
  return MultiProvider(
    providers: [
      Provider(create: (_) => AppsRepository()),
      ChangeNotifierProvider(create: (_) => prefs ?? PreferencesRepository()),
      ChangeNotifierProvider(
        create: (_) => DeviceProfileRepository(
          service: device == null ? const FakeDeviceInfoService() : FakeDeviceInfoService(profile: device),
          batteryService: const FakeBatteryService(),
          connectivityService: const FakeConnectivityService(),
        ),
      ),
      ChangeNotifierProvider(create: (_) => HistoryRepository()),
      ChangeNotifierProvider(create: (_) => FavoritesRepository()),
      ChangeNotifierProvider(create: (_) => FeedbackRepository()),
      ChangeNotifierProvider(create: (_) => AppInteractionRepository()),
    ],
    child: MaterialApp(theme: AppTheme.light, home: const ProfileScreen()),
  );
}

/// The page is a lazily-built list: scroll until [finder] is built and on screen.
Future<void> _reveal(WidgetTester tester, Finder finder) async {
  if (finder.evaluate().isEmpty) {
    await tester.scrollUntilVisible(finder, 150, scrollable: find.byType(Scrollable).first);
  }
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('header, summary and every preference (grouped) are shown', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();

    expect(find.text('Your Smart Profile'), findsOneWidget);
    expect(find.text('Your preferences and device context shape every app match.'), findsOneWidget);
    expect(find.text('SMART PROFILE'), findsOneWidget);
    expect(find.text('No preferences selected yet'), findsOneWidget);
    expect(find.text('Device profile detected'), findsOneWidget);
    expect(find.text('Your Preferences'), findsOneWidget);
    for (final group in ['APP EXPERIENCE', 'TRUST & PRIVACY', 'ACCESS']) {
      expect(find.text(group), findsOneWidget);
    }
    for (final preference in AppPreference.values) {
      expect(find.widgetWithText(FilterChip, preference.label), findsOneWidget, reason: '${preference.name} must still be selectable');
    }
  });

  testWidgets('toggling a grouped chip still saves through PreferencesRepository and updates count + insight', (tester) async {
    final prefs = PreferencesRepository();
    await tester.pumpWidget(_wrap(prefs: prefs));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(FilterChip, AppPreference.lightweight.label));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilterChip, AppPreference.privacyFriendly.label));
    await tester.pumpAndSettle();

    expect(prefs.preferences.selectedPreferences, {AppPreference.lightweight, AppPreference.privacyFriendly});
    expect(find.text('2 selected'), findsOneWidget);
    expect(find.text('2 preferences selected'), findsOneWidget);
    await _reveal(tester, find.text('Your profile prioritizes lightweight and privacy-friendly apps.'));
    expect(find.text('Your profile prioritizes lightweight and privacy-friendly apps.'), findsOneWidget,
        reason: 'the insight is derived only from the selected preferences');

    // Survives a reload from storage (same persistence as before).
    final reloaded = PreferencesRepository();
    while (reloaded.isLoading) {
      await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 10)));
    }
    expect(reloaded.preferences.selectedPreferences, {AppPreference.lightweight, AppPreference.privacyFriendly});
  });

  testWidgets('"How your matches are calculated" shows the engine\'s real weights', (tester) async {
    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();

    await _reveal(tester, find.text('How your matches are calculated'));
    await tester.tap(find.text('How your matches are calculated'));
    await tester.pumpAndSettle();

    const w = EngineWeights.defaults;
    for (final weight in [w.preference, w.device, w.privacy, w.resource, w.rating]) {
      expect(find.text('${(weight * 100).round()}%'), findsWidgets);
    }
    expect(find.textContaining('not a rating of the app\'s overall quality'), findsOneWidget);
  });

  testWidgets('saved What-If priorities are what the breakdown shows', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final prefs = PreferencesRepository();
    await tester.runAsync(() async {
      while (prefs.isLoading) {
        await Future<void>.delayed(const Duration(milliseconds: 10));
      }
    });
    final custom = EngineWeightsPriorities.fromPriorities(preference: PriorityLevel.high, rating: PriorityLevel.low);
    await tester.runAsync(() => prefs.setWeightOverrides(custom.toMap()));

    await tester.pumpWidget(_wrap(prefs: prefs));
    await tester.pumpAndSettle();
    await _reveal(tester, find.text('How your matches are calculated'));
    expect(find.text('Using your saved What-If priorities'), findsOneWidget);
    await tester.tap(find.text('How your matches are calculated'));
    await tester.pumpAndSettle();
    expect(find.text('${(custom.preference * 100).round()}%'), findsWidgets);
  });

  testWidgets('device status appears only when derived from real device data', (tester) async {
    await tester.pumpWidget(_wrap(
      device: const DeviceProfileModel(androidSdkInt: 36, androidRelease: '16', ramTotalMb: 1946, isLowRamDevice: false, storageFreeBytes: 14600000000),
    ));
    await tester.pumpAndSettle();
    await _reveal(tester, find.text('Your Device'));
    expect(find.text('Resource-constrained device'), findsOneWidget);
  });

  testWidgets('no device status is invented when the device reported nothing', (tester) async {
    await tester.pumpWidget(_wrap(device: const DeviceProfileModel()));
    await tester.pumpAndSettle();
    expect(find.text('Device profile unavailable'), findsOneWidget);
    await _reveal(tester, find.text('Your Device'));
    expect(find.text('Resource-constrained device'), findsNothing);
  });

  testWidgets('fits a small 320x568 phone without overflow', (tester) async {
    tester.view.physicalSize = const Size(320 * 2, 568 * 2);
    tester.view.devicePixelRatio = 2;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(_wrap());
    await tester.pumpAndSettle();
    await _reveal(tester, find.text('How your matches are calculated'));
    await tester.tap(find.text('How your matches are calculated'));
    await tester.pumpAndSettle();
    await _reveal(tester, find.text('Clear recommendation history'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
}
