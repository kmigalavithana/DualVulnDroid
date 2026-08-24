/// The three explicit states the backend ever returns for compatibility -
/// mirrored exactly, never reduced to a boolean (Phase 8C/9, Part 12).
enum CompatibilityStatus { compatible, incompatible, notAvailable, unknown }

CompatibilityStatus _parseStatus(dynamic raw) {
  switch (raw) {
    case 'COMPATIBLE':
      return CompatibilityStatus.compatible;
    case 'INCOMPATIBLE':
      return CompatibilityStatus.incompatible;
    case 'NOT_AVAILABLE':
      return CompatibilityStatus.notAvailable;
    default:
      return CompatibilityStatus.unknown;
  }
}

/// One individual check (androidVersion / requiredFeatures / abi).
/// "missing" is only ever populated on requiredFeatures, and only when
/// it's genuinely INCOMPATIBLE - real feature names the backend found
/// missing, never invented here.
class CompatibilityCheck {
  final CompatibilityStatus status;
  final List<String> missing;

  const CompatibilityCheck({required this.status, this.missing = const []});

  factory CompatibilityCheck.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const CompatibilityCheck(status: CompatibilityStatus.notAvailable);
    return CompatibilityCheck(
      status: _parseStatus(json['status']),
      missing: (json['missing'] as List<dynamic>?)?.map((m) => m.toString()).toList() ?? const [],
    );
  }
}

/// The combined result - matches "compatibility" in both GET
/// /apps/{id}/security and POST /apps/{id}/compatibility.
class FullCompatibilityResult {
  final CompatibilityStatus status;
  final CompatibilityCheck androidVersion;
  final CompatibilityCheck requiredFeatures;
  final CompatibilityCheck abi;
  final List<String> reasons;

  const FullCompatibilityResult({
    required this.status,
    required this.androidVersion,
    required this.requiredFeatures,
    required this.abi,
    this.reasons = const [],
  });

  factory FullCompatibilityResult.fromJson(Map<String, dynamic> json) {
    final checks = json['checks'] as Map<String, dynamic>? ?? const {};
    return FullCompatibilityResult(
      status: _parseStatus(json['status']),
      androidVersion: CompatibilityCheck.fromJson(checks['androidVersion'] as Map<String, dynamic>?),
      requiredFeatures: CompatibilityCheck.fromJson(checks['requiredFeatures'] as Map<String, dynamic>?),
      abi: CompatibilityCheck.fromJson(checks['abi'] as Map<String, dynamic>?),
      reasons: (json['reasons'] as List<dynamic>?)?.map((r) => r.toString()).toList() ?? const [],
    );
  }
}

/// Always NOT_AVAILABLE today (no verified RAM/CPU-model requirement
/// source exists in the backend) - modeled explicitly rather than
/// ignored, so the UI can show an honest "not evaluated" state instead
/// of silently omitting it.
class HardwareCompatibilityResult {
  final CompatibilityStatus status;
  final String reason;

  const HardwareCompatibilityResult({required this.status, required this.reason});

  factory HardwareCompatibilityResult.fromJson(Map<String, dynamic>? json) {
    if (json == null) {
      return const HardwareCompatibilityResult(status: CompatibilityStatus.notAvailable, reason: '');
    }
    return HardwareCompatibilityResult(
      status: _parseStatus(json['status']),
      reason: json['reason'] as String? ?? '',
    );
  }
}

/// The backend's own final recommendation string - never recomputed
/// client-side (Part 14: "Do NOT calculate a new score").
class FinalRecommendation {
  final String recommendation;
  final String reason;

  const FinalRecommendation({required this.recommendation, required this.reason});

  factory FinalRecommendation.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const FinalRecommendation(recommendation: 'SECURITY_ASSESSMENT_UNAVAILABLE', reason: '');
    return FinalRecommendation(
      recommendation: json['recommendation'] as String? ?? 'SECURITY_ASSESSMENT_UNAVAILABLE',
      reason: json['reason'] as String? ?? '',
    );
  }
}

/// The full POST /apps/{id}/compatibility response.
class CompatibilityResponse {
  final int applicationId;
  final String? applicationName;
  final FullCompatibilityResult compatibility;
  final HardwareCompatibilityResult hardwareCompatibility;
  final FinalRecommendation finalRecommendation;

  const CompatibilityResponse({
    required this.applicationId,
    this.applicationName,
    required this.compatibility,
    required this.hardwareCompatibility,
    required this.finalRecommendation,
  });

  factory CompatibilityResponse.fromJson(Map<String, dynamic> json) {
    final app = json['application'] as Map<String, dynamic>? ?? const {};
    return CompatibilityResponse(
      applicationId: app['id'] as int,
      applicationName: app['name'] as String?,
      compatibility: FullCompatibilityResult.fromJson(json['compatibility'] as Map<String, dynamic>),
      hardwareCompatibility: HardwareCompatibilityResult.fromJson(json['hardwareCompatibility'] as Map<String, dynamic>?),
      finalRecommendation: FinalRecommendation.fromJson(json['finalRecommendation'] as Map<String, dynamic>?),
    );
  }
}
