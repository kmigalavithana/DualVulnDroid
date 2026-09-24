import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/models/history_entry_model.dart';
import 'package:dualvulndroid_flutter/models/user_preferences_model.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/services/history_storage_service.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  Future<void> flushAsync() => Future<void>.delayed(Duration.zero);

  test('recordDiscovery persists the real recommended apps (name + score) and device context, surviving a reload', () async {
    final repo = HistoryRepository(storage: HistoryStorageService());
    await flushAsync();

    await repo.recordDiscovery(
      category: AppCategory.notes,
      preferences: {AppPreference.lightweight},
      resultCount: 3,
      recommendedApps: const [
        RecommendedAppEntry(packageName: 'com.smartapp.demo.noteflow', name: 'NoteFlow', score: 91, dataSource: 'google_play'),
        RecommendedAppEntry(packageName: 'com.smartapp.demo.taskflow', name: 'TaskFlow', score: 84),
      ],
      deviceContext: const DeviceContextSummary(ramTotalMb: 4096, androidRelease: '14', connectivityStatus: ConnectivityStatus.wifi, batteryLevel: 80),
    );

    final reloaded = HistoryRepository(storage: HistoryStorageService());
    await flushAsync();

    expect(reloaded.entries, hasLength(1));
    final entry = reloaded.entries.first;
    expect(entry.recommendedAppIds, ['com.smartapp.demo.noteflow', 'com.smartapp.demo.taskflow']);
    expect(entry.recommendedApps.first.name, 'NoteFlow');
    expect(entry.recommendedApps.first.score, 91);
    expect(entry.recommendedApps.first.dataSource, 'google_play');
    expect(entry.deviceContext.ramTotalMb, 4096);
    expect(entry.deviceContext.androidRelease, '14');
    expect(entry.deviceContext.connectivityStatus, ConnectivityStatus.wifi);
    expect(entry.deviceContext.batteryLevel, 80);
  });

  test('an entry with no device context round-trips as an empty (not fabricated) summary', () async {
    final repo = HistoryRepository(storage: HistoryStorageService());
    await flushAsync();
    await repo.recordDiscovery(category: null, preferences: const {}, resultCount: 0);

    final reloaded = HistoryRepository(storage: HistoryStorageService());
    await flushAsync();
    expect(reloaded.entries.single.deviceContext.isEmpty, isTrue);
    expect(reloaded.entries.single.recommendedAppIds, isEmpty);
  });

  test('clearing history removes every entry, including after a reload', () async {
    final repo = HistoryRepository(storage: HistoryStorageService());
    await flushAsync();
    await repo.recordDiscovery(category: AppCategory.notes, preferences: const {}, resultCount: 1);
    await repo.clear();

    final reloaded = HistoryRepository(storage: HistoryStorageService());
    await flushAsync();
    expect(reloaded.entries, isEmpty);
  });
}
