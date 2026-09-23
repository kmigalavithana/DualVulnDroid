/// One selectable "what matters most to you" preference (onboarding /
/// Discover / Profile screens). Each preference maps directly to one
/// boolean attribute on [AppInfo] - see RecommendationEngine.preferenceScore -
/// so the scoring stays traceable back to a single, named user choice
/// rather than a black box.
enum AppPreference {
  lightweight('Lightweight', 'Small download and low memory use'),
  privacyFriendly('Privacy-friendly', 'Minimal or no trackers'),
  noAds('No ads', 'No advertising shown in-app'),
  offlineSupport('Offline support', 'Works without an internet connection'),
  free('Free', 'No purchase required to use'),
  openSource('Open source', 'Source code is publicly available'),
  lowStorageUsage('Low storage usage', 'Small installed size on your device');

  final String label;
  final String description;

  const AppPreference(this.label, this.description);
}

/// The app categories a user can browse/discover within (Part 5).
enum AppCategory {
  productivity('Productivity', 'work_outline'),
  notes('Notes', 'note_alt_outlined'),
  photoEditing('Photo Editing', 'photo_outlined'),
  videoEditing('Video Editing', 'movie_creation_outlined'),
  documents('PDF & Documents', 'picture_as_pdf_outlined'),
  music('Music', 'music_note_outlined'),
  education('Education', 'school_outlined'),
  communication('Communication', 'chat_bubble_outline'),
  fileManagement('File Management', 'folder_outlined'),
  browsers('Browsers', 'public_outlined'),
  utilities('Utilities', 'build_outlined'),
  other('Other', 'apps_outlined');

  final String label;

  /// A stable string key for the icon (kept as a string, not an IconData,
  /// so this model has no Flutter/material dependency) - resolved to a
  /// real Icon by CategoryIcons in the widgets layer.
  final String iconKey;

  const AppCategory(this.label, this.iconKey);
}

/// The user's locally-stored preferences (Part 4) - never synced to a
/// server, never gated behind login. Persisted via PreferencesStorageService.
class UserPreferencesModel {
  final Set<AppPreference> selectedPreferences;
  final AppCategory? selectedCategory;

  /// Saved scoring-priority weights from the What-If Simulator (Part 8) -
  /// `null` means "use the default 30/25/20/15/10 weights everywhere".
  /// Only ever set when the user explicitly taps "Save to profile"; a
  /// temporary What-If exploration never reaches this field.
  final Map<String, double>? weightOverrides;

  const UserPreferencesModel({
    this.selectedPreferences = const {},
    this.selectedCategory,
    this.weightOverrides,
  });

  bool get hasCompletedOnboarding => selectedPreferences.isNotEmpty;

  UserPreferencesModel copyWith({
    Set<AppPreference>? selectedPreferences,
    AppCategory? selectedCategory,
    bool clearCategory = false,
    Map<String, double>? weightOverrides,
    bool clearWeightOverrides = false,
  }) {
    return UserPreferencesModel(
      selectedPreferences: selectedPreferences ?? this.selectedPreferences,
      selectedCategory: clearCategory ? null : (selectedCategory ?? this.selectedCategory),
      weightOverrides: clearWeightOverrides ? null : (weightOverrides ?? this.weightOverrides),
    );
  }

  Map<String, dynamic> toJson() => {
        'preferences': selectedPreferences.map((p) => p.name).toList(),
        if (selectedCategory != null) 'category': selectedCategory!.name,
        if (weightOverrides != null) 'weightOverrides': weightOverrides,
      };

  factory UserPreferencesModel.fromJson(Map<String, dynamic> json) {
    final rawPrefs = (json['preferences'] as List?) ?? const [];
    final prefs = rawPrefs.whereType<String>().map(_preferenceByName).whereType<AppPreference>().toSet();
    final categoryName = json['category'] as String?;
    final category = categoryName == null ? null : _categoryByName(categoryName);
    final rawWeights = json['weightOverrides'] as Map?;
    final weightOverrides = rawWeights?.map((key, value) => MapEntry(key.toString(), (value as num).toDouble()));
    return UserPreferencesModel(selectedPreferences: prefs, selectedCategory: category, weightOverrides: weightOverrides);
  }

  static AppPreference? _preferenceByName(String name) {
    for (final p in AppPreference.values) {
      if (p.name == name) return p;
    }
    return null;
  }

  static AppCategory? _categoryByName(String name) {
    for (final c in AppCategory.values) {
      if (c.name == name) return c;
    }
    return null;
  }
}
