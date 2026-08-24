import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// The ONLY place the JWT is persisted (Phase 9, Part 3: "Store JWT
/// securely using flutter_secure_storage. Do not use SharedPreferences
/// for the JWT."). Never logs the token - see AuthRepository, which is
/// the only other class allowed to touch this.
class SecureTokenStorage {
  static const _tokenKey = 'dualvulndroid_jwt';

  final FlutterSecureStorage _storage;

  SecureTokenStorage({FlutterSecureStorage? storage}) : _storage = storage ?? const FlutterSecureStorage();

  Future<void> saveToken(String token) => _storage.write(key: _tokenKey, value: token);

  Future<String?> readToken() => _storage.read(key: _tokenKey);

  Future<void> clear() => _storage.delete(key: _tokenKey);
}
