import '../models/app_info_model.dart';
import '../models/device_profile_model.dart';
import '../models/user_preferences_model.dart';

/// Research Evaluation Mode data model. Everything here is stored
/// separately from production data (history, favorites, feedback, app
/// interactions) - see EvaluationRepository - and is only ever created by
/// an explicit evaluator action. Nothing is generated from SmartApp's own
/// recommendation scores.

/// The ranking configurations compared in a paired evaluation. Only the
/// scoring method and which snapshot fields it may use differ; the
/// candidate set is identical.
enum EvaluationConfig {
  /// Before enrichment: the pre-availability-aware formula (neutral
  /// fallbacks, unverifiable preferences counted as unmet) on Google Play
  /// search fields only. See LegacyScorer for how it is reproduced.
  a('A', 'Before enrichment'),

  /// Current availability-aware scoring on Google Play search fields only.
  b('B', 'Availability-aware'),

  /// Current availability-aware scoring on the full snapshot, including
  /// verified enrichment (store facts, Exodus, F-Droid).
  c('C', 'Availability-aware + enrichment');

  final String code;
  final String label;
  const EvaluationConfig(this.code, this.label);

  static EvaluationConfig? byCode(String code) {
    for (final c in values) {
      if (c.code == code) return c;
    }
    return null;
  }
}

/// A frozen set of candidate apps, captured once from live data and reused
/// unchanged for every run that references [snapshotId].
class CandidateSnapshot {
  final String snapshotId;
  final DateTime collectedAt;

  /// The category label or query the candidates were fetched for.
  final String category;

  /// Each app exactly as captured - SmartApp backend field names (see
  /// snapshot_codec.dart). Never edited after capture.
  final List<Map<String, dynamic>> apps;

  const CandidateSnapshot({required this.snapshotId, required this.collectedAt, required this.category, required this.apps});

  List<String> get packageNames => [for (final a in apps) (a['packageName'] ?? a['id']) as String];

  Map<String, dynamic> toJson() => {
        'snapshotId': snapshotId,
        'collectedAt': collectedAt.toUtc().toIso8601String(),
        'category': category,
        'apps': apps,
      };

  factory CandidateSnapshot.fromJson(Map<String, dynamic> json) => CandidateSnapshot(
        snapshotId: json['snapshotId'] as String,
        collectedAt: DateTime.parse(json['collectedAt'] as String),
        category: json['category'] as String,
        apps: [for (final a in (json['apps'] as List)) Map<String, dynamic>.from(a as Map)],
      );
}

/// One participant's evaluation task: their preferences, a device
/// snapshot, and the candidate apps (from one frozen snapshot) to judge.
class EvaluationTask {
  final String taskId;
  final String participantId;
  final Set<AppPreference> preferences;
  final DeviceProfileModel deviceSnapshot;
  final String category;
  final String snapshotId;
  final List<String> candidateAppIds;

  /// The randomized order the candidates were shown in for judging
  /// (recorded for reproducibility); empty until judging starts.
  final List<String> presentationOrder;
  final DateTime createdAt;

  const EvaluationTask({
    required this.taskId,
    required this.participantId,
    required this.preferences,
    required this.deviceSnapshot,
    required this.category,
    required this.snapshotId,
    required this.candidateAppIds,
    this.presentationOrder = const [],
    required this.createdAt,
  });

  EvaluationTask withPresentationOrder(List<String> order) => EvaluationTask(
        taskId: taskId,
        participantId: participantId,
        preferences: preferences,
        deviceSnapshot: deviceSnapshot,
        category: category,
        snapshotId: snapshotId,
        candidateAppIds: candidateAppIds,
        presentationOrder: order,
        createdAt: createdAt,
      );

  UserPreferencesModel get userPreferences => UserPreferencesModel(selectedPreferences: preferences);

  Map<String, dynamic> toJson() => {
        'taskId': taskId,
        'participantId': participantId,
        'preferences': [for (final p in preferences) p.name],
        'deviceSnapshot': deviceToJson(deviceSnapshot),
        'category': category,
        'snapshotId': snapshotId,
        'candidateAppIds': candidateAppIds,
        'presentationOrder': presentationOrder,
        'createdAt': createdAt.toUtc().toIso8601String(),
      };

  factory EvaluationTask.fromJson(Map<String, dynamic> json) => EvaluationTask(
        taskId: json['taskId'] as String,
        participantId: json['participantId'] as String,
        preferences: {
          for (final name in (json['preferences'] as List).whereType<String>())
            for (final p in AppPreference.values)
              if (p.name == name) p,
        },
        deviceSnapshot: deviceFromJson(Map<String, dynamic>.from(json['deviceSnapshot'] as Map)),
        category: json['category'] as String,
        snapshotId: json['snapshotId'] as String,
        candidateAppIds: (json['candidateAppIds'] as List).cast<String>(),
        presentationOrder: ((json['presentationOrder'] as List?) ?? const []).cast<String>(),
        createdAt: DateTime.parse(json['createdAt'] as String),
      );
}

/// A human relevance judgment - the ONLY ground truth used by the
/// ranking metrics. 0 = Not suitable, 1 = Slightly suitable,
/// 2 = Suitable, 3 = Highly suitable.
class RelevanceLabel {
  final String taskId;
  final String participantId;
  final String packageName;
  final int grade;
  final DateTime labeledAt;

  RelevanceLabel({required this.taskId, required this.participantId, required this.packageName, required this.grade, required this.labeledAt}) {
    if (grade < 0 || grade > 3) throw ArgumentError.value(grade, 'grade', 'must be 0-3');
  }

  static const gradeNames = ['Not suitable', 'Slightly suitable', 'Suitable', 'Highly suitable'];

  Map<String, dynamic> toJson() => {
        'taskId': taskId,
        'participantId': participantId,
        'packageName': packageName,
        'grade': grade,
        'labeledAt': labeledAt.toUtc().toIso8601String(),
      };

  factory RelevanceLabel.fromJson(Map<String, dynamic> json) => RelevanceLabel(
        taskId: json['taskId'] as String,
        participantId: json['participantId'] as String,
        packageName: json['packageName'] as String,
        grade: json['grade'] as int,
        labeledAt: DateTime.parse(json['labeledAt'] as String),
      );
}

/// The optional 5-point Likert questionnaire. Stored only as evaluation
/// data - never mixed with implicit in-app interaction data.
class SurveyResponse {
  static const statements = [
    'Recommendations were relevant to my needs.',
    'The app helped me compare alternatives.',
    'I understood why an app was recommended.',
    'Device information was useful.',
    'The recommendation explanation was understandable.',
  ];
  static const scaleLabels = ['Strongly disagree', 'Disagree', 'Neutral', 'Agree', 'Strongly agree'];

  final String participantId;

  /// Statement index -> score 1-5. Unanswered statements are absent.
  final Map<int, int> answers;
  final DateTime submittedAt;

  SurveyResponse({required this.participantId, required this.answers, required this.submittedAt}) {
    for (final entry in answers.entries) {
      if (entry.key < 0 || entry.key >= statements.length) throw ArgumentError('unknown statement ${entry.key}');
      if (entry.value < 1 || entry.value > 5) throw ArgumentError.value(entry.value, 'score', 'must be 1-5');
    }
  }

  Map<String, dynamic> toJson() => {
        'participantId': participantId,
        'answers': {for (final e in answers.entries) '${e.key}': e.value},
        'submittedAt': submittedAt.toUtc().toIso8601String(),
      };

  factory SurveyResponse.fromJson(Map<String, dynamic> json) => SurveyResponse(
        participantId: json['participantId'] as String,
        answers: {for (final e in (json['answers'] as Map).entries) int.parse(e.key as String): e.value as int},
        submittedAt: DateTime.parse(json['submittedAt'] as String),
      );
}

/// One configuration's ranking for one task, with everything needed to
/// reproduce and audit it.
class RankingRun {
  final String evaluationId;
  final DateTime timestamp;
  final String snapshotId;
  final EvaluationConfig config;
  final String taskId;
  final String participantId;

  /// Candidate package names, best first.
  final List<String> ranking;

  /// Rounded match % per ranked package (same order) - recorded for audit,
  /// never used as ground truth.
  final List<int> scores;

  /// Wall-clock time of each timed ranking repetition, microseconds.
  final List<int> latenciesMicros;

  /// Recommendations whose displayed factor points matched the real
  /// RecommendationResult values, out of [explanationsChecked].
  final int explanationsConsistent;
  final int explanationsChecked;

  const RankingRun({
    required this.evaluationId,
    required this.timestamp,
    required this.snapshotId,
    required this.config,
    required this.taskId,
    required this.participantId,
    required this.ranking,
    required this.scores,
    required this.latenciesMicros,
    required this.explanationsConsistent,
    required this.explanationsChecked,
  });

  Map<String, dynamic> toJson() => {
        'evaluationId': evaluationId,
        'timestamp': timestamp.toUtc().toIso8601String(),
        'snapshotId': snapshotId,
        'config': config.code,
        'taskId': taskId,
        'participantId': participantId,
        'ranking': ranking,
        'scores': scores,
        'latenciesMicros': latenciesMicros,
        'explanationsConsistent': explanationsConsistent,
        'explanationsChecked': explanationsChecked,
      };

  factory RankingRun.fromJson(Map<String, dynamic> json) => RankingRun(
        evaluationId: json['evaluationId'] as String,
        timestamp: DateTime.parse(json['timestamp'] as String),
        snapshotId: json['snapshotId'] as String,
        config: EvaluationConfig.byCode(json['config'] as String)!,
        taskId: json['taskId'] as String,
        participantId: json['participantId'] as String,
        ranking: (json['ranking'] as List).cast<String>(),
        scores: (json['scores'] as List).cast<int>(),
        latenciesMicros: (json['latenciesMicros'] as List).cast<int>(),
        explanationsConsistent: json['explanationsConsistent'] as int,
        explanationsChecked: json['explanationsChecked'] as int,
      );
}

// ---- Device snapshot codec (DeviceProfileModel has no JSON of its own) ----

Map<String, dynamic> deviceToJson(DeviceProfileModel d) => {
      'androidSdkInt': d.androidSdkInt,
      'androidRelease': d.androidRelease,
      'ramTotalMb': d.ramTotalMb,
      'ramAvailableMb': d.ramAvailableMb,
      'isLowRamDevice': d.isLowRamDevice,
      'storageTotalBytes': d.storageTotalBytes,
      'storageFreeBytes': d.storageFreeBytes,
      'abis': d.abis,
      'manufacturer': d.manufacturer,
      'model': d.model,
      'batteryLevel': d.batteryLevel,
      'connectivityStatus': d.connectivityStatus.name,
    };

DeviceProfileModel deviceFromJson(Map<String, dynamic> j) => DeviceProfileModel(
      androidSdkInt: j['androidSdkInt'] as int?,
      androidRelease: j['androidRelease'] as String?,
      ramTotalMb: j['ramTotalMb'] as int?,
      ramAvailableMb: j['ramAvailableMb'] as int?,
      isLowRamDevice: j['isLowRamDevice'] as bool?,
      storageTotalBytes: j['storageTotalBytes'] as int?,
      storageFreeBytes: j['storageFreeBytes'] as int?,
      abis: ((j['abis'] as List?) ?? const []).cast<String>(),
      manufacturer: j['manufacturer'] as String?,
      model: j['model'] as String?,
      batteryLevel: j['batteryLevel'] as int?,
      connectivityStatus: ConnectivityStatus.values.firstWhere(
        (c) => c.name == j['connectivityStatus'],
        orElse: () => ConnectivityStatus.unavailable,
      ),
    );

// ---- Snapshot app codec ----------------------------------------------------

/// The Google Play SEARCH fields - all that configurations A and B may see.
const playSearchFields = {
  'id', 'name', 'packageName', 'category', 'description', 'iconUrl', 'rating', //
  'reviewCount', 'playStoreUrl', 'developer', 'realData', 'source',
};

/// An app as stored in a snapshot, using the SmartApp backend's field names
/// so AppInfo.fromSmartAppJson reads it back exactly. Only the fields a
/// live app can carry are written; `null` stays `null`.
Map<String, dynamic> appToSnapshotJson(AppInfo a) => {
      'id': a.id,
      'name': a.name,
      'packageName': a.packageName,
      'category': a.sourceCategory,
      'description': a.description,
      'iconUrl': a.iconUrl,
      'rating': a.rating,
      'reviewCount': a.reviewCount,
      'playStoreUrl': a.playStoreUrl,
      'developer': a.developer,
      'realData': a.isLiveData,
      'source': a.dataSource,
      'isFree': a.isFree,
      'price': a.price,
      'currency': a.currency,
      'hasAds': a.hasAds,
      'inAppPurchases': a.inAppPurchases,
      'dataSafety': a.dataSafety,
      'trackerCount': a.trackerCount,
      'trackerNames': a.trackerNames,
      'permissions': a.permissions,
      'privacyDataSource': a.privacyDataSource,
      'privacyMetadataUpdatedAt': a.privacyReportUpdatedAt,
      'isOpenSource': a.isOpenSource,
      'license': a.license,
      'antiFeatures': a.antiFeatures,
      'fdroidAvailable': a.fdroidAvailable,
      'fdroidSourceUrl': a.fdroidSourceUrl,
      'sizeMb': a.sizeMb,
      'supportsOffline': a.supportsOffline,
      'metadataSources': a.metadataSources.isEmpty ? [if (a.isLiveData) 'google_play'] : a.metadataSources,
      'metadataCoverage': a.metadataCoverage,
    };

/// The snapshot app as a given configuration may see it: A and B get only
/// the Google Play search fields; C gets everything captured.
AppInfo appForConfig(Map<String, dynamic> snapshotApp, EvaluationConfig config) {
  if (config == EvaluationConfig.c) return AppInfo.fromSmartAppJson(snapshotApp);
  final playOnly = {
    for (final e in snapshotApp.entries)
      if (playSearchFields.contains(e.key)) e.key: e.value,
    'metadataSources': ['google_play'],
  };
  return AppInfo.fromSmartAppJson(playOnly);
}
