/// One explicit user reaction to a recommendation (Part 11). Only ever
/// recorded when the user actually taps a feedback button - never
/// inferred or pre-seeded.
enum FeedbackType {
  useful('Useful'),
  notUseful('Not useful'),
  preferThis('Prefer this'),
  notForMe('Not for me');

  final String label;
  const FeedbackType(this.label);

  /// Whether this feedback type treats the app as a genuinely relevant
  /// recommendation - used by [EvaluationEngine] as the real relevance
  /// label behind Precision@K/Recall@K/NDCG@K (Part 14). Never inferred
  /// from anything but the user's own explicit choice.
  bool get isPositive => this == FeedbackType.useful || this == FeedbackType.preferThis;
}

/// One real, locally-recorded piece of feedback on a specific app.
class FeedbackEntry {
  final String appId;
  final FeedbackType type;
  final DateTime timestamp;

  const FeedbackEntry({required this.appId, required this.type, required this.timestamp});

  Map<String, dynamic> toJson() => {
        'appId': appId,
        'type': type.name,
        'timestamp': timestamp.toIso8601String(),
      };

  static FeedbackEntry? fromJson(Map<String, dynamic> json) {
    final appId = json['appId'] as String?;
    final typeName = json['type'] as String?;
    if (appId == null || typeName == null) return null;
    FeedbackType? type;
    for (final t in FeedbackType.values) {
      if (t.name == typeName) {
        type = t;
        break;
      }
    }
    if (type == null) return null;
    return FeedbackEntry(
      appId: appId,
      type: type,
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ?? DateTime.now(),
    );
  }
}
