import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/app_interaction_model.dart';

/// Local-only persistence for real "app opened" events (Part 10). Every
/// entry is written only when the user actually opens an app's detail
/// screen - never pre-seeded.
class AppInteractionStorageService {
  static const _key = 'smartapp.app_opens.v1';
  static const _maxEntries = 200;

  Future<List<AppOpenEvent>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key);
    if (raw == null) return const [];
    final events = <AppOpenEvent>[];
    for (final item in raw) {
      try {
        final event = AppOpenEvent.fromJson(jsonDecode(item) as Map<String, dynamic>);
        if (event != null) events.add(event);
      } catch (_) {
        // Skip a single corrupted entry rather than losing the whole list.
      }
    }
    events.sort((a, b) => b.timestamp.compareTo(a.timestamp));
    return events;
  }

  Future<void> append(AppOpenEvent event) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    existing.add(jsonEncode(event.toJson()));
    final trimmed = existing.length > _maxEntries ? existing.sublist(existing.length - _maxEntries) : existing;
    await prefs.setStringList(_key, trimmed);
  }
}
