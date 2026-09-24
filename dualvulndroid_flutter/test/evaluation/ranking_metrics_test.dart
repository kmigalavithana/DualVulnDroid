import 'dart:math';

import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/evaluation/ranking_metrics.dart';

/// Metric formulas checked against hand-computed values.
///
/// Ranking: a b c d e f; human grades: a=3 b=0 c=2 d=1 e=0 f=2
/// Relevant (grade >= 2): a, c, f (3 total).
void main() {
  const ranking = ['a', 'b', 'c', 'd', 'e', 'f'];
  const labels = {'a': 3, 'b': 0, 'c': 2, 'd': 1, 'e': 0, 'f': 2};
  double lg(int i) => log(i + 1) / ln2; // log2(i + 1), i 1-based

  test('1. Precision@3 = relevant in top 3 / 3', () {
    expect(RankingMetrics.precisionAtK(ranking, labels, 3), closeTo(2 / 3, 1e-12)); // a, c
  });

  test('2. Recall@3 = relevant in top 3 / all relevant', () {
    expect(RankingMetrics.recallAtK(ranking, labels, 3), closeTo(2 / 3, 1e-12));
  });

  test('3. NDCG@3 with graded gains 2^rel - 1', () {
    final dcg = (pow(2, 3) - 1) / lg(1) + 0 / lg(2) + (pow(2, 2) - 1) / lg(3); // 7 + 0 + 3/2
    final idcg = 7 / lg(1) + 3 / lg(2) + 3 / lg(3); // ideal grades 3,2,2
    expect(RankingMetrics.ndcgAtK(ranking, labels, 3), closeTo(dcg / idcg, 1e-12));
  });

  test('4. Precision@5', () {
    expect(RankingMetrics.precisionAtK(ranking, labels, 5), closeTo(2 / 5, 1e-12)); // a, c in top 5
  });

  test('5. Recall@5', () {
    expect(RankingMetrics.recallAtK(ranking, labels, 5), closeTo(2 / 3, 1e-12));
  });

  test('6. NDCG@5', () {
    final dcg = 7 / lg(1) + 0 + 3 / lg(3) + 1 / lg(4) + 0;
    final idcg = 7 / lg(1) + 3 / lg(2) + 3 / lg(3) + 1 / lg(4) + 0;
    expect(RankingMetrics.ndcgAtK(ranking, labels, 5), closeTo(dcg / idcg, 1e-12));
  });

  test('7. graded relevance: a 3 above a 2 scores higher than the reverse; perfect order = 1', () {
    const graded = {'x': 3, 'y': 2};
    expect(RankingMetrics.ndcgAtK(['x', 'y'], graded, 2), closeTo(1, 1e-12));
    expect(RankingMetrics.ndcgAtK(['y', 'x'], graded, 2)!, lessThan(1));
    // Binary precision can't tell them apart - NDCG can.
    expect(RankingMetrics.precisionAtK(['x', 'y'], graded, 2), RankingMetrics.precisionAtK(['y', 'x'], graded, 2));
  });

  test('8. empty / all-irrelevant relevance sets give undefined (null), never 0 or a guess', () {
    expect(RankingMetrics.precisionAtK(const [], const {}, 3), isNull);
    const noneRelevant = {'a': 0, 'b': 1};
    expect(RankingMetrics.recallAtK(['a', 'b'], noneRelevant, 3), isNull);
    const allZero = {'a': 0, 'b': 0};
    expect(RankingMetrics.ndcgAtK(['a', 'b'], allZero, 3), isNull);
    expect(RankingMetrics.precisionAtK(['a', 'b'], allZero, 3), 0, reason: 'precision IS defined: 0 relevant of K');
  });

  test('an unlabeled app in a ranking is rejected, never guessed', () {
    expect(() => RankingMetrics.precisionAtK(['a', 'zzz'], const {'a': 3}, 3), throwsArgumentError);
  });

  test('17. latency aggregation: mean, median and P95 (linear interpolation)', () {
    final s = Summary.of([100, 200, 300, 400, 1000])!;
    expect(s.n, 5);
    expect(s.mean, 400);
    expect(s.median, 300);
    expect(s.p95, closeTo(400 + (1000 - 400) * 0.8, 1e-9)); // rank 3.8
    expect(Summary.of(const <int>[]), isNull);
  });

  test('Wilcoxon: ranks, ties and the n < 10 rule', () {
    final w = WilcoxonResult.compute([0.1, -0.2, 0.3, 0, 0.3])!;
    expect(w.n, 4, reason: 'zero differences are dropped');
    // |d|: .1(r1) .2(r2) .3,.3 (tied ranks 3.5 each)
    expect(w.wPlus, 1 + 3.5 + 3.5);
    expect(w.wMinus, 2);
    expect(w.pTwoSided, isNull, reason: 'no normal-approximation p-value below 10 pairs');
    expect(WilcoxonResult.compute([0, 0]), isNull);

    final big = WilcoxonResult.compute(List.generate(12, (i) => (i + 1) / 10))!;
    expect(big.wMinus, 0);
    expect(big.pTwoSided, lessThan(0.01));
  });

  test('bootstrap CI is reproducible and brackets the mean; needs >= 2 values', () {
    final values = [0.1, 0.2, 0.15, 0.3, 0.05];
    final a = BootstrapCi.of(values)!;
    final b = BootstrapCi.of(values)!;
    expect(a.lower, b.lower);
    expect(a.upper, b.upper);
    expect(a.lower, lessThanOrEqualTo(a.mean));
    expect(a.upper, greaterThanOrEqualTo(a.mean));
    expect(BootstrapCi.of([0.1]), isNull);
  });
}
