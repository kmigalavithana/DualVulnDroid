import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/core/secure_token_storage.dart';
import 'package:dualvulndroid_flutter/repositories/auth_repository.dart';
import 'package:dualvulndroid_flutter/repositories/chat_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/screens/dashboard_screen.dart';
import 'package:dualvulndroid_flutter/services/auth_api_service.dart';
import 'package:dualvulndroid_flutter/services/chat_api_service.dart';
import 'package:dualvulndroid_flutter/services/history_api_service.dart';

import '../helpers/fake_http.dart';

/// In-memory stand-in for SecureTokenStorage (same pattern as
/// auth_repository_test.dart) - avoids the real flutter_secure_storage
/// platform channel in a widget test.
class _FakeTokenStorage extends SecureTokenStorage {
  @override
  Future<void> saveToken(String token) async {}
  @override
  Future<String?> readToken() async => null;
  @override
  Future<void> clear() async {}
}

Widget _wrap(Widget child) {
  final apiClient = ApiClient(
    client: buildFakeClient([
      FakeRoute(method: 'GET', pathPrefix: '/user/history', body: {'history': []}),
    ]),
  );
  return MultiProvider(
    providers: [
      ChangeNotifierProvider(
        create: (_) => AuthRepository(api: AuthApiService(apiClient), tokenStorage: _FakeTokenStorage()),
      ),
      Provider(create: (_) => HistoryRepository(HistoryApiService(apiClient))),
      Provider(create: (_) => ChatRepository(ChatApiService(apiClient))),
    ],
    child: MaterialApp(home: child),
  );
}

void main() {
  group('DashboardScreen', () {
    // Home screen must expose an obvious, working entry point into the
    // EXISTING SecurityChatScreen/ChatRepository - not a new chatbot
    // implementation. This regression-tests that the Home FAB actually
    // navigates there, rather than just existing visually.
    testWidgets('the chatbot entry point opens the existing SecurityChatScreen', (tester) async {
      await tester.pumpWidget(_wrap(const DashboardScreen()));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Security Chat'), findsOneWidget);
      expect(find.byTooltip('AI Security Assistant'), findsOneWidget);

      await tester.tap(find.byTooltip('AI Security Assistant'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Security assistant'), findsOneWidget);
    });

    // Phase: UI restyle replaced the single full-width "Search for an
    // application" button with a compact 3-action row (Search Apps /
    // Installed Apps / Upload APK) matching the approved design's Home
    // action row. The underlying navigation target (AppRouter.toSearch)
    // is unchanged - only the label/layout changed, so this test now
    // asserts the new label and that tapping it still opens the real
    // SearchApplicationScreen, rather than the old exact button text.
    testWidgets('the search entry point still opens the real SearchApplicationScreen', (tester) async {
      await tester.pumpWidget(_wrap(const DashboardScreen()));
      await tester.pumpAndSettle();

      expect(find.text('Search Apps'), findsOneWidget);

      await tester.tap(find.text('Search Apps'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Search application'), findsOneWidget);
    });

    testWidgets('Installed Apps is honest, not fabricated results', (tester) async {
      await tester.pumpWidget(_wrap(const DashboardScreen()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Installed Apps'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.textContaining('not available in this version'), findsOneWidget);
      for (final fakeName in ['WhatsApp', 'TikTok', 'Chrome', 'Facebook', 'Instagram']) {
        expect(find.textContaining(fakeName), findsNothing);
      }
    });

    // Flutter APK Scan implementation phase: "Upload APK" used to open the
    // same honest NotAvailableScreen stub as "Installed Apps" - the
    // backend now genuinely scans an uploaded APK for CWE-89/CWE-295
    // (backend/apk_code_scanner.py), so this asserts the real
    // ApkScanScreen opens instead, starting from its pick-a-file state
    // (no upload attempted, so no fabricated scan result is possible).
    testWidgets('Upload APK opens the real ApkScanScreen, not the old stub', (tester) async {
      await tester.pumpWidget(_wrap(const DashboardScreen()));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Upload APK'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.textContaining('not available in this version'), findsNothing);
      expect(find.text('Choose APK'), findsOneWidget);
    });

    testWidgets('the settings entry point opens SettingsScreen', (tester) async {
      await tester.pumpWidget(_wrap(const DashboardScreen()));
      await tester.pumpAndSettle();

      await tester.tap(find.byTooltip('Settings'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Settings'), findsWidgets);
      expect(find.text('Dark (fixed)'), findsOneWidget);
    });
  });
}
