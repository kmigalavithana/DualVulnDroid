/// One entry from GET /apps/{id}/alternatives - every field traces back
/// to a real stored Application/Scan row on the backend (Part 15/K/L).
/// No rating/download-count/popularity field exists here because the
/// backend never returns one; adding one here would mean inventing it.
class AlternativeApp {
  final int applicationId;
  final String name;
  final String? packageName;
  final String? riskLevel;
  final int? securityScore;
  final int? securityConfidence;
  final List<String> reasons;

  const AlternativeApp({
    required this.applicationId,
    required this.name,
    this.packageName,
    this.riskLevel,
    this.securityScore,
    this.securityConfidence,
    this.reasons = const [],
  });

  factory AlternativeApp.fromJson(Map<String, dynamic> json) {
    return AlternativeApp(
      applicationId: json['applicationId'] as int,
      name: json['name'] as String? ?? 'Unknown application',
      packageName: json['packageName'] as String?,
      riskLevel: json['riskLevel'] as String?,
      securityScore: json['securityScore'] as int?,
      securityConfidence: json['securityConfidence'] as int?,
      reasons: (json['reasons'] as List<dynamic>?)?.map((r) => r.toString()).toList() ?? const [],
    );
  }
}
