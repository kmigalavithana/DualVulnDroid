import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/favorites_repository.dart';
import 'package:dualvulndroid_flutter/services/favorites_storage_service.dart';

AppInfo _app(String packageName, String name) => AppInfo(
      id: packageName,
      name: name,
      packageName: packageName,
      category: AppCategory.notes,
      iconKey: 'apps_outlined',
      isLiveData: true,
      dataSource: 'google_play',
    );

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  Future<void> flushAsync() => Future<void>.delayed(Duration.zero);

  test('a repository with no prior stored data starts with no favorites', () async {
    final repo = FavoritesRepository(storage: FavoritesStorageService());
    await flushAsync();
    expect(repo.favoriteAppIds, isEmpty);
    expect(repo.isFavorite(_app('com.example.noteflow', 'NoteFlow')), isFalse);
  });

  test('toggling an app adds it, and toggling again removes it', () async {
    final repo = FavoritesRepository(storage: FavoritesStorageService());
    await flushAsync();
    final app = _app('com.example.noteflow', 'NoteFlow');

    await repo.toggle(app);
    expect(repo.isFavorite(app), isTrue);

    await repo.toggle(app);
    expect(repo.isFavorite(app), isFalse);
  });

  test('favorites survive a fresh repository instance (real persistence, not just in-memory)', () async {
    final repo = FavoritesRepository(storage: FavoritesStorageService());
    await flushAsync();
    await repo.toggle(_app('com.example.noteflow', 'NoteFlow'));
    await repo.toggle(_app('com.example.taskflow', 'TaskFlow'));

    final reloaded = FavoritesRepository(storage: FavoritesStorageService());
    await flushAsync();
    expect(reloaded.favoriteAppIds, containsAll(['com.example.noteflow', 'com.example.taskflow']));
  });

  test('the stored snapshot carries the real name/category, never a re-derived value', () async {
    final repo = FavoritesRepository(storage: FavoritesStorageService());
    await flushAsync();
    await repo.toggle(_app('com.example.noteflow', 'NoteFlow'));

    final snapshot = repo.favorites.single;
    expect(snapshot.packageName, 'com.example.noteflow');
    expect(snapshot.name, 'NoteFlow');
    expect(snapshot.category, AppCategory.notes);
    expect(snapshot.isLiveData, isTrue);
  });

  test('a curated demo app whose id differs from its packageName is keyed consistently', () async {
    // Regression: toggle() used to key by packageName while call sites
    // checked isFavorite(app.id) - for demo apps these differ, so
    // favoriting silently never "stuck". Both must now agree.
    final repo = FavoritesRepository(storage: FavoritesStorageService());
    await flushAsync();
    const demoApp = AppInfo(
      id: 'noteflow',
      name: 'NoteFlow',
      packageName: 'com.smartapp.demo.noteflow',
      category: AppCategory.notes,
      iconKey: 'apps_outlined',
    );

    await repo.toggle(demoApp);
    expect(repo.isFavorite(demoApp), isTrue);
  });
}
