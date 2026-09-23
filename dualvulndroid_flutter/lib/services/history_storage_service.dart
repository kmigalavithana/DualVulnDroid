import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/history_entry_model.dart';

/// Local-only persistence for recommendation history (Part 14: "Store
/// only real local history. Do not create fake history records."). Every
/// entry is written by RecommendationRepository the moment a real set of
/// results is actually shown to the user - nothing is pre-seeded here.
class HistoryStorageService {
  static const _key = 'smartapp.history.v1';
  static const _maxEntries = 100;

  Future<List<HistoryEntry>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key);
    if (raw == null) return const [];
    final entries = <HistoryEntry>[];
    for (final item in raw) {
      try {
        entries.add(HistoryEntry.fromJson(jsonDecode(item) as Map<String, dynamic>));
      } catch (_) {
        // Skip a single corrupted entry rather than losing the whole list.
      }
    }
    entries.sort((a, b) => b.timestamp.compareTo(a.timestamp));
    return entries;
  }

  Future<void> append(HistoryEntry entry) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    existing.add(jsonEncode(entry.toJson()));
    // Cap growth - this is a lightweight local log, not an archive.
    final trimmed = existing.length > _maxEntries ? existing.sublist(existing.length - _maxEntries) : existing;
    await prefs.setStringList(_key, trimmed);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
