import '../models/app_info_model.dart';
import '../models/device_profile_model.dart';
import '../models/user_preferences_model.dart';
import 'recommendation_engine.dart';

/// Which scoring implementation produced a [RecommendationPrediction] -
/// listed here so future model comparisons (Evaluation Mode) can name
/// candidates that do not exist yet without pretending they have results.
enum ModelType {
  ruleBased('Rule-Based (current)'),
  logisticRegression('Logistic Regression'),
  randomForest('Random Forest'),
  xgboost('XGBoost');

  final String label;
  const ModelType(this.label);
}

/// One model's real prediction for one app: a 0-100 score plus how
/// confident that specific model is. Deliberately mirrors
/// [RecommendationResult]'s shape closely enough to be compared
/// side-by-side, without depending on the rule-based engine's internal
/// weighted breakdown (a future ML model has no such breakdown).
class RecommendationPrediction {
  final AppInfo app;
  final double score;
  final double confidence;
  final ModelType modelType;

  const RecommendationPrediction({
    required this.app,
    required this.score,
    required this.confidence,
    required this.modelType,
  });
}

/// The interface any recommendation scorer - rule-based today, an
/// ML-trained model later - must implement, so the Evaluation screen can
/// run and compare candidates without depending on which one is real.
/// Part 15 is explicit
/// that no fake ML model may be added; the only concrete implementation
/// shipped here is [RuleBasedRecommendationModel], a thin adapter over
/// the existing, real [RecommendationEngine]. A LogisticRegression /
/// RandomForest / XGBoost implementation would be a separate class
/// implementing this same interface, trained and evaluated before it is
/// ever wired in - never stubbed with invented numbers.
abstract class RecommendationModel {
  ModelType get modelType;

  RecommendationPrediction predict({
    required AppInfo app,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
  });

  List<RecommendationPrediction> predictAll({
    required List<AppInfo> apps,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
  }) {
    final predictions = apps.map((a) => predict(app: a, preferences: preferences, device: device)).toList();
    predictions.sort((a, b) => b.score.compareTo(a.score));
    return predictions;
  }
}

/// Adapts the existing, real, weighted [RecommendationEngine] to the
/// [RecommendationModel] interface - the only model actually trained/
/// implemented in this build. Every value here is read straight off a
/// real [RecommendationResult]; nothing is invented for the adapter.
class RuleBasedRecommendationModel extends RecommendationModel {
  final RecommendationEngine _engine;

  RuleBasedRecommendationModel({RecommendationEngine engine = const RecommendationEngine()}) : _engine = engine;

  @override
  ModelType get modelType => ModelType.ruleBased;

  @override
  RecommendationPrediction predict({
    required AppInfo app,
    required UserPreferencesModel preferences,
    required DeviceProfileModel device,
  }) {
    final result = _engine.score(app: app, preferences: preferences, device: device);
    return RecommendationPrediction(
      app: app,
      score: result.breakdown.finalScore,
      confidence: result.confidence,
      modelType: modelType,
    );
  }
}
