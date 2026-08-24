import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/core/api_exceptions.dart';
import 'package:dualvulndroid_flutter/core/secure_token_storage.dart';
import 'package:dualvulndroid_flutter/repositories/auth_repository.dart';
import 'package:dualvulndroid_flutter/services/auth_api_service.dart';

import '../helpers/fake_http.dart';

/// In-memory stand-in for SecureTokenStorage - avoids needing to mock
/// the real flutter_secure_storage platform channel in a unit test,
/// while still exercising AuthRepository's real save/read/clear calls.
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
  group('AuthRepository', () {
    // 1. Login success
    test('login success stores the user and the real returned token', () async {
      final client = buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/login', body: {
          'message': 'Login successful.',
          'user': {'id': 1, 'email': 'alice@example.com', 'name': 'Alice'},
          'token': 'real-jwt-token-value',
        }),
      ]);
      final storage = _FakeTokenStorage();
      final repo = AuthRepository(api: AuthApiService(ApiClient(client: client)), tokenStorage: storage);

      await repo.login(email: 'alice@example.com', password: 'correct-password');

      expect(repo.isAuthenticated, isTrue);
      expect(repo.currentUser?.email, 'alice@example.com');
      // 3. JWT storage - the token was actually persisted via SecureTokenStorage.
      expect(await storage.readToken(), 'real-jwt-token-value');
    });

    // 2. Login failure
    test('login failure surfaces the backend real message and leaves auth state unset', () async {
      final client = buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/login', status: 401, body: {'detail': 'Invalid email or password.'}),
      ]);
      final repo = AuthRepository(api: AuthApiService(ApiClient(client: client)), tokenStorage: _FakeTokenStorage());

      await expectLater(
        repo.login(email: 'alice@example.com', password: 'wrong-password'),
        throwsA(isA<UnauthorizedException>().having((e) => e.message, 'message', 'Invalid email or password.')),
      );
      expect(repo.isAuthenticated, isFalse);
      expect(repo.currentUser, isNull);
    });

    // 4. Logout
    test('logout clears user state and the stored token', () async {
      final client = buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/login', body: {
          'message': 'Login successful.',
          'user': {'id': 1, 'email': 'alice@example.com'},
          'token': 'real-jwt-token-value',
        }),
      ]);
      final storage = _FakeTokenStorage();
      final repo = AuthRepository(api: AuthApiService(ApiClient(client: client)), tokenStorage: storage);
      await repo.login(email: 'alice@example.com', password: 'correct-password');

      await repo.logout();

      expect(repo.isAuthenticated, isFalse);
      expect(repo.currentUser, isNull);
      expect(await storage.readToken(), isNull);
    });

    // 16. 401 handling (expired/invalid JWT elsewhere in the app)
    test('handleUnauthorized logs the user out', () async {
      final client = buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/login', body: {
          'message': 'Login successful.',
          'user': {'id': 1, 'email': 'alice@example.com'},
          'token': 'real-jwt-token-value',
        }),
      ]);
      final storage = _FakeTokenStorage();
      final repo = AuthRepository(api: AuthApiService(ApiClient(client: client)), tokenStorage: storage);
      await repo.login(email: 'alice@example.com', password: 'correct-password');

      await repo.handleUnauthorized(const UnauthorizedException());

      expect(repo.isAuthenticated, isFalse);
      expect(await storage.readToken(), isNull);
    });
  });
}
