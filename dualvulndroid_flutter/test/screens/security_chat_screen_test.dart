import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/core/secure_token_storage.dart';
import 'package:dualvulndroid_flutter/repositories/auth_repository.dart';
import 'package:dualvulndroid_flutter/repositories/chat_repository.dart';
import 'package:dualvulndroid_flutter/screens/security_chat_screen.dart';
import 'package:dualvulndroid_flutter/services/auth_api_service.dart';
import 'package:dualvulndroid_flutter/services/chat_api_service.dart';

import '../helpers/fake_http.dart';

/// In-memory stand-in for SecureTokenStorage (same pattern used across the
/// other screen tests) - avoids the real flutter_secure_storage platform
/// channel in a widget test.
class _FakeTokenStorage extends SecureTokenStorage {
  String? _token;
  @override
  Future<void> saveToken(String token) async => _token = token;
  @override
  Future<String?> readToken() async => _token;
  @override
  Future<void> clear() async => _token = null;
}

/// SecurityChatScreen only loads history for an authenticated user
/// (currentUser != null), and AuthRepository only ever sets currentUser via
/// a real login() call (restoreSession() alone restores the token but not
/// the user object) - so every test needing history must actually log in
/// through a real fake /login route first, exactly as a real session would.
Widget _wrap(Widget child, {required List<FakeRoute> routes, bool loggedIn = true}) {
  final allRoutes = [
    if (loggedIn)
      FakeRoute(method: 'POST', pathPrefix: '/login', body: {
        'message': 'Login successful.',
        'user': {'id': 1, 'email': 'user@test.com', 'name': 'Test User'},
        'token': 'fake-jwt-token',
      }),
    ...routes,
  ];
  final apiClient = ApiClient(client: buildFakeClient(allRoutes));
  final authRepo = AuthRepository(api: AuthApiService(apiClient), tokenStorage: _FakeTokenStorage());
  if (loggedIn) {
    // Synchronous kick-off is fine: the widget tree's first pumpAndSettle
    // awaits this real (faked-HTTP) future the same as it would await
    // anything else async during startup.
    authRepo.login(email: 'user@test.com', password: 'password');
  }
  return MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: authRepo),
      Provider(create: (_) => ChatRepository(ChatApiService(apiClient))),
    ],
    child: MaterialApp(home: child),
  );
}

void main() {
  group('SecurityChatScreen', () {
    testWidgets('groups real chat history into day separators from real timestamps', (tester) async {
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day, 10);
      final yesterday = today.subtract(const Duration(days: 1));

      await tester.pumpWidget(_wrap(
        const SecurityChatScreen(),
        routes: [
          FakeRoute(method: 'GET', pathPrefix: '/user/chat-history', body: {
            'history': [
              {'question': 'Why is this app high risk?', 'answer': 'It has a known SQL injection finding.', 'created_at': yesterday.toIso8601String()},
              {'question': 'What does CWE-295 mean?', 'answer': 'Improper certificate validation.', 'created_at': today.toIso8601String()},
            ],
          }),
        ],
      ));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      // Real message content from the fake backend response renders verbatim.
      expect(find.text('Why is this app high risk?'), findsOneWidget);
      expect(find.text('It has a known SQL injection finding.'), findsOneWidget);
      expect(find.text('What does CWE-295 mean?'), findsOneWidget);
      // Two distinct real calendar days -> two separators, labeled honestly
      // relative to the real current date, never a fabricated grouping.
      expect(find.text('Today'), findsOneWidget);
      expect(find.text('Yesterday'), findsOneWidget);
    });

    testWidgets('an unauthenticated/empty history shows the suggestion chips, no separators', (tester) async {
      await tester.pumpWidget(_wrap(
        const SecurityChatScreen(),
        routes: const [],
        loggedIn: false,
      ));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Ask about app security, risk, or compatibility.'), findsOneWidget);
      expect(find.text('Today'), findsNothing);
      expect(find.text('Yesterday'), findsNothing);
    });
  });
}
