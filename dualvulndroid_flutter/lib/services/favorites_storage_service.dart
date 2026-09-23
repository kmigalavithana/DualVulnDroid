import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_snapshot_model.dart';

/// Local-only persistence for the user's favorited apps (Part 13). No
/// account/login - favorites live only on this device, same mechanism as
/// preferences/history. Stores a real [AppSnapshot] per favorite (not
/// just an id) so a real Google Play app - with no local catalog entry
/// to resolve an id back against - can still be displayed later.
class FavoritesStorageService {
  static const _key = 'smartapp.favorites.v2';

  Future<Map<String, AppSnapshot>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key);
    if (raw == null) return const {};
    final result = <String, AppSnapshot>{};
    for (final item in raw) {
      try {
        final snapshot = AppSnapshot.fromJson(jsonDecode(item) as Map<String, dynamic>);
        result[snapshot.packageName] = snapshot;
      } catch (_) {
        // Skip a single corrupted entry rather than losing the whole list.
      }
    }
    return result;
  }

  Future<void> save(Map<String, AppSnapshot> favorites) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_key, favorites.values.map((s) => jsonEncode(s.toJson())).toList());
  }
}
