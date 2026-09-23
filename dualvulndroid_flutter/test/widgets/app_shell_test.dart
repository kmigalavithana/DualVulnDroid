import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/repositories/app_interaction_repository.dart';
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

Widget _wrap(Widget child) {
  return MultiProvider(
    providers: [
      Provider(create: (_) => AppsRepository()),
      Provider(create: (_) => InstalledAppsService()),
      Provider(create: (_) => PlayStoreLauncher()),
      ChangeNotifierProvider(create: (_) => PreferencesRepository()),
      // Never touches a real platform channel (Part: pumpAndSettle would
      // otherwise time out waiting on an indeterminate loading spinner, or
      // leave a pending timer at test teardown) - see FakeDeviceInfoService's
      // own doc comment.
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
    child: MaterialApp(theme: AppTheme.light, home: child),
  );
}

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  testWidgets('AppShell shows the four SmartApp tabs and starts on Home', (tester) async {
    await tester.pumpWidget(_wrap(const AppShell()));
    await tester.pumpAndSettle();

    expect(find.text('Home'), findsOneWidget);
    expect(find.text('Discover'), findsOneWidget);
    expect(find.text('History'), findsOneWidget);
    expect(find.text('Profile'), findsOneWidget);
    expect(find.text('SmartApp'), findsWidgets);
  });

  testWidgets('switching tabs shows the corresponding screen without crashing', (tester) async {
    await tester.pumpWidget(_wrap(const AppShell()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Discover'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.byType(TextField), findsOneWidget);

    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    await tester.tap(find.text('Profile'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('Your Preferences'), findsOneWidget);
  });
}
