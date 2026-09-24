import 'dart:math';

/// Ranking-quality metrics over HUMAN relevance labels (0-3). Pure
/// functions; every undefined case returns `null` rather than a made-up
/// number.
///
/// Binary relevance for Precision/Recall: an app is "relevant" when its
/// grade is >= [relevantThreshold] (2 = Suitable).
///
///   Precision@K = |relevant in top K| / K
///   Recall@K    = |relevant in top K| / |relevant among all candidates|
///                 (undefined when no candidate is relevant)
///   DCG@K       = sum_{i=1..K} (2^rel_i - 1) / log2(i + 1)
///   NDCG@K      = DCG@K / IDCG@K, IDCG from the ideal (label-sorted)
///                 ordering; undefined when IDCG = 0 (every label is 0)
///
/// [ranking] must contain only labeled candidates: a missing label is never
/// guessed (EvaluationRunner skips tasks with incomplete labels).
class RankingMetrics {
  RankingMetrics._();

  static const int relevantThreshold = 2;

  static void _check(List<String> ranking, Map<String, int> labels, int k) {
    if (k <= 0) throw ArgumentError.value(k, 'k', 'must be positive');
    for (final id in ranking) {
      if (!labels.containsKey(id)) throw ArgumentError('no relevance label for $id');
    }
  }

  static double? precisionAtK(List<String> ranking, Map<String, int> labels, int k) {
    _check(ranking, labels, k);
    if (labels.isEmpty) return null;
    final hits = ranking.take(k).where((id) => labels[id]! >= relevantThreshold).length;
    return hits / k;
  }

  static double? recallAtK(List<String> ranking, Map<String, int> labels, int k) {
    _check(ranking, labels, k);
    final totalRelevant = labels.values.where((g) => g >= relevantThreshold).length;
    if (totalRelevant == 0) return null;
    final hits = ranking.take(k).where((id) => labels[id]! >= relevantThreshold).length;
    return hits / totalRelevant;
  }

  static double dcg(List<int> grades, int k) {
    var sum = 0.0;
    for (var i = 0; i < min(k, grades.length); i++) {
      sum += (pow(2, grades[i]) - 1) / (log(i + 2) / ln2);
    }
    return sum;
  }

  static double? ndcgAtK(List<String> ranking, Map<String, int> labels, int k) {
    _check(ranking, labels, k);
    final ideal = labels.values.toList()..sort((a, b) => b.compareTo(a));
    final idcg = dcg(ideal, k);
    if (idcg == 0) return null;
    return dcg([for (final id in ranking) labels[id]!], k) / idcg;
  }
}

/// Descriptive statistics over a list of numbers (null when empty).
class Summary {
  final int n;
  final double mean;
  final double median;
  final double p95;

  const Summary(this.n, this.mean, this.median, this.p95);

  static Summary? of(Iterable<num> values) {
    final sorted = values.map((v) => v.toDouble()).toList()..sort();
    if (sorted.isEmpty) return null;
    final n = sorted.length;
    final mean = sorted.reduce((a, b) => a + b) / n;
    return Summary(n, mean, percentile(sorted, 50), percentile(sorted, 95));
  }

  /// Linear-interpolation percentile (the "R-7"/NumPy default) of an
  /// already-sorted list.
  static double percentile(List<double> sorted, double p) {
    if (sorted.length == 1) return sorted.first;
    final rank = p / 100 * (sorted.length - 1);
    final lo = rank.floor();
    final hi = rank.ceil();
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (rank - lo);
  }
}

/// Wilcoxon signed-rank on paired differences. Zero differences are
/// dropped (Wilcox method); ties share average ranks. The normal
/// approximation (with continuity and tie correction) is only reported
/// for n >= 10 non-zero pairs - below that, callers should use exact
/// tables on the exported data; no p-value is invented.
class WilcoxonResult {
  final int n;
  final double wPlus;
  final double wMinus;
  final double? z;
  final double? pTwoSided;

  const WilcoxonResult(this.n, this.wPlus, this.wMinus, this.z, this.pTwoSided);

  static WilcoxonResult? compute(List<double> differences) {
    final nonZero = differences.where((d) => d != 0).toList();
    final n = nonZero.length;
    if (n == 0) return null;
    final order = List.generate(n, (i) => i)..sort((a, b) => nonZero[a].abs().compareTo(nonZero[b].abs()));
    final ranks = List<double>.filled(n, 0);
    var tieCorrection = 0.0;
    var i = 0;
    while (i < n) {
      var j = i;
      while (j + 1 < n && nonZero[order[j + 1]].abs() == nonZero[order[i]].abs()) {
        j++;
      }
      final avg = (i + j) / 2 + 1;
      for (var t = i; t <= j; t++) {
        ranks[order[t]] = avg;
      }
      final tie = j - i + 1;
      tieCorrection += (tie * tie * tie - tie) / 48;
      i = j + 1;
    }
    var wPlus = 0.0;
    var wMinus = 0.0;
    for (var t = 0; t < n; t++) {
      if (nonZero[t] > 0) {
        wPlus += ranks[t];
      } else {
        wMinus += ranks[t];
      }
    }
    if (n < 10) return WilcoxonResult(n, wPlus, wMinus, null, null);
    final mean = n * (n + 1) / 4;
    final variance = n * (n + 1) * (2 * n + 1) / 24 - tieCorrection;
    if (variance <= 0) return WilcoxonResult(n, wPlus, wMinus, null, null);
    final w = min(wPlus, wMinus);
    final z = (w - mean + 0.5) / sqrt(variance);
    final p = (2 * _normalCdf(-z.abs())).clamp(0.0, 1.0);
    return WilcoxonResult(n, wPlus, wMinus, z, p.toDouble());
  }

  static double _normalCdf(double x) => 0.5 * (1 + _erf(x / sqrt2));

  // Abramowitz & Stegun 7.1.26 (|error| < 1.5e-7).
  static double _erf(double x) {
    final sign = x < 0 ? -1 : 1;
    x = x.abs();
    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741, a4 = -1.453152027, a5 = 1.061405429, p = 0.3275911;
    final t = 1 / (1 + p * x);
    final y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * exp(-x * x);
    return sign * y;
  }
}

/// Percentile bootstrap 95% CI of the mean of [values]. Seeded, so the same
/// data always gives the same interval. Null with fewer than 2 values.
class BootstrapCi {
  final double mean;
  final double lower;
  final double upper;
  final int resamples;

  const BootstrapCi(this.mean, this.lower, this.upper, this.resamples);

  static BootstrapCi? of(List<double> values, {int resamples = 2000, int seed = 42}) {
    if (values.length < 2) return null;
    final rng = Random(seed);
    final means = <double>[];
    for (var r = 0; r < resamples; r++) {
      var sum = 0.0;
      for (var i = 0; i < values.length; i++) {
        sum += values[rng.nextInt(values.length)];
      }
      means.add(sum / values.length);
    }
    means.sort();
    final mean = values.reduce((a, b) => a + b) / values.length;
    return BootstrapCi(mean, Summary.percentile(means, 2.5), Summary.percentile(means, 97.5), resamples);
  }
}
