import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:provider/provider.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/core/secure_token_storage.dart';
import 'package:dualvulndroid_flutter/repositories/auth_repository.dart';
import 'package:dualvulndroid_flutter/repositories/chat_repository.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/services/auth_api_service.dart';
import 'package:dualvulndroid_flutter/services/chat_api_service.dart';
import 'package:dualvulndroid_flutter/services/history_api_service.dart';
import 'package:dualvulndroid_flutter/widgets/app_shell.dart';

class _FakeTokenStorage extends SecureTokenStorage {
  @override
  Future<void> saveToken(String token) async {}
  @override
  Future<String?> readToken() async => null;
  @override
  Future<void> clear() async {}
}

/// Counts real requests to /user/history, so the lazy-build claim (only
/// the active tab's data is fetched, not all 4 up front) is verified
/// directly rather than assumed - same local-MockClient pattern already
/// used elsewhere in this test suite (chat_repository_test.dart's
/// _CapturingClient) rather than modifying the shared fake_http.dart
/// helper just for one counter.
class _CountingClient {
  int historyCount = 0;

  MockClient build() {
    return MockClient((request) async {
      if (request.method == 'GET' && request.url.path == '/user/history') {
        historyCount++;
        return http.Response(jsonEncode({'history': []}), 200, headers: {'content-type': 'application/json'});
      }
      return http.Response(jsonEncode({'detail': 'unmatched: ${request.method} ${request.url.path}'}), 404);
    });
  }
}

Widget _wrap(Widget child, MockClient client) {
  final apiClient = ApiClient(client: client);
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
  group('AppShell', () {
    testWidgets('shows all 4 nav destinations and the Home FAB remains alongside the Chat tab', (tester) async {
      final client = _CountingClient();
      await tester.pumpWidget(_wrap(const AppShell(), client.build()));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Home'), findsOneWidget);
      expect(find.text('Search'), findsOneWidget);
      expect(find.text('History'), findsOneWidget);
      expect(find.text('Chat'), findsOneWidget);
      // The existing Home FAB is preserved alongside the new Chat tab -
      // not a duplicate chatbot, just a second entry point to the same
      // real screen, matching the app's existing precedent elsewhere.
      expect(find.byTooltip('AI Security Assistant'), findsOneWidget);
    });

    testWidgets('tabs are built lazily - switching to Search/History/Chat only fetches on first visit', (tester) async {
      final client = _CountingClient();
      await tester.pumpWidget(_wrap(const AppShell(), client.build()));
      await tester.pumpAndSettle();

      // Home's own real getHistory() call has already fired once.
      expect(client.historyCount, 1);

      await tester.tap(find.text('Search'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Search for an app by name or package name.'), findsOneWidget);
      // Search tab makes no history call, so the count is unaffected.
      expect(client.historyCount, 1);

      await tester.tap(find.text('History'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('No applications assessed yet.'), findsOneWidget);
      // History tab's own real getHistory() call now fires for the first time.
      expect(client.historyCount, 2);

      await tester.tap(find.text('Chat'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Ask about app security, risk, or compatibility.'), findsOneWidget);

      // Switching back to Home does not re-fetch (state preserved, no flash).
      await tester.tap(find.text('Home'));
      await tester.pumpAndSettle();
      expect(client.historyCount, 2);
    });
  });
}
