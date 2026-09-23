import 'package:flutter/foundation.dart';

import '../models/feedback_model.dart';
import '../services/feedback_storage_service.dart';

/// Holds real, locally-recorded user feedback for the app's lifetime
/// (Part 11). Used as an explicit signal for [AdaptiveSuggestionEngine]
/// and [EvaluationEngine] - never synthesized.
class FeedbackRepository extends ChangeNotifier {
  final FeedbackStorageService _storage;

  List<FeedbackEntry> _entries = const [];
  bool _loading = true;

  FeedbackRepository({FeedbackStorageService? storage}) : _storage = storage ?? FeedbackStorageService() {
    _load();
  }

  List<FeedbackEntry> get entries => _entries;
  bool get isLoading => _loading;

  Future<void> _load() async {
    _entries = await _storage.load();
    _loading = false;
    notifyListeners();
  }

  Future<void> record(String appId, FeedbackType type) async {
    final entry = FeedbackEntry(appId: appId, type: type, timestamp: DateTime.now());
    await _storage.append(entry);
    _entries = [entry, ..._entries];
    notifyListeners();
  }

  /// The most recent feedback entry for [appId], if any - used to show
  /// which button (if any) the user already tapped for this app.
  FeedbackEntry? latestFor(String appId) {
    for (final entry in _entries) {
      if (entry.appId == appId) return entry;
    }
    return null;
  }

  Future<void> clear() async {
    await _storage.clear();
    _entries = const [];
    notifyListeners();
  }
}
