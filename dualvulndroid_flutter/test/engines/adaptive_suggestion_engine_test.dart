import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/engines/adaptive_suggestion_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';

const _engine = AdaptiveSuggestionEngine();

void main() {
  final apps = AppsRepository();
  // Real catalog entries known to satisfy specific preferences (see
  // sample_apps_data.dart): noteflow/taskflow/filepilot/studybuddy are
  // all lightweight AND offline AND open source.
  const lightweightOfflineIds = ['noteflow', 'taskflow', 'filepilot', 'studybuddy'];

  group('AdaptiveSuggestionEngine', () {
    test('suggests nothing when there are fewer than minSignals liked apps', () {
      final likedApps = ['noteflow'].map(apps.byId).whereType<AppInfo>().toList();
      final suggestion = _engine.suggest(likedApps: likedApps, currentPreferences: const {});
      expect(suggestion, isNull);
    });

    test('suggests nothing when liked apps do not share a strong common preference', () {
      // Deliberately pick apps that don't share a dominant unselected preference.
      final likedApps = ['docsuitepro', 'proretouch', 'videoforgepro'] // heavy, ad-supported, non-offline
          .map(apps.byId)
          .whereType<AppInfo>()
          .toList();
      final suggestion = _engine.suggest(
        likedApps: likedApps,
        currentPreferences: const {AppPreference.lightweight, AppPreference.offlineSupport, AppPreference.openSource},
      );
      expect(suggestion, isNull);
    });

    test('suggests a preference already satisfied by a strong majority of liked apps', () {
      final likedApps = lightweightOfflineIds.map(apps.byId).whereType<AppInfo>().toList();
      final suggestion = _engine.suggest(likedApps: likedApps, currentPreferences: const {});
      expect(suggestion, isNotNull);
      expect(suggestion!.confidence, greaterThanOrEqualTo(AdaptiveSuggestionEngine.minRatio));
    });

    test('never suggests a preference the user has already selected', () {
      final likedApps = lightweightOfflineIds.map(apps.byId).whereType<AppInfo>().toList();
      final suggestion = _engine.suggest(
        likedApps: likedApps,
        currentPreferences: AppPreference.values.toSet(), // already everything
      );
      expect(suggestion, isNull);
    });

    test('an app with unverified attributes (e.g. real Google Play data) never counts toward a pattern', () {
      // A "liked" app whose recommendation-relevant fields are all null
      // (as any live Google Play result's are today) can never honestly
      // satisfy() a preference, so it contributes nothing to a pattern -
      // this is the correct, non-fabricating consequence of Part 10/11,
      // not a bug.
      const liveApp = AppInfo(
        id: 'com.example.live',
        name: 'Live App',
        packageName: 'com.example.live',
        category: AppCategory.utilities,
        iconKey: 'apps_outlined',
        isLiveData: true,
      );
      final likedApps = [...lightweightOfflineIds.map(apps.byId).whereType<AppInfo>(), liveApp];
      final suggestion = _engine.suggest(likedApps: likedApps, currentPreferences: const {});
      // Still finds the real pattern among the 4 verified demo apps -
      // the unverifiable live app just doesn't help or hurt it.
      expect(suggestion, isNotNull);
    });
  });
}
