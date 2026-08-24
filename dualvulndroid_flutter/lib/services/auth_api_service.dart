import '../core/api_client.dart';
import '../models/user_model.dart';

/// Thin wrapper around the real /register and /login endpoints - returns
/// parsed models, never raw HTTP. Token storage/auth-state management is
/// AuthRepository's job, not this service's (Part 1: UI -> Repository ->
/// API Service -> FastAPI).
class AuthApiService {
  final ApiClient _client;

  AuthApiService(this._client);

  Future<void> register({required String name, required String email, required String password}) async {
    await _client.post('/register', body: {'name': name, 'email': email, 'password': password});
  }

  /// Returns (user, token) - matches /login's real {message, user, token}
  /// response. Throws an ApiException (see api_exceptions.dart) on
  /// failure - a 401 with the backend's real "Invalid email or
  /// password." detail message, surfaced as-is.
  Future<(UserModel, String)> login({required String email, required String password}) async {
    final json = await _client.post('/login', body: {'email': email, 'password': password}) as Map<String, dynamic>;
    final user = UserModel.fromJson(json['user'] as Map<String, dynamic>);
    final token = json['token'] as String;
    return (user, token);
  }
}
