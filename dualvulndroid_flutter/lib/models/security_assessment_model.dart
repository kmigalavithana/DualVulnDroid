import 'app_version_model.dart';
import 'compatibility_model.dart';
import 'vulnerability_model.dart';

/// The core risk/recommendation block - real decision-engine output,
/// never recomputed client-side (Part 8: "do not create a new frontend
/// scoring system").
class AssessmentResult {
  final String? riskLevel;
  final String? recommendation;
  final int? confidence;
  final int? securityScore;
  final DateTime? assessedAt;

  const AssessmentResult({this.riskLevel, this.recommendation, this.confidence, this.securityScore, this.assessedAt});

  factory AssessmentResult.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const AssessmentResult();
    return AssessmentResult(
      riskLevel: json['riskLevel'] as String?,
      recommendation: json['recommendation'] as String?,
      confidence: json['confidence'] as int?,
      securityScore: json['securityScore'] as int?,
      assessedAt: json['assessedAt'] != null ? DateTime.tryParse(json['assessedAt'] as String) : null,
    );
  }
}

/// One real finding restated for the "evidence" list (Phase 10A, Part 3) -
/// a compact subset of the same Vulnerability fields already in
/// SecurityAssessment.vulnerabilities (cwe/type/severity/confidence/
/// source/sink only, no fileName/description/status), not a second,
/// separately-computed piece of evidence.
class RecommendationEvidence {
  final String? cwe;
  final String? type;
  final String? severity;
  final int? confidence;
  final String? source;
  final String? sink;

  const RecommendationEvidence({this.cwe, this.type, this.severity, this.confidence, this.source, this.sink});

  factory RecommendationEvidence.fromJson(Map<String, dynamic> json) {
    return RecommendationEvidence(
      cwe: json['cwe'] as String?,
      type: json['type'] as String?,
      severity: json['severity'] as String?,
      confidence: json['confidence'] as int?,
      source: json['source'] as String?,
      sink: json['sink'] as String?,
    );
  }
}

/// The "recommendation" block added in Phase 10A - "decision" mirrors
/// AssessmentResult.recommendation (same real value), "reason" is the
/// real stored recommendations.reason text (null when the backend never
/// stored one - NEVER replaced with a generated fallback sentence here,
/// Part 2/6: "Do not invent natural-language explanations"), and
/// "evidence" is the same real per-finding data restated compactly.
/// Absent entirely on an older/mocked response - defaults to an empty,
/// all-null instance rather than throwing (Part 4: backward compatible).
class RecommendationExplanation {
  final String? decision;
  final String? reason;
  final List<RecommendationEvidence> evidence;

  const RecommendationExplanation({this.decision, this.reason, this.evidence = const []});

  factory RecommendationExplanation.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const RecommendationExplanation();
    return RecommendationExplanation(
      decision: json['decision'] as String?,
      reason: json['reason'] as String?,
      evidence: (json['evidence'] as List<dynamic>?)
              ?.map((e) => RecommendationEvidence.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
    );
  }
}

/// debuggable/allowBackup - security-relevant signals, explicitly NOT
/// vulnerabilities on their own (Part 11).
class SecurityMetadata {
  final bool? debuggable;
  final bool? allowBackup;

  const SecurityMetadata({this.debuggable, this.allowBackup});

  factory SecurityMetadata.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const SecurityMetadata();
    return SecurityMetadata(
      debuggable: json['debuggable'] as bool?,
      allowBackup: json['allowBackup'] as bool?,
    );
  }
}

/// The full GET /apps/{id}/security response. When the app has never
/// been assessed, the backend returns only {assessed:false, message},
/// and every other field here stays null/empty - the UI must show that
/// honestly (Part 6/18), never a fabricated risk level.
class SecurityAssessment {
  final bool assessed;
  final String? message;
  final int? applicationId;
  final String? applicationName;
  final String? packageName;
  final AppVersionModel? version;
  final AssessmentResult assessment;
  final List<VulnerabilityModel> vulnerabilities;
  final RecommendationExplanation recommendation;
  final SecurityMetadata securityMetadata;
  final FullCompatibilityResult? compatibility;

  const SecurityAssessment({
    required this.assessed,
    this.message,
    this.applicationId,
    this.applicationName,
    this.packageName,
    this.version,
    this.assessment = const AssessmentResult(),
    this.vulnerabilities = const [],
    this.recommendation = const RecommendationExplanation(),
    this.securityMetadata = const SecurityMetadata(),
    this.compatibility,
  });

  factory SecurityAssessment.fromJson(Map<String, dynamic> json) {
    final assessed = json['assessed'] as bool? ?? false;
    if (!assessed) {
      return SecurityAssessment(assessed: false, message: json['message'] as String?);
    }
    final app = json['application'] as Map<String, dynamic>?;
    return SecurityAssessment(
      assessed: true,
      applicationId: app?['id'] as int?,
      applicationName: app?['name'] as String?,
      packageName: app?['packageName'] as String?,
      version: json['version'] != null ? AppVersionModel.fromJson(json['version'] as Map<String, dynamic>) : null,
      assessment: AssessmentResult.fromJson(json['assessment'] as Map<String, dynamic>?),
      vulnerabilities: (json['vulnerabilities'] as List<dynamic>?)
              ?.map((v) => VulnerabilityModel.fromJson(v as Map<String, dynamic>))
              .toList() ??
          const [],
      recommendation: RecommendationExplanation.fromJson(json['recommendation'] as Map<String, dynamic>?),
      securityMetadata: SecurityMetadata.fromJson(json['securityMetadata'] as Map<String, dynamic>?),
      compatibility: json['compatibility'] != null
          ? FullCompatibilityResult.fromJson(json['compatibility'] as Map<String, dynamic>)
          : null,
    );
  }
}
