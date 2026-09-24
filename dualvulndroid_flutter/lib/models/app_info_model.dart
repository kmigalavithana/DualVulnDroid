import 'user_preferences_model.dart';

/// How "resource-heavy" an app is, on a coarse scale actually usable
/// without per-device telemetry we don't have (Part 7/8). This is a
/// characteristic of the app (declared in the dataset), not a
/// measurement of any specific device. `null` on [AppInfo.resourceLevel]
/// means genuinely unknown - never guessed from real Play Store metadata,
/// which does not report this.
enum ResourceLevel {
  light('Light'),
  moderate('Moderate'),
  heavy('Heavy');

  final String label;
  const ResourceLevel(this.label);
}

/// One recommendable application and everything the recommendation
/// engine needs to score it.
///
/// Two data provenances feed this same type:
/// - The curated demo dataset (data/sample_apps_data.dart,
///   `isCuratedSample = true`, `isLiveData = false`) - every field known,
///   used only for onboarding/testing, never the production
///   Discover/recommendation flow.
/// - Real Google Play data (`isLiveData = true`, `dataSource =
///   "google_play"`), fetched via AppRepository from SmartApp's own
///   backend (never SerpApi directly - see AppRepository's doc comment).
///   Google Play does not report trackerCount/isOpenSource/
///   supportsOffline/hasAds/isFree/sizeMb/resourceLevel, so these stay
///   `null` ("unavailable") rather than being guessed (Part 10/11: "Do
///   not assume... when data is missing" / "Google Play metadata alone
///   must NOT be treated as authoritative tracker/privacy information").
class AppInfo {
  final String id;
  final String name;
  final String? packageName;
  final AppCategory category;

  /// The category text exactly as the live data source returned it (e.g.
  /// Google Play's "Productivity" or "Health & Fitness"). [category] is
  /// SmartApp's own mapping of it, and becomes [AppCategory.other] both
  /// for an unmapped label and for a missing one - this field keeps the two
  /// apart. `null` when the source returned no category (or for demo data).
  final String? sourceCategory;
  final String? description;

  /// A Material icon key (see CategoryIcons) used as a fallback when no
  /// real remote [iconUrl] is available (or fails to load) - never a
  /// fabricated photo of a real app's actual icon.
  final String iconKey;

  /// A real Google Play icon image URL, when available. `null` for the
  /// curated demo dataset (which uses [iconKey] only) and for any live
  /// result the provider didn't return an icon for.
  final String? iconUrl;

  // ---- Recommendation-relevant app characteristics - all nullable.
  // `null` means "unavailable/unverified", scored neutrally by
  // RecommendationEngine and never treated as satisfying a preference
  // that depends on it (see satisfies() below).
  final double? sizeMb;
  final bool? hasAds;
  final int? trackerCount;
  final bool? isOpenSource;
  final bool? supportsOffline;
  final bool? isFree;
  final int? minimumAndroidSdk;
  final ResourceLevel? resourceLevel;

  /// 0-5. `null` when no rating is available (must be shown as
  /// "No rating available", never defaulted to 0 or a guess).
  final double? rating;
  final int? reviewCount;

  final String? playStoreUrl;
  final String? developer;

  /// Details-only real metadata (populated only via
  /// AppRepository.getAppDetails - a search result alone doesn't carry
  /// these) - all `null`/empty until fetched, never invented.
  final String? version;
  final String? releaseDate;
  final String? updatedOn;
  final List<String> screenshots;

  /// `true` for every entry in the curated demo dataset - clearly
  /// separates verified/live app metadata from curated/demo data.
  final bool isCuratedSample;

  /// `true` only for a result that actually came from the real Google
  /// Play provider via SmartApp's backend - never set true by hand for
  /// demo data.
  final bool isLiveData;

  /// e.g. "google_play" when [isLiveData] is true; `null` for demo data.
  final String? dataSource;

  // ---- Verified metadata from the backend's enrichment layer. Each is
  // `null`/empty unless a real source stated it - never inferred.
  /// Store price text (e.g. "$6.99") when Google Play lists a price.
  final String? price;
  final String? currency;
  final bool? inAppPurchases;
  /// Developer-declared Play "Data safety" statements (not verified by
  /// Google or SmartApp - shown as declared).
  final List<String> dataSafety;
  final List<String> trackerNames;
  final List<String>? permissions;
  /// e.g. "exodus" when [trackerCount] came from an Exodus report.
  final String? privacyDataSource;
  final String? privacyReportUpdatedAt;
  final String? license;
  final List<String> antiFeatures;
  final bool? fdroidAvailable;
  final String? fdroidSourceUrl;
  /// Every source that contributed data to this app, e.g.
  /// ["google_play", "google_play_details", "fdroid"].
  final List<String> metadataSources;

  const AppInfo({
    required this.id,
    required this.name,
    this.packageName,
    required this.category,
    this.sourceCategory,
    this.description,
    required this.iconKey,
    this.iconUrl,
    this.sizeMb,
    this.hasAds,
    this.trackerCount,
    this.isOpenSource,
    this.supportsOffline,
    this.isFree,
    this.minimumAndroidSdk,
    this.resourceLevel,
    this.rating,
    this.reviewCount,
    this.playStoreUrl,
    this.developer,
    this.version,
    this.releaseDate,
    this.updatedOn,
    this.screenshots = const [],
    this.isCuratedSample = true,
    this.isLiveData = false,
    this.dataSource,
    this.price,
    this.currency,
    this.inAppPurchases,
    this.dataSafety = const [],
    this.trackerNames = const [],
    this.permissions,
    this.privacyDataSource,
    this.privacyReportUpdatedAt,
    this.license,
    this.antiFeatures = const [],
    this.fdroidAvailable,
    this.fdroidSourceUrl,
    this.metadataSources = const [],
  });

  /// Whether this app verifiably meets [preference]: `true` (verified
  /// yes), `false` (verified no), or `null` - no source verified the
  /// underlying attribute, so it can be neither credited nor held against
  /// the app.
  bool? preferenceStatus(AppPreference preference) {
    switch (preference) {
      case AppPreference.lightweight:
        final level = resourceLevel;
        return level == null ? null : level == ResourceLevel.light;
      case AppPreference.privacyFriendly:
        final trackers = trackerCount;
        return trackers == null ? null : trackers == 0;
      case AppPreference.noAds:
        final ads = hasAds;
        return ads == null ? null : !ads;
      case AppPreference.offlineSupport:
        return supportsOffline;
      case AppPreference.free:
        return isFree;
      case AppPreference.openSource:
        return isOpenSource;
      case AppPreference.lowStorageUsage:
        final size = sizeMb;
        return size == null ? null : size <= 30;
    }
  }

  /// The 7 recommendation attributes (same list as the backend's
  /// metadata_coverage()): rating, privacy, resource, price, ads, open
  /// source, offline - each entry is whether it is verified.
  List<bool> get _coverageSignals => [
        rating != null,
        trackerCount != null,
        sizeMb != null || resourceLevel != null,
        isFree != null,
        hasAds != null,
        isOpenSource != null,
        supportsOffline != null,
      ];

  /// Share (0-1) of those attributes that are verified for this app - a
  /// data-completeness figure, NOT a prediction confidence or accuracy.
  double get metadataCoverage {
    final signals = _coverageSignals;
    return signals.where((s) => s).length / signals.length;
  }

  /// Which of the 7 user-facing preferences this app actually,
  /// VERIFIABLY satisfies - the single source of truth both the scoring
  /// engine (preferenceScore) and the "why this app" UI read from. An
  /// unknown/unverified underlying field never counts as satisfying a
  /// preference (Part 10: "Known value vs Unavailable value" - unknown is
  /// not assumed favorable).
  bool satisfies(AppPreference preference) {
    switch (preference) {
      case AppPreference.lightweight:
        return resourceLevel == ResourceLevel.light;
      case AppPreference.privacyFriendly:
        return trackerCount == 0;
      case AppPreference.noAds:
        return hasAds == false;
      case AppPreference.offlineSupport:
        return supportsOffline == true;
      case AppPreference.free:
        return isFree == true;
      case AppPreference.openSource:
        return isOpenSource == true;
      case AppPreference.lowStorageUsage:
        return sizeMb != null && sizeMb! <= 30;
    }
  }

  /// Parses SmartApp's own backend response shape (never SerpApi's raw
  /// shape directly - see AppRepository) for both the search endpoint's
  /// `apps[]` items and the details endpoint's `app` object, which share
  /// the same base fields (SmartAppItem vs SmartAppDetails on the
  /// backend). Every field is read defensively - a missing/null key
  /// becomes `null` here, never a fabricated default.
  factory AppInfo.fromSmartAppJson(Map<String, dynamic> json) {
    final packageName = json['packageName'] as String?;
    final rawScreenshots = json['screenshots'];
    return AppInfo(
      id: (json['id'] as String?) ?? packageName ?? (json['name'] as String? ?? 'unknown'),
      name: (json['name'] as String?) ?? 'Unavailable',
      packageName: packageName,
      category: _categoryFromLabel(json['category'] as String?),
      sourceCategory: _nonEmpty(json['category'] as String?),
      description: json['description'] as String?,
      iconKey: 'apps_outlined',
      iconUrl: json['iconUrl'] as String?,
      rating: (json['rating'] as num?)?.toDouble(),
      reviewCount: (json['reviewCount'] as num?)?.toInt(),
      playStoreUrl: json['playStoreUrl'] as String?,
      developer: json['developer'] as String?,
      version: json['version'] as String?,
      releaseDate: json['releaseDate'] as String?,
      updatedOn: json['updatedOn'] as String?,
      screenshots: rawScreenshots is List ? rawScreenshots.whereType<String>().toList() : const [],
      isCuratedSample: false,
      isLiveData: json['realData'] == true || json['isLiveData'] == true,
      dataSource: json['source'] as String? ?? json['dataSource'] as String?,
      sizeMb: (json['sizeMb'] as num?)?.toDouble(),
      hasAds: json['hasAds'] as bool?,
      trackerCount: (json['trackerCount'] as num?)?.toInt(),
      isOpenSource: json['isOpenSource'] as bool?,
      supportsOffline: json['supportsOffline'] as bool?,
      isFree: json['isFree'] as bool?,
      price: json['price'] as String?,
      currency: json['currency'] as String?,
      inAppPurchases: json['inAppPurchases'] as bool?,
      dataSafety: _strings(json['dataSafety']),
      trackerNames: _strings(json['trackerNames']),
      permissions: json['permissions'] is List ? _strings(json['permissions']) : null,
      privacyDataSource: json['privacyDataSource'] as String?,
      privacyReportUpdatedAt: json['privacyMetadataUpdatedAt'] as String?,
      license: json['license'] as String?,
      antiFeatures: _strings(json['antiFeatures']),
      fdroidAvailable: json['fdroidAvailable'] as bool?,
      fdroidSourceUrl: json['fdroidSourceUrl'] as String?,
      metadataSources: _strings(json['metadataSources']),
    );
  }

  static String? _nonEmpty(String? value) {
    final trimmed = value?.trim();
    return trimmed == null || trimmed.isEmpty ? null : trimmed;
  }

  static List<String> _strings(Object? value) => value is List ? value.whereType<String>().toList() : const [];

  /// Keeps the verified metadata of [previous] when a refreshed copy of
  /// the same app (App Details' re-fetch) didn't carry a field.
  AppInfo mergedWith(AppInfo previous) {
    return AppInfo(
      id: id,
      name: name,
      packageName: packageName ?? previous.packageName,
      category: category == AppCategory.other ? previous.category : category,
      sourceCategory: sourceCategory ?? previous.sourceCategory,
      description: description ?? previous.description,
      iconKey: iconKey,
      iconUrl: iconUrl ?? previous.iconUrl,
      sizeMb: sizeMb ?? previous.sizeMb,
      hasAds: hasAds ?? previous.hasAds,
      trackerCount: trackerCount ?? previous.trackerCount,
      isOpenSource: isOpenSource ?? previous.isOpenSource,
      supportsOffline: supportsOffline ?? previous.supportsOffline,
      isFree: isFree ?? previous.isFree,
      minimumAndroidSdk: minimumAndroidSdk ?? previous.minimumAndroidSdk,
      resourceLevel: resourceLevel ?? previous.resourceLevel,
      rating: rating ?? previous.rating,
      reviewCount: reviewCount ?? previous.reviewCount,
      playStoreUrl: playStoreUrl ?? previous.playStoreUrl,
      developer: developer ?? previous.developer,
      version: version ?? previous.version,
      releaseDate: releaseDate ?? previous.releaseDate,
      updatedOn: updatedOn ?? previous.updatedOn,
      screenshots: screenshots.isNotEmpty ? screenshots : previous.screenshots,
      isCuratedSample: isCuratedSample,
      isLiveData: isLiveData,
      dataSource: dataSource ?? previous.dataSource,
      price: price ?? previous.price,
      currency: currency ?? previous.currency,
      inAppPurchases: inAppPurchases ?? previous.inAppPurchases,
      dataSafety: dataSafety.isNotEmpty ? dataSafety : previous.dataSafety,
      trackerNames: trackerNames.isNotEmpty ? trackerNames : previous.trackerNames,
      permissions: permissions ?? previous.permissions,
      privacyDataSource: privacyDataSource ?? previous.privacyDataSource,
      privacyReportUpdatedAt: privacyReportUpdatedAt ?? previous.privacyReportUpdatedAt,
      license: license ?? previous.license,
      antiFeatures: antiFeatures.isNotEmpty ? antiFeatures : previous.antiFeatures,
      fdroidAvailable: fdroidAvailable ?? previous.fdroidAvailable,
      fdroidSourceUrl: fdroidSourceUrl ?? previous.fdroidSourceUrl,
      metadataSources: {...previous.metadataSources, ...metadataSources}.toList(),
    );
  }

  /// Best-effort match against SmartApp's own fixed category set - a
  /// live category label the provider returns that doesn't match one of
  /// these exactly falls back to [AppCategory.other] rather than being
  /// dropped or guessed at further (Part 8: "Do not fabricate category
  /// information").
  static AppCategory _categoryFromLabel(String? label) {
    if (label == null) return AppCategory.other;
    final normalized = label.trim().toLowerCase();
    for (final category in AppCategory.values) {
      if (category.label.toLowerCase() == normalized) return category;
    }
    // A couple of common real Google Play category names that don't
    // literally match SmartApp's own labels but clearly correspond.
    const aliases = {
      'photography': AppCategory.photoEditing,
      'video players & editors': AppCategory.videoEditing,
      'productivity': AppCategory.productivity,
      'communication': AppCategory.communication,
      'tools': AppCategory.utilities,
      'books & reference': AppCategory.documents,
      'education': AppCategory.education,
      'music & audio': AppCategory.music,
    };
    return aliases[normalized] ?? AppCategory.other;
  }
}
