import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';

void main() {
  final repo = AppsRepository();

  test('the curated catalog is non-empty and every entry is marked as a curated sample', () {
    expect(repo.all, isNotEmpty);
    expect(repo.all.every((a) => a.isCuratedSample), isTrue);
  });

  test('byCategory only returns apps in that category', () {
    final notesApps = repo.byCategory(AppCategory.notes);
    expect(notesApps, isNotEmpty);
    expect(notesApps.every((a) => a.category == AppCategory.notes), isTrue);
  });

  test('a category absent from the demo dataset returns an empty (not fabricated) list', () {
    expect(repo.byCategory(AppCategory.other), isEmpty);
  });

  test('search matches by name, description, or category label, and an empty query matches nothing', () {
    expect(repo.search('pdf'), isNotEmpty);
    expect(repo.search('').isEmpty, isTrue);
    expect(repo.search('zzz_not_a_real_query_zzz'), isEmpty);
  });

  test('alternativesTo never includes the app itself and stays within the same category', () {
    final app = repo.all.first;
    final alternatives = repo.alternativesTo(app);
    expect(alternatives.any((a) => a.id == app.id), isFalse);
    expect(alternatives.every((a) => a.category == app.category), isTrue);
  });

  test('every declared preference-filter helper only returns apps that actually satisfy it', () {
    expect(repo.lightweight().every((a) => a.satisfies(AppPreference.lightweight)), isTrue);
    expect(repo.privacyFriendly().every((a) => a.satisfies(AppPreference.privacyFriendly)), isTrue);
    expect(repo.offlineCapable().every((a) => a.satisfies(AppPreference.offlineSupport)), isTrue);
    expect(repo.openSource().every((a) => a.satisfies(AppPreference.openSource)), isTrue);
    expect(repo.lowStorage().every((a) => a.satisfies(AppPreference.lowStorageUsage)), isTrue);
  });

  test('findByName resolves an exact (case-insensitive) match and returns null for nothing close', () {
    final app = repo.all.first;
    expect(repo.findByName(app.name.toUpperCase())?.id, app.id);
    expect(repo.findByName('definitely-not-a-real-app-xyz'), isNull);
  });
}
