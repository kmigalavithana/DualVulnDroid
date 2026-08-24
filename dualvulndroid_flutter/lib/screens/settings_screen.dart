import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../repositories/auth_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';

/// Each section here is honestly scoped: Account shows real, already-known
/// user data; Notifications and Appearance are stated plainly as not
/// interactive rather than shown as a working toggle that does nothing
/// (a disabled Switch would read as broken UI, not an honest fixed
/// setting). Logout is the exact same real AuthRepository.logout() call
/// that used to live on the Dashboard AppBar, just relocated here.
class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthRepository>().currentUser;

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SettingsSection(
            title: 'Account',
            children: [
              _SettingsRow(label: 'Name', value: user?.name ?? user?.displayName ?? 'Not available'),
              _SettingsRow(label: 'Email', value: user?.email ?? 'Not available'),
            ],
          ),
          _SettingsSection(
            title: 'Notifications',
            children: const [
              _SettingsRow(label: 'Push notifications', value: 'Not available in this version.'),
            ],
          ),
          _SettingsSection(
            title: 'Appearance',
            children: const [
              _SettingsRow(label: 'Theme', value: 'Dark (fixed)'),
            ],
          ),
          _SettingsSection(
            title: 'About DualVulnDroid',
            children: const [
              _SettingsRow(label: 'Application', value: 'DualVulnDroid'),
              _SettingsRow(label: 'Version', value: '1.0.0'),
            ],
          ),
          const SizedBox(height: 8),
          Card(
            child: ListTile(
              leading: const Icon(Icons.logout, color: AppColors.riskHigh),
              title: const Text('Log out', style: TextStyle(color: AppColors.riskHigh, fontWeight: FontWeight.w600)),
              onTap: () async {
                await context.read<AuthRepository>().logout();
                if (context.mounted) AppRouter.toLogin(context);
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  final String title;
  final List<Widget> children;
  const _SettingsSection({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(bottom: 8, left: 4),
            child: Text(title.toUpperCase(), style: Theme.of(context).textTheme.labelSmall),
          ),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Column(children: children),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  final String label;
  final String value;
  const _SettingsRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: [
          Expanded(child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600))),
          Flexible(child: Text(value, textAlign: TextAlign.end, style: const TextStyle(color: AppColors.textSecondary))),
        ],
      ),
    );
  }
}
