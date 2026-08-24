import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/alternative_app_model.dart';
import '../models/app_version_model.dart';
import '../models/application_summary.dart';
import '../models/security_assessment_model.dart';
import '../repositories/apps_repository.dart';
import '../routing/app_router.dart';
import '../screens/device_compatibility_screen.dart';
import '../theme/app_colors.dart';
import '../widgets/alternative_app_tile.dart';
import '../widgets/risk_badge.dart';
import '../widgets/state_views.dart';
import '../widgets/vulnerability_tile.dart';

/// Phase 9, Part 7-11, 15. One scrollable screen combining the security
/// assessment, the "why was this flagged" rollup, the Android metadata
/// section, and the safer-alternatives section - all backed by a single
/// real GET /apps/{id}/security call (plus a lazy GET
/// /apps/{id}/alternatives for the last section). Device compatibility
/// is a separate screen (Part 12) since it needs its own device-profile
/// input before it has anything real to show.
class ApplicationDetailsScreen extends StatefulWidget {
  final ApplicationSummary? application;
  final int? applicationId;

  const ApplicationDetailsScreen({super.key, required ApplicationSummary this.application}) : applicationId = null;

  const ApplicationDetailsScreen.byId({super.key, required int this.applicationId}) : application = null;

  int get resolvedId => application?.id ?? applicationId!;

  @override
  State<ApplicationDetailsScreen> createState() => _ApplicationDetailsScreenState();
}

class _ApplicationDetailsScreenState extends State<ApplicationDetailsScreen> {
  late Future<SecurityAssessment> _assessmentFuture;
  ApplicationSummary? _application;

  @override
  void initState() {
    super.initState();
    _application = widget.application;
    _load();
  }

  void _load() {
    final repo = context.read<AppsRepository>();
    _assessmentFuture = repo.getSecurity(widget.resolvedId).then((assessment) async {
      // If we only got here by id (e.g. from history), fetch the
      // application's own basic details too, for the header + chat
      // context - real data, same as the search-driven path.
      if (_application == null) {
        _application = await repo.getApplication(widget.resolvedId);
      }
      return assessment;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_application?.appName ?? 'Application details')),
      body: FutureBuilder<SecurityAssessment>(
        future: _assessmentFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const LoadingView(message: 'Loading security assessment...');
          }
          if (snapshot.hasError) {
            final message = snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Could not load this application.';
            return ErrorStateView(message: message, onRetry: () => setState(_load));
          }
          final assessment = snapshot.data!;
          return RefreshIndicator(
            onRefresh: () async {
              setState(_load);
              await _assessmentFuture;
            },
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                _Header(application: _application, assessment: assessment),
                const SizedBox(height: 20),
                if (!assessment.assessed)
                  const EmptyStateView(
                    message: 'This application has not been assessed yet.',
                    icon: Icons.hourglass_empty,
                  )
                else ...[
                  _SectionTitle('Security assessment'),
                  _SecuritySection(assessment: assessment),
                  const SizedBox(height: 20),
                  if (assessment.vulnerabilities.isNotEmpty) ...[
                    _SectionTitle('Findings'),
                    ...assessment.vulnerabilities.map((v) => Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: VulnerabilityTile(
                            vulnerability: v,
                            onViewDetails: () => AppRouter.toVulnerabilityDetail(context, v),
                          ),
                        )),
                    const SizedBox(height: 20),
                  ],
                  _SectionTitle('Why was this flagged?'),
                  _WhyFlaggedSection(riskLevel: assessment.assessment.riskLevel, recommendation: assessment.recommendation),
                  const SizedBox(height: 20),
                  _SectionTitle('Android security metadata'),
                  _AndroidMetadataSection(version: assessment.version, metadata: assessment.securityMetadata),
                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    icon: const Icon(Icons.phonelink_ring),
                    label: const Text('Check device compatibility'),
                    onPressed: () {
                      Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => DeviceCompatibilityScreen(
                          applicationId: widget.resolvedId,
                          applicationName: _application?.appName,
                        ),
                      ));
                    },
                  ),
                  const SizedBox(height: 10),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.chat_outlined),
                    label: const Text('Ask about this app'),
                    onPressed: () => AppRouter.toChat(context, selectedApplication: _application),
                  ),
                  const SizedBox(height: 24),
                  _SectionTitle('Safer alternatives'),
                  _AlternativesSection(applicationId: widget.resolvedId),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  final String title;
  const _SectionTitle(this.title);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Text(title, style: Theme.of(context).textTheme.titleMedium),
    );
  }
}

class _Header extends StatelessWidget {
  final ApplicationSummary? application;
  final SecurityAssessment assessment;
  const _Header({required this.application, required this.assessment});

  @override
  Widget build(BuildContext context) {
    final version = assessment.version;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(application?.appName ?? 'Application', style: Theme.of(context).textTheme.headlineSmall),
            if (application?.packageName != null) Text(application!.packageName!, style: const TextStyle(color: AppColors.textSecondary)),
            if (version?.versionName != null || version?.versionCode != null) ...[
              const SizedBox(height: 8),
              Text(
                'Version ${version?.versionName ?? '—'}'
                '${version?.versionCode != null ? ' (code ${version!.versionCode})' : ''}',
                style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
            if (assessment.assessment.assessedAt != null)
              Text('Assessed ${assessment.assessment.assessedAt}', style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
          ],
        ),
      ),
    );
  }
}

class _SecuritySection extends StatelessWidget {
  final SecurityAssessment assessment;
  const _SecuritySection({required this.assessment});

  @override
  Widget build(BuildContext context) {
    final a = assessment.assessment;
    // The design's "large status card" treatment - a wash of the real risk
    // color (never a separate palette; still the same RiskBadge/data below).
    return Container(
      decoration: BoxDecoration(
        gradient: AppColors.riskGradient(a.riskLevel),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      margin: const EdgeInsets.symmetric(vertical: 6),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                RiskBadge(riskLevel: a.riskLevel),
                const Spacer(),
                if (a.securityScore != null) Text('Score: ${a.securityScore}', style: const TextStyle(fontWeight: FontWeight.bold)),
              ],
            ),
            const SizedBox(height: 10),
            if (a.recommendation != null) _kv('Recommendation', a.recommendation!),
            if (a.confidence != null) _kv('Confidence', '${a.confidence}%'),
          ],
        ),
      ),
    );
  }

  Widget _kv(String k, String v) => Padding(
        padding: const EdgeInsets.only(top: 4),
        child: RichText(
          text: TextSpan(
            style: const TextStyle(fontSize: 13, color: AppColors.textPrimary),
            children: [
              TextSpan(text: '$k: ', style: const TextStyle(color: AppColors.textSecondary)),
              TextSpan(text: v, style: const TextStyle(fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      );
}

/// Phase 10A, Parts 5/6: three sub-sections built entirely from the real
/// backend "recommendation" block (decision/reason/evidence) - never a
/// second, client-invented explanation. "Why this decision?" and
/// "Evidence" are visible by default (primary, user-facing); "Technical
/// details" is an ExpansionTile, collapsed by default, for source/sink
/// data a normal user doesn't need up front.
class _WhyFlaggedSection extends StatelessWidget {
  final String? riskLevel;
  final RecommendationExplanation recommendation;

  const _WhyFlaggedSection({required this.riskLevel, required this.recommendation});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('WHY THIS DECISION?', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.textSecondary, letterSpacing: 0.5)),
            const SizedBox(height: 8),
            if (riskLevel != null)
              Text('Security risk: $riskLevel', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 6),
            // The real stored explanation, verbatim - never a generated
            // fallback sentence when it's genuinely absent (Part 2/6).
            Text(
              recommendation.reason ?? 'No explanation was recorded for this assessment.',
              style: TextStyle(
                fontSize: 14,
                fontStyle: recommendation.reason == null ? FontStyle.italic : FontStyle.normal,
                color: recommendation.reason == null ? AppColors.textSecondary : AppColors.textPrimary,
              ),
            ),
            if (recommendation.evidence.isNotEmpty) ...[
              const SizedBox(height: 20),
              const Text('EVIDENCE', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: AppColors.textSecondary, letterSpacing: 0.5)),
              const SizedBox(height: 8),
              ...recommendation.evidence.map((e) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.circle, size: 6, color: AppColors.riskHigh),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            [
                              e.type ?? e.cwe ?? 'Finding',
                              if (e.cwe != null && e.type != null) e.cwe,
                              if (e.severity != null) e.severity,
                              if (e.confidence != null) '${e.confidence}% confidence',
                            ].whereType<String>().join(' · '),
                            style: const TextStyle(fontSize: 13),
                          ),
                        ),
                      ],
                    ),
                  )),
              const SizedBox(height: 10),
              Theme(
                data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                child: ExpansionTile(
                  tilePadding: EdgeInsets.zero,
                  title: const Text('Technical details', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
                  initiallyExpanded: false,
                  childrenPadding: const EdgeInsets.only(bottom: 8),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    ...recommendation.evidence.where((e) => e.source != null || e.sink != null).map((e) => Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Text(
                            '${e.source ?? '?'} → ${e.sink ?? '?'}',
                            style: const TextStyle(fontSize: 12, fontFamily: 'monospace', color: AppColors.textSecondary),
                          ),
                        )),
                    // No SHAP/model-factor data is currently persisted
                    // for any stored scan (Part 3) - stated honestly
                    // rather than omitted silently or fabricated.
                    const Text(
                      'Model-level evidence (e.g. SHAP feature weights) is not currently stored for this assessment.',
                      style: TextStyle(fontSize: 11, color: AppColors.textSecondary, fontStyle: FontStyle.italic),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Phase 9, Part 11: shown as neutral, factual statements - never
/// "this application is vulnerable" solely because of these flags.
class _AndroidMetadataSection extends StatelessWidget {
  final AppVersionModel? version;
  final SecurityMetadata metadata;
  const _AndroidMetadataSection({required this.version, required this.metadata});

  String _boolText(bool? value, String trueText, String falseText) {
    if (value == null) return 'Not available from the manifest.';
    return value ? trueText : falseText;
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _row('Minimum Android version (SDK)', version?.minSdkVersion?.toString() ?? 'Not available'),
            _row('Target Android version (SDK)', version?.targetSdkVersion?.toString() ?? 'Not available'),
            _row('Debuggable', _boolText(metadata.debuggable,
                'Application declares debuggable=true.', 'Application declares debuggable=false.')),
            _row('Allow backup', _boolText(metadata.allowBackup,
                'Application declares allowBackup=true - a security consideration, not a vulnerability by itself.',
                'Application declares allowBackup=false.')),
          ],
        ),
      ),
    );
  }

  Widget _row(String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary)),
            Text(value, style: const TextStyle(fontSize: 14)),
          ],
        ),
      );
}

class _AlternativesSection extends StatefulWidget {
  final int applicationId;
  const _AlternativesSection({required this.applicationId});

  @override
  State<_AlternativesSection> createState() => _AlternativesSectionState();
}

class _AlternativesSectionState extends State<_AlternativesSection> {
  late final Future<(bool, List<AlternativeApp>)> _future;

  @override
  void initState() {
    super.initState();
    _future = context.read<AppsRepository>().getAlternatives(widget.applicationId);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<(bool, List<AlternativeApp>)>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: LoadingView());
        }
        if (snapshot.hasError) {
          final message = snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Could not load alternatives.';
          return ErrorStateView(message: message);
        }
        final (available, alternatives) = snapshot.data!;
        if (!available || alternatives.isEmpty) {
          return const EmptyStateView(message: 'No verified safer alternatives are available yet.', icon: Icons.verified_outlined);
        }
        return Column(children: alternatives.map((a) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: AlternativeAppTile(alternative: a),
            )).toList());
      },
    );
  }
}
