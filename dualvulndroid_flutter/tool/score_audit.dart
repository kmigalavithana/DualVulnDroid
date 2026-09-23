// Score-distribution audit for live Google Play apps.
//
// Fetches REAL search results from SmartApp's backend (never SerpApi
// directly, never demo data), scores them with the app's own
// RecommendationEngine, and prints the distribution plus metadata
// coverage - used to compare scoring BEFORE vs AFTER metadata enrichment.
//
//   dart run tool/score_audit.dart [backendBaseUrl] [query1,query2,...]
//
// The device profile below mirrors the test emulator's real reported
// values (1.9 GB RAM, Android 16) so the audit reflects the same context
// the app itself scores against.
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:http/http.dart' as http;

import 'package:dualvulndroid_flutter/engines/recommendation_engine.dart';
import 'package:dualvulndroid_flutter/models/app_info_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';

const _device = DeviceProfileModel(
  androidSdkInt: 36,
  androidRelease: '16',
  ramTotalMb: 1946,
  isLowRamDevice: false,
  storageFreeBytes: 14500000000,
);

/// The 7 recommendation attributes coverage is measured over (same list as
/// AppInfo.metadataCoverage / backend metadata_coverage()).
double coverageOf(AppInfo a) {
  final known = [
    a.rating != null,
    a.trackerCount != null,
    a.sizeMb != null || a.resourceLevel != null,
    a.isFree != null,
    a.hasAds != null,
    a.isOpenSource != null,
    a.supportsOffline != null,
  ];
  return known.where((k) => k).length / known.length;
}

String stats(List<num> values) {
  if (values.isEmpty) return 'n=0';
  final sorted = [...values]..sort();
  final n = sorted.length;
  final mean = sorted.fold<double>(0, (a, b) => a + b) / n;
  final median = n.isOdd ? sorted[n ~/ 2].toDouble() : (sorted[n ~/ 2 - 1] + sorted[n ~/ 2]) / 2;
  final sd = sqrt(sorted.fold<double>(0, (a, b) => a + (b - mean) * (b - mean)) / n);
  return 'n=$n min=${sorted.first} max=${sorted.last} mean=${mean.toStringAsFixed(1)} '
      'median=${median.toStringAsFixed(1)} sd=${sd.toStringAsFixed(2)} unique=${sorted.toSet().length}';
}

Future<void> main(List<String> args) async {
  final base = args.isNotEmpty ? args[0] : 'http://127.0.0.1:8000';
  final queries = args.length > 1 ? args[1].split(',') : ['notes', 'pdf reader', 'music player'];

  final apps = <String, AppInfo>{};
  for (final q in queries) {
    final uri = Uri.parse('$base/smartapp/apps/search').replace(queryParameters: {'q': q, 'limit': '20'});
    final response = await http.get(uri);
    if (response.statusCode != 200) {
      stderr.writeln('search "$q" failed: HTTP ${response.statusCode}');
      exit(1);
    }
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    for (final raw in (body['apps'] as List).cast<Map<String, dynamic>>()) {
      final app = AppInfo.fromSmartAppJson(raw);
      apps[app.packageName ?? app.id] = app;
    }
  }
  final list = apps.values.toList();
  stdout.writeln('backend=$base queries=$queries unique live apps=${list.length}');

  const engine = RecommendationEngine();
  for (final scenario in {
    'all 7 preferences': AppPreference.values.toSet(),
    'no preferences': <AppPreference>{},
    'lightweight + privacy': {AppPreference.lightweight, AppPreference.privacyFriendly},
  }.entries) {
    final prefs = UserPreferencesModel(selectedPreferences: scenario.value);
    final scores = list.map((a) => engine.score(app: a, preferences: prefs, device: _device).matchPercent).toList();
    stdout.writeln('  [${scenario.key}] match%: ${stats(scores)}');
  }

  final coverage = list.map((a) => (coverageOf(a) * 100).round()).toList();
  stdout.writeln('  metadata coverage %: ${stats(coverage)}');
  String pct(bool Function(AppInfo) f) => '${(list.where(f).length / list.length * 100).round()}%';
  stdout.writeln('  google play (rating)   ${pct((a) => a.rating != null)}');
  stdout.writeln('  privacy (trackers)     ${pct((a) => a.trackerCount != null)}');
  stdout.writeln('  resource (size/level)  ${pct((a) => a.sizeMb != null || a.resourceLevel != null)}');
  stdout.writeln('  price (isFree)         ${pct((a) => a.isFree != null)}');
  stdout.writeln('  ads (hasAds)           ${pct((a) => a.hasAds != null)}');
  stdout.writeln('  open source            ${pct((a) => a.isOpenSource != null)}');
  stdout.writeln('  offline                ${pct((a) => a.supportsOffline != null)}');
}
