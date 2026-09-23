import '../models/app_info_model.dart';
import '../models/user_preferences_model.dart';

/// One real, calculated suggestion to add an unselected preference,
/// derived from the user's own recorded behavior (Part 10). Never applied
/// automatically - shown as a dismissible prompt, applied only if the
/// user explicitly accepts it.
class AdaptiveSuggestion {
  final AppPreference suggestedPreference;
  final String message;
  final double confidence;

  const AdaptiveSuggestion({required this.suggestedPreference, required this.message, required this.confidence});
}

/// Looks for a real, strong pattern in the [AppInfo]s the caller has
/// already resolved as "liked" (favorited/opened/positively-rated), and
/// suggests adding ONE matching preference the user hasn't already
/// selected (Part 10: "Use these signals to suggest preference
/// adjustments... Do not silently alter user preferences"). Pure and
/// stateless - takes already-resolved [AppInfo]s, does no I/O or catalog
/// lookups itself, and NEVER mutates [UserPreferencesModel] - only the
/// caller's explicit "accept" action does that.
///
/// A real Google Play app with unverified attributes (trackerCount,
/// resourceLevel, etc. all `null`) satisfies none of the 7 preferences by
/// construction (see AppInfo.satisfies) - so this engine can only ever
/// detect a real pattern among apps with genuinely known attributes
/// (today, the curated demo dataset). That is a correct consequence of
/// never fabricating privacy/resource data, not a bug: an unresolved
/// pattern is honestly reported as "not enough data", never guessed at.
class AdaptiveSuggestionEngine {
  const AdaptiveSuggestionEngine();

  /// A pattern must be backed by at least this many distinct liked apps
  /// before a suggestion is offered at all - too little data must never
  /// produce a suggestion.
  static const int minSignals = 3;

  /// A preference must be satisfied by at least this fraction of the
  /// user's liked apps to count as a real, strong pattern (not noise).
  static const double minRatio = 0.7;

  AdaptiveSuggestion? suggest({
    required List<AppInfo> likedApps,
    required Set<AppPreference> currentPreferences,
  }) {
    if (likedApps.length < minSignals) return null;

    AppPreference? bestPreference;
    double bestRatio = 0;
    for (final preference in AppPreference.values) {
      if (currentPreferences.contains(preference)) continue;
      final matching = likedApps.where((a) => a.satisfies(preference)).length;
      final ratio = matching / likedApps.length;
      if (ratio > bestRatio) {
        bestRatio = ratio;
        bestPreference = preference;
      }
    }

    if (bestPreference == null || bestRatio < minRatio) return null;
    return AdaptiveSuggestion(
      suggestedPreference: bestPreference,
      message: 'You frequently choose ${bestPreference.label.toLowerCase()} apps. '
          'Would you like to prioritize this?',
      confidence: bestRatio,
    );
  }
}
