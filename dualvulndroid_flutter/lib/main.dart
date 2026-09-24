import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'engines/recommendation_engine.dart';
import 'repositories/app_interaction_repository.dart';
import 'repositories/app_repository.dart';
import 'repositories/apps_repository.dart';
import 'repositories/device_profile_repository.dart';
import 'repositories/evaluation_repository.dart';
import 'repositories/favorites_repository.dart';
import 'repositories/feedback_repository.dart';
import 'repositories/history_repository.dart';
import 'repositories/preferences_repository.dart';
import 'screens/splash_screen.dart';
import 'services/installed_apps_service.dart';
import 'services/play_store_launcher.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const SmartAppApp());
}

/// SmartApp: a standalone, offline-first Android app-discovery and
/// recommendation experience (see README.md). No backend, no login, no
/// APK upload/scan - every provider here is either pure local state
/// (preferences/history, persisted via shared_preferences) or a thin
/// wrapper around a real platform API (device info, installed apps,
/// launching a Play Store URL).
class SmartAppApp extends StatelessWidget {
  const SmartAppApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider(create: (_) => AppsRepository()),
        Provider(create: (_) => AppRepository()),
        Provider(create: (_) => const RecommendationEngine()),
        Provider(create: (_) => InstalledAppsService()),
        Provider(create: (_) => PlayStoreLauncher()),
        ChangeNotifierProvider(create: (_) => PreferencesRepository()),
        ChangeNotifierProvider(create: (_) => DeviceProfileRepository()),
        ChangeNotifierProvider(create: (_) => HistoryRepository()),
        ChangeNotifierProvider(create: (_) => FavoritesRepository()),
        ChangeNotifierProvider(create: (_) => FeedbackRepository()),
        ChangeNotifierProvider(create: (_) => AppInteractionRepository()),
        // Research Evaluation Mode - separate storage, never read by the
        // production recommendation flow.
        ChangeNotifierProvider(create: (_) => EvaluationRepository()),
      ],
      child: MaterialApp(
        title: 'SmartApp',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const SplashScreen(),
      ),
    );
  }
}
