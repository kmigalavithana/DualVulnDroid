import 'package:flutter/material.dart';

import '../models/app_info_model.dart';
import '../models/user_preferences_model.dart';
import '../screens/alternative_finder_screen.dart';
import '../screens/app_detail_screen.dart';
import '../screens/category_selection_screen.dart';
import '../screens/device_profile_screen.dart';
import '../screens/discover_screen.dart';
import '../screens/evaluation_screen.dart';
import '../screens/favorites_screen.dart';
import '../screens/history_screen.dart';
import '../screens/installed_apps_screen.dart';
import '../screens/onboarding_preferences_screen.dart';
import '../screens/recommendation_results_screen.dart';
import '../screens/what_if_simulator_screen.dart';
import '../widgets/app_shell.dart';

/// Centralizes navigation (plain MaterialPageRoute pushes - the theme's
/// PageTransitionsTheme supplies the subtle fade transition). Top-level
/// destinations (Discover, History, Profile) are tabs: going "to" one
/// returns to the shell and switches tab instead of stacking a copy.
class AppRouter {
  AppRouter._();

  static void toOnboarding(BuildContext context) {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const OnboardingPreferencesScreen(isFirstRun: true)),
      (route) => false,
    );
  }

  static void toHome(BuildContext context) {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const AppShell()),
      (route) => false,
    );
  }

  /// Back to the bottom-navigation shell on [tab]; falls back to [fallback]
  /// when no shell is on screen.
  static void _toTab(BuildContext context, ShellTab tab, Widget Function() fallback) {
    final navigator = Navigator.of(context);
    if (AppShell.select(tab)) {
      navigator.popUntil((route) => route.isFirst);
    } else {
      navigator.push(MaterialPageRoute(builder: (_) => fallback()));
    }
  }

  static void toDiscover(BuildContext context) => _toTab(context, ShellTab.discover, () => const DiscoverScreen());

  static void toHistory(BuildContext context) => _toTab(context, ShellTab.history, () => const HistoryScreen());

  static void toPreferences(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const OnboardingPreferencesScreen()));
  }

  static void toCategorySelection(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CategorySelectionScreen()));
  }

  static void toResultsForCategory(BuildContext context, AppCategory category) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => RecommendationResultsScreen(category: category)));
  }

  static void toResultsForCandidates(BuildContext context, List<AppInfo> candidates, {String? searchLabel}) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => RecommendationResultsScreen(candidates: candidates, searchLabel: searchLabel)));
  }

  static void toAppDetail(BuildContext context, AppInfo app) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => AppDetailScreen(app: app)));
  }

  static void toAlternativeFinder(BuildContext context, {AppInfo? initialApp, String? initialAppName}) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => AlternativeFinderScreen(initialApp: initialApp, initialAppName: initialAppName),
    ));
  }

  static void toDeviceProfile(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DeviceProfileScreen()));
  }

  static void toInstalledApps(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const InstalledAppsScreen()));
  }

  static void toWhatIfSimulator(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const WhatIfSimulatorScreen()));
  }

  static void toFavorites(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const FavoritesScreen()));
  }

  static void toEvaluation(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const EvaluationScreen()));
  }
}
