import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/user_preferences_model.dart';

/// Local-only persistence for the user's preferences (Part 4: "Store
/// these preferences locally using a simple appropriate mechanism" /
/// "Do not require login"). SharedPreferences is the standard, simple
/// mechanism for small, non-sensitive user settings like this - nothing
/// here is a secret, so the heavier flutter_secure_storage the old
/// backend-auth build used for JWTs would be the wrong tool.
class PreferencesStorageService {
  static const _key = 'smartapp.user_preferences.v1';

  Future<UserPreferencesModel> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_key);
    if (raw == null) return const UserPreferencesModel();
    try {
      return UserPreferencesModel.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      // Corrupted/unreadable local data must never crash the app - start
      // fresh rather than propagate a parse error to the UI.
      return const UserPreferencesModel();
    }
  }

  Future<void> save(UserPreferencesModel preferences) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, jsonEncode(preferences.toJson()));
  }
}
