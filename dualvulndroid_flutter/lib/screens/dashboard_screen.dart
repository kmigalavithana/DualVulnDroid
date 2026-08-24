import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/history_item_model.dart';
import '../repositories/auth_repository.dart';
import '../repositories/history_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../widgets/risk_badge.dart';
import '../widgets/state_views.dart';

/// Phase 9, Part 5. Sections: welcome header, search entry point, recent
/// assessments, a real (never fabricated) risk summary derived from the
/// user's own history, and quick access to full history.
class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  late Future<List<HistoryItem>> _historyFuture;

  @override
  void initState() {
    super.initState();
    _historyFuture = context.read<HistoryRepository>().getHistory();
  }

  Future<void> _refresh() async {
    setState(() => _historyFuture = context.read<HistoryRepository>().getHistory());
    await _historyFuture;
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthRepository>().currentUser;

    return Scaffold(
      appBar: AppBar(
        title: const Text('DualVulnDroid'),
        actions: [
          // Logout itself is unchanged (still the real AuthRepository.logout()
          // + AppRouter.toLogin call) - it just now lives on SettingsScreen
          // instead of here directly, alongside the other real settings.
          IconButton(
            tooltip: 'Settings',
            icon: const Icon(Icons.settings_outlined),
            onPressed: () => AppRouter.toSettings(context),
          ),
        ],
      ),
      // Home's second primary action (Part: chatbot must be obviously
      // reachable from Home, not just from an application's own details
      // screen). Reuses the existing SecurityChatScreen/ChatRepository via
      // AppRouter.toChat - no new chatbot screen or API path is created.
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => AppRouter.toChat(context),
        backgroundColor: AppColors.accent,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.smart_toy_outlined),
        label: const Text('Security Chat'),
        tooltip: 'AI Security Assistant',
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 96),
          children: [
            Text('Welcome, ${user?.displayName ?? "there"}', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 4),
            const Text('Check whether an app is safe before you install it.', style: TextStyle(color: AppColors.textSecondary)),
            const SizedBox(height: 20),
            // Search is fully real (AppRouter.toSearch). Installed Apps and
            // Upload APK are kept as visible actions matching the approved
            // design, but neither has any real capability behind it in this
            // app (no on-device app enumeration, no upload endpoint) - each
            // honestly says so via NotAvailableScreen rather than faking a
            // result.
            Row(
              children: [
                Expanded(
                  child: _ActionButton(
                    icon: Icons.search,
                    label: 'Search Apps',
                    onTap: () => AppRouter.toSearch(context),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.apps_outlined,
                    label: 'Installed Apps',
                    onTap: () => AppRouter.toInstalledApps(context),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: _ActionButton(
                    icon: Icons.upload_file_outlined,
                    label: 'Upload APK',
                    onTap: () => AppRouter.toUploadApk(context),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 28),
            FutureBuilder<List<HistoryItem>>(
              future: _historyFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(padding: EdgeInsets.symmetric(vertical: 32), child: LoadingView());
                }
                if (snapshot.hasError) {
                  final message = snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Could not load your assessment history.';
                  return ErrorStateView(message: message, onRetry: _refresh);
                }
                final history = snapshot.data ?? const [];
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _RiskSummary(history: history),
                    const SizedBox(height: 24),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('Recent assessments', style: Theme.of(context).textTheme.titleMedium),
                        TextButton(onPressed: () => AppRouter.toHistory(context), child: const Text('View all')),
                      ],
                    ),
                    if (history.isEmpty)
                      const EmptyStateView(message: 'No applications assessed yet.', icon: Icons.fact_check_outlined)
                    else
                      ...history.take(5).map((item) => Card(
                            child: ListTile(
                              title: Text(item.appName ?? 'Unknown application'),
                              subtitle: Text(item.packageName ?? ''),
                              trailing: RiskBadge(riskLevel: item.riskLevel),
                            ),
                          )),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _ActionButton({required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.surfaceAlt,
      borderRadius: BorderRadius.circular(14),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 6),
          child: Column(
            children: [
              Icon(icon, color: AppColors.accent, size: 22),
              const SizedBox(height: 6),
              Text(label, textAlign: TextAlign.center, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color? color;
  const _StatCard({required this.label, required this.value, required this.icon, this.color});

  @override
  Widget build(BuildContext context) {
    final c = color ?? AppColors.accent;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: c, size: 20),
          const SizedBox(height: 10),
          Text(value, style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 2),
          Text(label, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
        ],
      ),
    );
  }
}

/// A REAL summary derived by counting the user's own already-fetched
/// history entries by risk level - never a fabricated statistic (Part
/// 5: "Do not fabricate statistics").
class _RiskSummary extends StatelessWidget {
  final List<HistoryItem> history;

  const _RiskSummary({required this.history});

  @override
  Widget build(BuildContext context) {
    if (history.isEmpty) return const SizedBox.shrink();

    final counts = <String, int>{};
    for (final item in history) {
      final level = item.riskLevel?.toUpperCase() ?? 'UNKNOWN';
      counts[level] = (counts[level] ?? 0) + 1;
    }
    // Both real, derived directly from the user's own already-fetched
    // history - a "vulnerabilities found" tile was considered but dropped:
    // HistoryItem carries no per-app vulnerability count, so showing one
    // would mean either an extra N+1 fetch per history row or a fabricated
    // number, neither of which this restyle does.
    final safeCount = counts['LOW'] ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Your security overview', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 10),
        Row(
          children: [
            Expanded(child: _StatCard(label: 'Apps analysed', value: '${history.length}', icon: Icons.fact_check_outlined)),
            const SizedBox(width: 12),
            Expanded(child: _StatCard(label: 'Safe applications', value: '$safeCount', icon: Icons.verified_outlined, color: AppColors.riskLow)),
          ],
        ),
        const SizedBox(height: 12),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('By risk level', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                Text('Based on ${history.length} assessed application${history.length == 1 ? '' : 's'} in your history.',
                    style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: counts.entries.map((e) => Chip(
                        avatar: CircleAvatar(backgroundColor: AppColors.forRiskLevel(e.key), radius: 6),
                        label: Text('${e.key}: ${e.value}'),
                      )).toList(),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
