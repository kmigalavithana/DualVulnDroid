import 'package:flutter/foundation.dart';

import '../engines/recommendation_engine.dart';
import '../models/history_entry_model.dart';
import '../models/user_preferences_model.dart';
import '../services/history_storage_service.dart';

/// Holds real, locally-recorded recommendation history (Part 14). An
/// entry is only ever appended when the user genuinely views a set of
/// results (see RecommendationResultsScreen) - never pre-seeded or
/// fabricated.
class HistoryRepository extends ChangeNotifier {
  final HistoryStorageService _storage;

  List<HistoryEntry> _entries = const [];
  bool _loading = true;

  HistoryRepository({HistoryStorageService? storage}) : _storage = storage ?? HistoryStorageService() {
    _load();
  }

  List<HistoryEntry> get entries => _entries;
  bool get isLoading => _loading;

  Future<void> _load() async {
    _entries = await _storage.load();
    _loading = false;
    notifyListeners();
  }

  Future<void> recordDiscovery({
    required AppCategory? category,
    required Set<AppPreference> preferences,
    required int resultCount,
    List<RecommendedAppEntry> recommendedApps = const [],
    DeviceContextSummary deviceContext = const DeviceContextSummary(),
    int scoringVersion = RecommendationEngine.scoringVersion,
  }) async {
    final entry = HistoryEntry(
      id: '${DateTime.now().microsecondsSinceEpoch}',
      category: category,
      preferences: preferences,
      resultCount: resultCount,
      timestamp: DateTime.now(),
      recommendedApps: recommendedApps,
      deviceContext: deviceContext,
      scoringVersion: scoringVersion,
    );
    await _storage.append(entry);
    _entries = [entry, ..._entries];
    notifyListeners();
  }

  Future<void> clear() async {
    await _storage.clear();
    _entries = const [];
    notifyListeners();
  }
}
