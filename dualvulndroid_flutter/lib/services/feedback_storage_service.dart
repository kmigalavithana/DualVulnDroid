import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/feedback_model.dart';

/// Local-only persistence for explicit user feedback (Part 11). Every
/// entry is written the moment the user actually taps a feedback button -
/// nothing here is pre-seeded or fabricated.
class FeedbackStorageService {
  static const _key = 'smartapp.feedback.v1';
  static const _maxEntries = 500;

  Future<List<FeedbackEntry>> load() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getStringList(_key);
    if (raw == null) return const [];
    final entries = <FeedbackEntry>[];
    for (final item in raw) {
      try {
        final entry = FeedbackEntry.fromJson(jsonDecode(item) as Map<String, dynamic>);
        if (entry != null) entries.add(entry);
      } catch (_) {
        // Skip a single corrupted entry rather than losing the whole list.
      }
    }
    entries.sort((a, b) => b.timestamp.compareTo(a.timestamp));
    return entries;
  }

  Future<void> append(FeedbackEntry entry) async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getStringList(_key) ?? <String>[];
    existing.add(jsonEncode(entry.toJson()));
    final trimmed = existing.length > _maxEntries ? existing.sublist(existing.length - _maxEntries) : existing;
    await prefs.setStringList(_key, trimmed);
  }

  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_key);
  }
}
