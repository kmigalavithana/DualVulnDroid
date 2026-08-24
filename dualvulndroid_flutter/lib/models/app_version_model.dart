/// One `uses-feature` manifest declaration, as returned inside a version's
/// "features" list. NOTE: unlike the rest of this API, the backend
/// passes this list straight through from its stored JSON column
/// without re-casing it, so these particular keys are snake_case
/// (feature_name/gl_es_version/required_explicit), not camelCase like
/// everything else - this is a real, verified quirk of the actual
/// response, not a typo.
class FeatureDeclaration {
  final String? featureName;
  final String? glEsVersion;
  final bool? required;
  final bool requiredExplicit;

  const FeatureDeclaration({
    this.featureName,
    this.glEsVersion,
    this.required,
    this.requiredExplicit = false,
  });

  factory FeatureDeclaration.fromJson(Map<String, dynamic> json) {
    return FeatureDeclaration(
      featureName: json['feature_name'] as String?,
      glEsVersion: json['gl_es_version'] as String?,
      required: json['required'] as bool?,
      requiredExplicit: json['required_explicit'] as bool? ?? false,
    );
  }
}

/// Real facts about one specific compiled build - matches the "version"
/// object inside GET /apps/{id}/security and POST /upload-apk. Every
/// field is nullable: null means the backend genuinely never determined
/// it, never a guessed default (Phase 8A/8B/8C's core rule, carried
/// through unchanged into the UI layer).
class AppVersionModel {
  final int? id;
  final String? versionName;
  final int? versionCode;
  final DateTime? analyzedAt;
  final int? minSdkVersion;
  final int? targetSdkVersion;
  final List<FeatureDeclaration> features;
  final List<String> abis;

  const AppVersionModel({
    this.id,
    this.versionName,
    this.versionCode,
    this.analyzedAt,
    this.minSdkVersion,
    this.targetSdkVersion,
    this.features = const [],
    this.abis = const [],
  });

  factory AppVersionModel.fromJson(Map<String, dynamic> json) {
    return AppVersionModel(
      id: json['id'] as int?,
      versionName: json['versionName'] as String?,
      versionCode: json['versionCode'] as int?,
      analyzedAt: json['analyzedAt'] != null ? DateTime.tryParse(json['analyzedAt'] as String) : null,
      minSdkVersion: json['minSdkVersion'] as int?,
      targetSdkVersion: json['targetSdkVersion'] as int?,
      features: (json['features'] as List<dynamic>?)
              ?.map((f) => FeatureDeclaration.fromJson(f as Map<String, dynamic>))
              .toList() ??
          const [],
      abis: (json['abis'] as List<dynamic>?)?.map((a) => a.toString()).toList() ?? const [],
    );
  }
}
