import 'package:flutter/foundation.dart';

import '../models/app_info_model.dart';
import '../models/app_snapshot_model.dart';
import '../services/favorites_storage_service.dart';

/// Holds the user's real, locally-favorited apps for the app's lifetime
/// (Part 13). An entry is only ever added when the user actually taps
/// "favorite" - never pre-seeded. Keyed by package name (real Google
/// Play apps have no other stable local id), storing a real [AppSnapshot]
/// so a favorite can be displayed without depending on a static catalog.
class FavoritesRepository extends ChangeNotifier {
  final FavoritesStorageService _storage;

  Map<String, AppSnapshot> _favorites = const {};
  bool _loading = true;

  FavoritesRepository({FavoritesStorageService? storage}) : _storage = storage ?? FavoritesStorageService() {
    _load();
  }

  List<AppSnapshot> get favorites => _favorites.values.toList();
  Set<String> get favoriteAppIds => _favorites.keys.toSet();
  bool get isLoading => _loading;

  /// The same key [toggle] stores a favorite under - packageName when
  /// known (every real Google Play app), otherwise the local id (curated
  /// demo apps only, some of which have a packageName that differs from
  /// their id, so this must be the ONE place both agree on which to use).
  String keyFor(AppInfo app) => app.packageName ?? app.id;

  bool isFavorite(AppInfo app) => _favorites.containsKey(keyFor(app));

  Future<void> _load() async {
    _favorites = await _storage.load();
    _loading = false;
    notifyListeners();
  }

  Future<void> toggle(AppInfo app) async {
    final id = keyFor(app);
    final updated = Map<String, AppSnapshot>.from(_favorites);
    if (!updated.containsKey(id)) {
      updated[id] = AppSnapshot.fromApp(app);
    } else {
      updated.remove(id);
    }
    _favorites = updated;
    notifyListeners();
    await _storage.save(_favorites);
  }
}
