import 'package:flutter/foundation.dart';

import '../models/user_preferences_model.dart';
import '../services/preferences_storage_service.dart';

/// Holds the user's local preferences for the app's lifetime and keeps
/// them persisted (Part 4). No login/account is ever required - this is
/// purely on-device state.
class PreferencesRepository extends ChangeNotifier {
  final PreferencesStorageService _storage;

  UserPreferencesModel _preferences = const UserPreferencesModel();
  bool _loading = true;

  PreferencesRepository({PreferencesStorageService? storage}) : _storage = storage ?? PreferencesStorageService() {
    _load();
  }

  UserPreferencesModel get preferences => _preferences;
  bool get isLoading => _loading;
  bool get hasCompletedOnboarding => _preferences.hasCompletedOnboarding;

  Future<void> _load() async {
    _preferences = await _storage.load();
    _loading = false;
    notifyListeners();
  }

  Future<void> togglePreference(AppPreference preference) async {
    final updated = Set<AppPreference>.from(_preferences.selectedPreferences);
    if (!updated.remove(preference)) updated.add(preference);
    _preferences = _preferences.copyWith(selectedPreferences: updated);
    notifyListeners();
    await _storage.save(_preferences);
  }

  Future<void> setPreferences(Set<AppPreference> preferences) async {
    _preferences = _preferences.copyWith(selectedPreferences: preferences);
    notifyListeners();
    await _storage.save(_preferences);
  }

  Future<void> setCategory(AppCategory? category) async {
    _preferences = _preferences.copyWith(selectedCategory: category, clearCategory: category == null);
    notifyListeners();
    await _storage.save(_preferences);
  }

  /// Persists a set of scoring-priority weights from the What-If Simulator
  /// (Part 8) - only called when the user explicitly taps "Save to
  /// profile", never automatically from a temporary exploration.
  Future<void> setWeightOverrides(Map<String, double> weights) async {
    _preferences = _preferences.copyWith(weightOverrides: weights);
    notifyListeners();
    await _storage.save(_preferences);
  }

  Future<void> clearWeightOverrides() async {
    _preferences = _preferences.copyWith(clearWeightOverrides: true);
    notifyListeners();
    await _storage.save(_preferences);
  }
}
