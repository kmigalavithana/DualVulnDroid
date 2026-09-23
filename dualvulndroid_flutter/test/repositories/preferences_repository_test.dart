import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/preferences_repository.dart';
import 'package:dualvulndroid_flutter/services/preferences_storage_service.dart';

/// 12. Preference persistence - preferences survive a fresh
/// PreferencesRepository instance (i.e. a simulated app restart) because
/// they round-trip through real (mocked-platform-channel) SharedPreferences,
/// not just an in-memory field.
void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  Future<void> flushAsync() => Future<void>.delayed(Duration.zero);

  test('a toggled preference is still selected after reloading from storage', () async {
    final repo = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    await repo.togglePreference(AppPreference.lightweight);
    await repo.togglePreference(AppPreference.privacyFriendly);

    final reloaded = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    expect(reloaded.preferences.selectedPreferences, containsAll([AppPreference.lightweight, AppPreference.privacyFriendly]));
  });

  test('toggling a preference twice clears it, including after a reload', () async {
    final repo = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    await repo.togglePreference(AppPreference.noAds);
    await repo.togglePreference(AppPreference.noAds);

    final reloaded = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    expect(reloaded.preferences.selectedPreferences, isNot(contains(AppPreference.noAds)));
  });

  test('selected category persists across reload', () async {
    final repo = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    await repo.setCategory(AppCategory.notes);

    final reloaded = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    expect(reloaded.preferences.selectedCategory, AppCategory.notes);
  });

  test('a repository with no prior stored data starts with no preferences and no onboarding completed', () async {
    final repo = PreferencesRepository(storage: PreferencesStorageService());
    await flushAsync();

    expect(repo.preferences.selectedPreferences, isEmpty);
    expect(repo.hasCompletedOnboarding, isFalse);
  });
}
