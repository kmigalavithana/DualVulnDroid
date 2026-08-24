import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/application_summary.dart';
import '../models/security_assessment_model.dart';
import '../repositories/apps_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';
import '../widgets/risk_badge.dart';
import '../widgets/state_views.dart';

/// Phase 9, Part 6. Search results only ever show real data: app name,
/// package name, and (once resolved) a REAL assessment status fetched
/// per result - never a placeholder/fabricated risk level for a result
/// this screen hasn't actually checked yet.
class SearchApplicationScreen extends StatefulWidget {
  const SearchApplicationScreen({super.key});

  @override
  State<SearchApplicationScreen> createState() => _SearchApplicationScreenState();
}

class _SearchApplicationScreenState extends State<SearchApplicationScreen> {
  final _controller = TextEditingController();
  Future<List<ApplicationSummary>>? _resultsFuture;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _search() {
    final query = _controller.text.trim();
    if (query.isEmpty) return;
    setState(() {
      _resultsFuture = context.read<AppsRepository>().search(query);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Search application')),
      body: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(hintText: 'Search application name...', prefixIcon: Icon(Icons.search)),
                    onSubmitted: (_) => _search(),
                    textInputAction: TextInputAction.search,
                  ),
                ),
                const SizedBox(width: 10),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(minimumSize: const Size(48, 48), padding: EdgeInsets.zero),
                  onPressed: _search,
                  child: const Icon(Icons.arrow_forward),
                ),
              ],
            ),
            const SizedBox(height: 20),
            Expanded(
              child: _resultsFuture == null
                  ? const EmptyStateView(message: 'Search for an app by name or package name.', icon: Icons.travel_explore)
                  : FutureBuilder<List<ApplicationSummary>>(
                      future: _resultsFuture,
                      builder: (context, snapshot) {
                        if (snapshot.connectionState == ConnectionState.waiting) {
                          return const LoadingView(message: 'Searching...');
                        }
                        if (snapshot.hasError) {
                          final message = snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Search failed.';
                          return ErrorStateView(message: message, onRetry: _search);
                        }
                        final results = snapshot.data ?? const [];
                        if (results.isEmpty) {
                          return const EmptyStateView(message: 'No applications matched your search.', icon: Icons.search_off);
                        }
                        return ListView.builder(
                          itemCount: results.length,
                          itemBuilder: (context, index) => _SearchResultTile(application: results[index]),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SearchResultTile extends StatefulWidget {
  final ApplicationSummary application;
  const _SearchResultTile({required this.application});

  @override
  State<_SearchResultTile> createState() => _SearchResultTileState();
}

class _SearchResultTileState extends State<_SearchResultTile> {
  late final Future<SecurityAssessment> _assessmentFuture;

  @override
  void initState() {
    super.initState();
    _assessmentFuture = context.read<AppsRepository>().getSecurity(widget.application.id);
  }

  @override
  Widget build(BuildContext context) {
    final iconUrl = widget.application.iconUrl;
    return Card(
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: AppColors.surfaceAlt,
          backgroundImage: (iconUrl != null && iconUrl.isNotEmpty) ? NetworkImage(iconUrl) : null,
          child: (iconUrl == null || iconUrl.isEmpty) ? const Icon(Icons.apps, color: AppColors.textSecondary, size: 20) : null,
        ),
        title: Text(widget.application.appName, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(widget.application.packageName ?? '', style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
        trailing: FutureBuilder<SecurityAssessment>(
          future: _assessmentFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2));
            }
            if (snapshot.hasError || snapshot.data == null || !snapshot.data!.assessed) {
              return const Tooltip(
                message: 'This application has not been assessed yet.',
                child: Icon(Icons.help_outline, color: AppColors.textSecondary),
              );
            }
            return RiskBadge(riskLevel: snapshot.data!.assessment.riskLevel);
          },
        ),
        onTap: () => AppRouter.toApplicationDetails(context, widget.application),
      ),
    );
  }
}
