import 'package:flutter/material.dart';

import '../models/application_summary.dart';
import '../models/vulnerability_model.dart';
import '../screens/application_details_screen.dart';
import '../screens/assessment_history_screen.dart';
import '../screens/login_screen.dart';
import '../screens/not_available_screen.dart';
import '../screens/search_application_screen.dart';
import '../screens/security_chat_screen.dart';
import '../screens/settings_screen.dart';
import '../screens/vulnerability_detail_screen.dart';
import '../widgets/app_shell.dart';

/// Centralizes navigation (Part 1: routing/ layer). Kept as plain
/// MaterialPageRoute pushes rather than a full named-route table or a
/// third-party router package - this app's navigation graph is a
/// straightforward stack (login -> dashboard -> search -> details ->
/// sub-screens), so a router package would add complexity without a
/// matching benefit; the point of this class is just to keep every
/// `Navigator.push(...)` call written in one place instead of scattered
/// across screens.
class AppRouter {
  AppRouter._();

  static void toLogin(BuildContext context) {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (route) => false,
    );
  }

  static void toDashboard(BuildContext context) {
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const AppShell()),
      (route) => false,
    );
  }

  static void toSearch(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SearchApplicationScreen()));
  }

  static void toApplicationDetails(BuildContext context, ApplicationSummary application) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => ApplicationDetailsScreen(application: application)));
  }

  static void toApplicationDetailsById(BuildContext context, int applicationId) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => ApplicationDetailsScreen.byId(applicationId: applicationId)));
  }

  static void toHistory(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AssessmentHistoryScreen()));
  }

  static void toChat(BuildContext context, {ApplicationSummary? selectedApplication}) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => SecurityChatScreen(selectedApplication: selectedApplication)));
  }

  static void toSettings(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const SettingsScreen()));
  }

  static void toVulnerabilityDetail(BuildContext context, VulnerabilityModel vulnerability) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => VulnerabilityDetailScreen(vulnerability: vulnerability)));
  }

  // Both target a design concept with no real backend/data support behind
  // it (Part: "do not fabricate an installed-app list or an upload/scan
  // result") - each pushes the same honest NotAvailableScreen with
  // different, centralized copy rather than duplicating the message at
  // every call site.
  static void toInstalledApps(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => const NotAvailableScreen(
        title: 'Installed Apps',
        message: 'On-device app scanning is not available in this version. Use Search to look up an application instead.',
      ),
    ));
  }

  static void toUploadApk(BuildContext context) {
    Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => const NotAvailableScreen(
        title: 'Upload APK',
        message: 'Uploading an APK for direct analysis is not available in this version. Use Search to look up an already-analyzed application instead.',
      ),
    ));
  }
}
