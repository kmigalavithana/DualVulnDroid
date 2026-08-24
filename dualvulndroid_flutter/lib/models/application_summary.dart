/// A search result / basic application record - matches GET /apps/search
/// and GET /apps/{id}'s real fields. Never carries a risk level or score
/// itself (Part 6: "do not display a fake risk level" for unassessed
/// search results) - that only ever comes from a real
/// SecurityAssessment, fetched separately.
class ApplicationSummary {
  final int id;
  final String appName;
  final String? packageName;
  final String? category;
  final String? developer;
  final String? iconUrl;

  const ApplicationSummary({
    required this.id,
    required this.appName,
    this.packageName,
    this.category,
    this.developer,
    this.iconUrl,
  });

  /// GET /apps/search results: {id, app_name, package_name, category}.
  factory ApplicationSummary.fromSearchJson(Map<String, dynamic> json) {
    return ApplicationSummary(
      id: json['id'] as int,
      appName: json['app_name'] as String? ?? 'Unknown application',
      packageName: json['package_name'] as String?,
      category: json['category'] as String?,
    );
  }

  /// GET /apps/{id}: {id, app_name, package_name, developer, category, icon_url}.
  factory ApplicationSummary.fromDetailJson(Map<String, dynamic> json) {
    return ApplicationSummary(
      id: json['id'] as int,
      appName: json['app_name'] as String? ?? 'Unknown application',
      packageName: json['package_name'] as String?,
      category: json['category'] as String?,
      developer: json['developer'] as String?,
      iconUrl: json['icon_url'] as String?,
    );
  }
}
