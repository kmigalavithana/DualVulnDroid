import 'package:flutter/foundation.dart';

import '../models/app_interaction_model.dart';
import '../models/app_snapshot_model.dart';
import '../services/app_interaction_storage_service.dart';

/// Holds real, locally-recorded "app opened" events for the app's
/// lifetime (Part 10). Feeds [AdaptiveSuggestionEngine] alongside
/// [HistoryRepository] (categories/preferences searched) and
/// [FavoritesRepository] - never a separately-invented signal.
class AppInteractionRepository extends ChangeNotifier {
  final AppInteractionStorageService _storage;

  List<AppOpenEvent> _events = const [];
  bool _loading = true;

  AppInteractionRepository({AppInteractionStorageService? storage}) : _storage = storage ?? AppInteractionStorageService() {
    _load();
  }

  List<AppOpenEvent> get events => _events;
  bool get isLoading => _loading;

  Future<void> _load() async {
    _events = await _storage.load();
    _loading = false;
    notifyListeners();
  }

  Future<void> recordOpen(AppSnapshot snapshot) async {
    final event = AppOpenEvent(snapshot: snapshot, timestamp: DateTime.now());
    await _storage.append(event);
    _events = [event, ..._events];
    notifyListeners();
  }
}
