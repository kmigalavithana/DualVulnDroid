/// One real CWE-89/CWE-295 finding from POST /upload-apk's "codeAnalysis"
/// block - every field is exactly what apk_code_scanner.py actually
/// reported, never invented in the UI. "file" always points at
/// DECOMPILED, RECONSTRUCTED code (prefixed "decompiled/" by the
/// backend), never the app's original source - see ApkCodeAnalysis.note.
class ApkCodeFinding {
  final String? type;
  final String? cwe;
  final String? file;
  final int? line;
  final num? confidence;
  final String? severity;
  final List<String> explanation;

  const ApkCodeFinding({
    this.type,
    this.cwe,
    this.file,
    this.line,
    this.confidence,
    this.severity,
    this.explanation = const [],
  });

  factory ApkCodeFinding.fromJson(Map<String, dynamic> json) {
    return ApkCodeFinding(
      type: json['type'] as String?,
      cwe: json['cwe'] as String?,
      file: json['file'] as String?,
      line: json['line'] as int?,
      confidence: json['confidence'] as num?,
      severity: json['severity'] as String?,
      explanation: (json['explanation'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? const [],
    );
  }
}

/// The real "codeAnalysis" block - CWE-89/CWE-295 findings from
/// decompiling the uploaded APK's DEX bytecode, via the same detection
/// pipeline the IDE plugin uses (see backend/apk_code_scanner.py).
class ApkCodeAnalysis {
  final int filesScanned;
  final int classesTotal;
  final int filesSkippedThirdParty;
  final bool truncated;
  final String? truncationReason;
  final int totalFindings;
  final int cwe89Count;
  final int cwe295Count;
  final List<ApkCodeFinding> findings;
  final String? note;

  const ApkCodeAnalysis({
    this.filesScanned = 0,
    this.classesTotal = 0,
    this.filesSkippedThirdParty = 0,
    this.truncated = false,
    this.truncationReason,
    this.totalFindings = 0,
    this.cwe89Count = 0,
    this.cwe295Count = 0,
    this.findings = const [],
    this.note,
  });

  /// Display-side check of the same invariant the backend already
  /// guarantees (Phase 7: "verify this both backend-side and
  /// Flutter-side") - never a second computation that could disagree with
  /// the server's counts, just an assertion that they're self-consistent.
  bool get countsAreConsistent => totalFindings == cwe89Count + cwe295Count;

  factory ApkCodeAnalysis.fromJson(Map<String, dynamic>? json) {
    if (json == null) return const ApkCodeAnalysis();
    return ApkCodeAnalysis(
      filesScanned: json['filesScanned'] as int? ?? 0,
      classesTotal: json['classesTotal'] as int? ?? 0,
      filesSkippedThirdParty: json['filesSkippedThirdParty'] as int? ?? 0,
      truncated: json['truncated'] as bool? ?? false,
      truncationReason: json['truncationReason'] as String?,
      totalFindings: json['totalFindings'] as int? ?? 0,
      cwe89Count: json['cwe89Count'] as int? ?? 0,
      cwe295Count: json['cwe295Count'] as int? ?? 0,
      findings: (json['findings'] as List<dynamic>?)
              ?.map((f) => ApkCodeFinding.fromJson(f as Map<String, dynamic>))
              .toList() ??
          const [],
      note: json['note'] as String?,
    );
  }
}

/// The full real POST /upload-apk response - manifest/permission/URL
/// fields (already existed before this phase) plus the new codeAnalysis
/// block. Never fabricates a field the backend didn't send.
class ApkScanResult {
  final int? scanId;
  final int? applicationId;
  final String apkName;
  final String? packageName;
  final String? riskLevel;
  final bool vulnerable;
  final int? securityScore;
  final String? explanation;
  final List<String> dangerousPermissions;
  final int maliciousUrlCount;
  final ApkCodeAnalysis codeAnalysis;

  const ApkScanResult({
    this.scanId,
    this.applicationId,
    required this.apkName,
    this.packageName,
    this.riskLevel,
    this.vulnerable = false,
    this.securityScore,
    this.explanation,
    this.dangerousPermissions = const [],
    this.maliciousUrlCount = 0,
    this.codeAnalysis = const ApkCodeAnalysis(),
  });

  factory ApkScanResult.fromJson(Map<String, dynamic> json) {
    final application = json['application'] as Map<String, dynamic>?;
    return ApkScanResult(
      scanId: json['scan_id'] as int?,
      applicationId: application?['id'] as int?,
      apkName: json['app_name'] as String? ?? 'Uploaded APK',
      packageName: json['package_name'] as String?,
      riskLevel: json['risk_level'] as String?,
      vulnerable: json['vulnerable'] as bool? ?? false,
      securityScore: json['security_score'] as int?,
      explanation: json['explanation'] as String?,
      dangerousPermissions: (json['dangerous_permissions'] as List<dynamic>?)?.map((p) => p.toString()).toList() ?? const [],
      maliciousUrlCount: (json['malicious_urls'] as List<dynamic>?)?.length ?? 0,
      codeAnalysis: ApkCodeAnalysis.fromJson(json['codeAnalysis'] as Map<String, dynamic>?),
    );
  }
}
