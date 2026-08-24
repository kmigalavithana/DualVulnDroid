import 'package:flutter/material.dart';

import '../widgets/state_views.dart';

/// A thin, honest wrapper around the app's existing EmptyStateView for a
/// design concept with no real backend/data support (e.g. Installed Apps,
/// Upload APK). Never fabricates content (no fake app list, no fake scan
/// result) - just states plainly that the capability isn't available yet.
class NotAvailableScreen extends StatelessWidget {
  final String title;
  final String message;
  final IconData icon;

  const NotAvailableScreen({super.key, required this.title, required this.message, this.icon = Icons.construction_outlined});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: EmptyStateView(message: message, icon: icon),
    );
  }
}
