import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/core/secure_token_storage.dart';
import 'package:dualvulndroid_flutter/repositories/auth_repository.dart';
import 'package:dualvulndroid_flutter/screens/login_screen.dart';
import 'package:dualvulndroid_flutter/screens/settings_screen.dart';
import 'package:dualvulndroid_flutter/services/auth_api_service.dart';

import '../helpers/fake_http.dart';

class _FakeTokenStorage extends SecureTokenStorage {
  String? _token;
  @override
  Future<void> saveToken(String token) async => _token = token;
  @override
  Future<String?> readToken() async => _token;
  @override
  Future<void> clear() async => _token = null;
}

void main() {
  group('SettingsScreen', () {
    testWidgets('Notifications and Appearance are honest static text, never a working toggle', (tester) async {
      final apiClient = ApiClient(client: buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/login', body: {
          'message': 'Login successful.',
          'user': {'id': 1, 'email': 'user@test.com', 'name': 'Test User'},
          'token': 'fake-jwt-token',
        }),
      ]));
      final authRepo = AuthRepository(api: AuthApiService(apiClient), tokenStorage: _FakeTokenStorage());
      await authRepo.login(email: 'user@test.com', password: 'password');

      await tester.pumpWidget(
        ChangeNotifierProvider.value(
          value: authRepo,
          child: const MaterialApp(home: SettingsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Not available in this version.'), findsOneWidget);
      expect(find.text('Dark (fixed)'), findsOneWidget);
      // No fake toggle of any kind anywhere on this screen.
      expect(find.byType(Switch), findsNothing);
      expect(find.byType(SwitchListTile), findsNothing);
      // Real account data renders, not a placeholder.
      expect(find.text('user@test.com'), findsOneWidget);
    });

    testWidgets('Log out calls the real AuthRepository.logout() and returns to LoginScreen', (tester) async {
      final apiClient = ApiClient(client: buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/login', body: {
          'message': 'Login successful.',
          'user': {'id': 1, 'email': 'user@test.com', 'name': 'Test User'},
          'token': 'fake-jwt-token',
        }),
      ]));
      final tokenStorage = _FakeTokenStorage();
      final authRepo = AuthRepository(api: AuthApiService(apiClient), tokenStorage: tokenStorage);
      await authRepo.login(email: 'user@test.com', password: 'password');
      expect(authRepo.isAuthenticated, isTrue);

      await tester.pumpWidget(
        ChangeNotifierProvider.value(
          value: authRepo,
          child: const MaterialApp(home: SettingsScreen()),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Log out'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(authRepo.isAuthenticated, isFalse);
      expect(await tokenStorage.readToken(), isNull);
      expect(find.byType(LoginScreen), findsOneWidget);
    });
  });
}
