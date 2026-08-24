import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/repositories/history_repository.dart';
import 'package:dualvulndroid_flutter/services/history_api_service.dart';

import '../helpers/fake_http.dart';

void main() {
  group('HistoryRepository', () {
    // 15. History
    test('getHistory returns the real, only-this-user history list', () async {
      final client = buildFakeClient([
        FakeRoute(method: 'GET', pathPrefix: '/user/history', body: {
          'history': [
            {
              'scan_id': 5,
              'application_id': 3,
              'app_name': 'RealBank',
              'package_name': 'com.realbank.app',
              'security_score': 40,
              'risk_level': 'HIGH',
              'recommendation': 'AVOID_INSTALLING',
              'timestamp': '2026-08-17T12:00:00',
            },
          ],
        }),
      ]);
      final repo = HistoryRepository(HistoryApiService(ApiClient(client: client)));

      final history = await repo.getHistory();

      expect(history, hasLength(1));
      expect(history.first.scanId, 5);
      expect(history.first.applicationId, 3);
      expect(history.first.appName, 'RealBank');
      expect(history.first.riskLevel, 'HIGH');
    });

    test('getHistory returns an empty list honestly when the user has none', () async {
      final client = buildFakeClient([
        FakeRoute(method: 'GET', pathPrefix: '/user/history', body: {'history': []}),
      ]);
      final repo = HistoryRepository(HistoryApiService(ApiClient(client: client)));

      final history = await repo.getHistory();

      expect(history, isEmpty);
    });
  });
}
