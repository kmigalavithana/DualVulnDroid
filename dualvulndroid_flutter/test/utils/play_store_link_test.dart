import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/app_interaction_repository.dart';
import 'package:dualvulndroid_flutter/repositories/app_repository.dart';
import 'package:dualvulndroid_flutter/repositories/device_profile_repository.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/repositories/feedback_repository.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/screens/app_detail_screen.dart';
import 'package:dualvulndroid_flutter/services/play_store_launcher.dart';
import 'package:dualvulndroid_flutter/theme/app_theme.dart';
import 'package:dualvulndroid_flutter/utils/play_store_link.dart';

import '../helpers/fake_battery_service.dart';
import '../helpers/fake_connectivity_service.dart';
import '../helpers/fake_device_info_service.dart';

AppInfo _live({String? package, String? url}) => AppInfo.fromSmartAppJson({
      'id': package ?? 'no-package',
      'name': 'Live App',
      'packageName': ?package,
      'playStoreUrl': ?url,
      'realData': true,
      'source': 'google_play',
    });

class _RecordingLauncher extends PlayStoreLauncher {
  final List<String> opened = [];
  @override
  Future<bool> open(String url) async {
    opened.add(url);
    return true;
  }
}

Widget _details(AppInfo app, PlayStoreLauncher launcher) => MultiProvider(
      providers: [
        // Details re-fetch returns 404 -> the screen keeps the app it was given.
        Provider(create: (_) => AppRepository(client: MockClient((_) async => http.Response('{}', 404)), baseUrl: 'http://test.invalid')),
        Provider<PlayStoreLauncher>.value(value: launcher),
        ChangeNotifierProvider(create: (_) => PreferencesRepository()),
        ChangeNotifierProvider(
          create: (_) => DeviceProfileRepository(
            service: const FakeDeviceInfoService(),
            batteryService: const FakeBatteryService(),
            connectivityService: const FakeConnectivityService(),
          ),
        ),
        ChangeNotifierProvider(create: (_) => FavoritesRepository()),
        ChangeNotifierProvider(create: (_) => FeedbackRepository()),
        ChangeNotifierProvider(create: (_) => AppInteractionRepository()),
      ],
      child: MaterialApp(theme: AppTheme.light, home: AppDetailScreen(app: app)),
    );

void main() {
  group('resolvePlayStoreUrl', () {
    test('1. the URL the live provider returned is used exactly', () {
      const returned = 'https://play.google.com/store/apps/details?id=com.example.app&hl=en';
      expect(resolvePlayStoreUrl(_live(package: 'com.example.app', url: returned)), returned);
    });

    test('2. no returned URL + verified live package -> standard package URL', () {
      expect(
        resolvePlayStoreUrl(_live(package: 'com.socialnmobile.dictapps.notepad.color.note')),
        'https://play.google.com/store/apps/details?id=com.socialnmobile.dictapps.notepad.color.note',
      );
      expect(resolvePlayStoreUrl(_live(package: 'org.my_app.v2')), 'https://play.google.com/store/apps/details?id=org.my_app.v2');
    });

    test('3. missing or invalid package name -> no link', () {
      expect(resolvePlayStoreUrl(_live()), isNull);
      expect(resolvePlayStoreUrl(_live(package: 'My Notes App')), isNull, reason: 'an app name is never a package');
      expect(resolvePlayStoreUrl(_live(package: 'notes')), isNull, reason: 'not a dotted application id');
      expect(resolvePlayStoreUrl(_live(package: 'com.x&id=evil')), isNull, reason: 'no injection into the query string');
    });

    test('4. demo / curated apps never get a fabricated URL', () {
      const demo = AppInfo(id: 'noteflow', name: 'NoteFlow', packageName: 'com.example.noteflow', category: AppCategory.notes, iconKey: 'apps_outlined');
      expect(demo.isCuratedSample, isTrue);
      expect(resolvePlayStoreUrl(demo), isNull);
      // Live flag without the Google Play source is not enough either.
      final otherSource = AppInfo.fromSmartAppJson({'id': 'a', 'name': 'A', 'packageName': 'com.a.b', 'realData': true, 'source': 'other'});
      expect(resolvePlayStoreUrl(otherSource), isNull);
    });
  });

  group('5. Open in Google Play button', () {
    setUp(() => SharedPreferences.setMockInitialValues({}));

    Future<void> tapOpen(WidgetTester tester) async {
      await tester.tap(find.text('Open in Google Play'));
      await tester.pumpAndSettle();
    }

    testWidgets('launches the provider URL when one was returned', (tester) async {
      final launcher = _RecordingLauncher();
      const url = 'https://play.google.com/store/apps/details?id=com.example.app';
      await tester.pumpWidget(_details(_live(package: 'com.example.app', url: url), launcher));
      await tester.pumpAndSettle();
      await tapOpen(tester);
      expect(launcher.opened, [url]);
    });

    testWidgets('launches the package URL for a verified live package without a returned URL', (tester) async {
      final launcher = _RecordingLauncher();
      await tester.pumpWidget(_details(_live(package: 'com.example.notes'), launcher));
      await tester.pumpAndSettle();
      expect(find.text('No verified Play Store link available.'), findsNothing);
      await tapOpen(tester);
      expect(launcher.opened, ['https://play.google.com/store/apps/details?id=com.example.notes']);
    });

    testWidgets('live app without a package: disabled with the explanation', (tester) async {
      final launcher = _RecordingLauncher();
      await tester.pumpWidget(_details(_live(), launcher));
      await tester.pumpAndSettle();
      final button = tester.widget<FilledButton>(find.ancestor(of: find.text('Open in Google Play'), matching: find.byWidgetPredicate((w) => w is FilledButton)));
      expect(button.onPressed, isNull);
      expect(find.text('No verified Play Store link available.'), findsOneWidget);
      expect(launcher.opened, isEmpty);
    });
  });
}
