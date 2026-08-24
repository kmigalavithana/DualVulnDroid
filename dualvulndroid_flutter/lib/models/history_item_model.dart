/// One entry from GET /user/history's "history" list - matches
/// db/crud.py's get_user_history() output: {scan_id, application_id,
/// app_name, package_name, security_score, risk_level, recommendation,
/// timestamp}. application_id was added to the backend in Phase 9
/// specifically so this screen can navigate straight to
/// ApplicationDetailsScreen (Part 16) - see the Phase 9 report for why.
class HistoryItem {
  final int scanId;
  final int? applicationId;
  final String? appName;
  final String? packageName;
  final int? securityScore;
  final String? riskLevel;
  final String? recommendation;
  final DateTime? timestamp;

  const HistoryItem({
    required this.scanId,
    this.applicationId,
    this.appName,
    this.packageName,
    this.securityScore,
    this.riskLevel,
    this.recommendation,
    this.timestamp,
  });

  factory HistoryItem.fromJson(Map<String, dynamic> json) {
    return HistoryItem(
      scanId: json['scan_id'] as int,
      applicationId: json['application_id'] as int?,
      appName: json['app_name'] as String?,
      packageName: json['package_name'] as String?,
      securityScore: json['security_score'] as int?,
      riskLevel: json['risk_level'] as String?,
      recommendation: json['recommendation'] as String?,
      timestamp: json['timestamp'] != null ? DateTime.tryParse(json['timestamp'] as String) : null,
    );
  }
}
