import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/models/compatibility_model.dart';
import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/services/apps_api_service.dart';

import '../helpers/fake_http.dart';

AppsRepository _repoWith(List<FakeRoute> routes) {
  return AppsRepository(AppsApiService(ApiClient(client: buildFakeClient(routes))));
}

void main() {
  group('AppsRepository', () {
    // 5. Search success
    test('search returns real parsed results', () async {
      final repo = _repoWith([
        FakeRoute(method: 'GET', pathPrefix: '/apps/search', body: {
          'results': [
            {'id': 1, 'app_name': 'RealBank', 'package_name': 'com.realbank.app', 'category': 'Finance'},
          ],
        }),
      ]);
      final results = await repo.search('realbank');
      expect(results, hasLength(1));
      expect(results.first.appName, 'RealBank');
      expect(results.first.packageName, 'com.realbank.app');
    });

    // 6. Search empty
    test('search with no matches returns an empty list, not an error', () async {
      final repo = _repoWith([
        FakeRoute(method: 'GET', pathPrefix: '/apps/search', body: {'results': []}),
      ]);
      final results = await repo.search('nonexistent-app-xyz');
      expect(results, isEmpty);
    });

    // 8. Security assessment (real, assessed)
    test('getSecurity returns a fully parsed real assessment', () async {
      final repo = _repoWith([
        FakeRoute(method: 'GET', pathPrefix: '/apps/1/security', body: {
          'assessed': true,
          'application': {'id': 1, 'name': 'RealBank', 'packageName': 'com.realbank.app'},
          'version': {'versionName': '1.0', 'versionCode': 1, 'minSdkVersion': 21, 'targetSdkVersion': 34, 'features': [], 'abis': []},
          'assessment': {'riskLevel': 'HIGH', 'recommendation': 'AVOID_INSTALLING', 'confidence': 87, 'securityScore': 20, 'assessedAt': null},
          'vulnerabilities': [
            {'cwe': 'CWE-89', 'type': 'SQL Injection', 'severity': 'HIGH', 'confidence': 91, 'description': 'Unsafe query.'},
          ],
          'securityMetadata': {'debuggable': false, 'allowBackup': true},
          'compatibility': {'status': 'NOT_AVAILABLE', 'checks': {}, 'reasons': []},
        }),
      ]);
      final assessment = await repo.getSecurity(1);
      expect(assessment.assessed, isTrue);
      expect(assessment.assessment.riskLevel, 'HIGH');
      expect(assessment.vulnerabilities, hasLength(1));
      expect(assessment.vulnerabilities.first.cwe, 'CWE-89');
    });

    // Unassessed application - the honest "not assessed" shape.
    test('getSecurity returns assessed=false honestly, never a fake risk level', () async {
      final repo = _repoWith([
        FakeRoute(method: 'GET', pathPrefix: '/apps/2/security', body: {
          'assessed': false,
          'message': 'This application has not been assessed yet.',
        }),
      ]);
      final assessment = await repo.getSecurity(2);
      expect(assessment.assessed, isFalse);
      expect(assessment.assessment.riskLevel, isNull);
      expect(assessment.message, 'This application has not been assessed yet.');
    });

    // 10. Compatibility: COMPATIBLE
    test('checkCompatibility returns COMPATIBLE when the backend says so', () async {
      final repo = _repoWith([
        FakeRoute(method: 'POST', pathPrefix: '/apps/1/compatibility', body: {
          'application': {'id': 1, 'name': 'RealBank'},
          'compatibility': {
            'status': 'COMPATIBLE',
            'checks': {
              'androidVersion': {'status': 'COMPATIBLE'},
              'requiredFeatures': {'status': 'COMPATIBLE', 'missing': []},
              'abi': {'status': 'COMPATIBLE'},
            },
            'reasons': [],
          },
          'hardwareCompatibility': {'status': 'NOT_AVAILABLE', 'reason': 'Verified hardware requirements are not available.'},
          'finalRecommendation': {'recommendation': 'SAFE_TO_INSTALL', 'reason': 'Based on the existing security assessment.'},
        }),
      ]);
      final result = await repo.checkCompatibility(1, const DeviceProfileModel(androidVersion: 30));
      expect(result.compatibility.status, CompatibilityStatus.compatible);
      expect(result.finalRecommendation.recommendation, 'SAFE_TO_INSTALL');
    });

    // 11. Compatibility: INCOMPATIBLE
    test('checkCompatibility returns INCOMPATIBLE with real reasons', () async {
      final repo = _repoWith([
        FakeRoute(method: 'POST', pathPrefix: '/apps/1/compatibility', body: {
          'application': {'id': 1, 'name': 'RealBank'},
          'compatibility': {
            'status': 'INCOMPATIBLE',
            'checks': {
              'androidVersion': {'status': 'INCOMPATIBLE'},
              'requiredFeatures': {'status': 'COMPATIBLE', 'missing': []},
              'abi': {'status': 'COMPATIBLE'},
            },
            'reasons': ['Device Android version (15) is lower than the application\'s minimum required Android version (21).'],
          },
          'hardwareCompatibility': {'status': 'NOT_AVAILABLE', 'reason': 'Verified hardware requirements are not available.'},
          'finalRecommendation': {'recommendation': 'DO_NOT_INSTALL_ON_THIS_DEVICE', 'reason': 'Not compatible with this device.'},
        }),
      ]);
      final result = await repo.checkCompatibility(1, const DeviceProfileModel(androidVersion: 15));
      expect(result.compatibility.status, CompatibilityStatus.incompatible);
      expect(result.compatibility.androidVersion.status, CompatibilityStatus.incompatible);
      expect(result.compatibility.reasons, isNotEmpty);
    });

    // 12. Compatibility: NOT_AVAILABLE
    test('checkCompatibility returns NOT_AVAILABLE when device data is missing, never a fabricated verdict', () async {
      final repo = _repoWith([
        FakeRoute(method: 'POST', pathPrefix: '/apps/1/compatibility', body: {
          'application': {'id': 1, 'name': 'RealBank'},
          'compatibility': {
            'status': 'NOT_AVAILABLE',
            'checks': {
              'androidVersion': {'status': 'NOT_AVAILABLE'},
              'requiredFeatures': {'status': 'NOT_AVAILABLE', 'missing': []},
              'abi': {'status': 'NOT_AVAILABLE'},
            },
            'reasons': [],
          },
          'hardwareCompatibility': {'status': 'NOT_AVAILABLE', 'reason': 'Verified hardware requirements are not available.'},
          'finalRecommendation': {'recommendation': 'SECURITY_ASSESSMENT_UNAVAILABLE', 'reason': 'Not assessed yet.'},
        }),
      ]);
      final result = await repo.checkCompatibility(1, const DeviceProfileModel());
      expect(result.compatibility.status, CompatibilityStatus.notAvailable);
    });

    // 13. Alternative apps
    test('getAlternatives returns real ranked candidates', () async {
      final repo = _repoWith([
        FakeRoute(method: 'GET', pathPrefix: '/apps/1/alternatives', body: {
          'available': true,
          'alternatives': [
            {'applicationId': 2, 'name': 'SaferBank', 'packageName': 'com.saferbank.app', 'riskLevel': 'LOW', 'securityScore': 92, 'reasons': ['Lower assessed security risk (LOW) than the selected application (HIGH).']},
          ],
        }),
      ]);
      final (available, alternatives) = await repo.getAlternatives(1);
      expect(available, isTrue);
      expect(alternatives, hasLength(1));
      expect(alternatives.first.name, 'SaferBank');
      expect(alternatives.first.reasons, isNotEmpty);
    });

    // 14. No alternatives
    test('getAlternatives honestly reports none available', () async {
      final repo = _repoWith([
        FakeRoute(method: 'GET', pathPrefix: '/apps/1/alternatives', body: {'available': false, 'alternatives': []}),
      ]);
      final (available, alternatives) = await repo.getAlternatives(1);
      expect(available, isFalse);
      expect(alternatives, isEmpty);
    });
  });
}
