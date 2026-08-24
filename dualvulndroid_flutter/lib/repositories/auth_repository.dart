import 'package:flutter/foundation.dart';

import '../core/api_exceptions.dart';
import '../core/secure_token_storage.dart';
import '../models/user_model.dart';
import '../services/auth_api_service.dart';

/// Owns authentication STATE (Part 3/4) - the JWT (via SecureTokenStorage),
/// the current user, and whether the app is authenticated. A
/// ChangeNotifier so the UI (routing, dashboard header, etc.) can react
/// to login/logout without polling. This is the only class that reads or
/// writes the stored token; ApiClient only ever asks it for the current
/// value through the tokenProvider callback wired up in main.dart.
class AuthRepository extends ChangeNotifier {
  final AuthApiService _api;
  final SecureTokenStorage _tokenStorage;

  UserModel? _currentUser;
  String? _token;
  bool _initialized = false;

  AuthRepository({required AuthApiService api, SecureTokenStorage? tokenStorage})
      : _api = api,
        _tokenStorage = tokenStorage ?? SecureTokenStorage();

  UserModel? get currentUser => _currentUser;
  bool get isAuthenticated => _token != null;
  bool get initialized => _initialized;

  /// Called once at startup - restores a previously-stored session (if
  /// any) so the user doesn't have to log in again every launch. Never
  /// logs the token itself.
  Future<void> restoreSession() async {
    _token = await _tokenStorage.readToken();
    _initialized = true;
    notifyListeners();
  }

  Future<String?> currentToken() async => _token;

  Future<void> register({required String name, required String email, required String password}) async {
    await _api.register(name: name, email: email, password: password);
  }

  Future<void> login({required String email, required String password}) async {
    final (user, token) = await _api.login(email: email, password: password);
    _currentUser = user;
    _token = token;
    await _tokenStorage.saveToken(token);
    notifyListeners();
  }

  Future<void> logout() async {
    _currentUser = null;
    _token = null;
    await _tokenStorage.clear();
    notifyListeners();
  }

  /// Call when any API call reports an expired/invalid session (Part 21:
  /// "Handle expired JWT") - clears local state so the UI routes back to
  /// login instead of silently retrying with a dead token.
  Future<void> handleUnauthorized(UnauthorizedException _) async {
    await logout();
  }
}
