import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/history_item_model.dart';
import '../repositories/history_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../widgets/risk_badge.dart';
import '../widgets/state_views.dart';

/// Phase 9, Part 16. Only ever the authenticated user's own history
/// (GET /user/history is JWT-derived server-side - this screen has no
/// way to ask for anyone else's).
class AssessmentHistoryScreen extends StatefulWidget {
  const AssessmentHistoryScreen({super.key});

  @override
  State<AssessmentHistoryScreen> createState() => _AssessmentHistoryScreenState();
}

class _AssessmentHistoryScreenState extends State<AssessmentHistoryScreen> {
  late Future<List<HistoryItem>> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<HistoryRepository>().getHistory();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Assessment history')),
      body: FutureBuilder<List<HistoryItem>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const LoadingView();
          }
          if (snapshot.hasError) {
            final message = snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Could not load your history.';
            return ErrorStateView(message: message, onRetry: () => setState(() {
                  _future = context.read<HistoryRepository>().getHistory();
                }));
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const EmptyStateView(message: 'No applications assessed yet.', icon: Icons.fact_check_outlined);
          }
          return ListView.builder(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
            itemCount: items.length,
            itemBuilder: (context, index) {
              final item = items[index];
              return Card(
                child: ListTile(
                  contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  title: Text(item.appName ?? 'Unknown application', style: const TextStyle(fontWeight: FontWeight.w600)),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 2),
                      if (item.packageName != null) Text(item.packageName!, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
                      if (item.timestamp != null)
                        Text(_formatDate(item.timestamp!), style: const TextStyle(fontSize: 11, color: AppColors.textSecondary)),
                    ],
                  ),
                  isThreeLine: item.packageName != null && item.timestamp != null,
                  trailing: RiskBadge(riskLevel: item.riskLevel),
                  onTap: item.applicationId != null
                      ? () => AppRouter.toApplicationDetailsById(context, item.applicationId!)
                      : null,
                ),
              );
            },
          );
        },
      ),
    );
  }

  String _formatDate(DateTime dt) {
    return '${dt.year}-${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')}';
  }
}
