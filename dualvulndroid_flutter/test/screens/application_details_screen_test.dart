import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/models/application_summary.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/screens/application_details_screen.dart';
import 'package:dualvulndroid_flutter/services/apps_api_service.dart';

import '../helpers/fake_http.dart';

Widget _wrap(Widget child, AppsRepository repo) {
  return MultiProvider(
    providers: [Provider<AppsRepository>.value(value: repo)],
    child: MaterialApp(home: child),
  );
}

Map<String, dynamic> _assessedResponse({
  required int id,
  Map<String, dynamic>? recommendation,
  List<Map<String, dynamic>>? vulnerabilities,
}) {
  return {
    'assessed': true,
    'application': {'id': id, 'name': 'VulnApp', 'packageName': 'com.example.vuln'},
    'version': {'versionName': '1.0', 'versionCode': 1, 'features': [], 'abis': []},
    'assessment': {'riskLevel': 'HIGH', 'recommendation': 'AVOID_INSTALLING', 'confidence': 90, 'securityScore': 15},
    'vulnerabilities': vulnerabilities ?? const [],
    if (recommendation != null) 'recommendation': recommendation,
    'securityMetadata': {'debuggable': null, 'allowBackup': null},
    'compatibility': {'status': 'NOT_AVAILABLE', 'checks': {}, 'reasons': []},
  };
}

void main() {
  group('ApplicationDetailsScreen', () {
    // 7. Unassessed application
    testWidgets('shows the honest "not assessed" message, never a fake risk level', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'GET', pathPrefix: '/apps/1/security', body: {
          'assessed': false,
          'message': 'This application has not been assessed yet.',
        }),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 1, appName: 'UnassessedApp', packageName: 'com.example.unassessed')),
        repo,
      ));
      await tester.pumpAndSettle();

      expect(find.text('This application has not been assessed yet.'), findsOneWidget);
      expect(find.textContaining('HIGH'), findsNothing);
      expect(find.textContaining('LOW'), findsNothing);
    });

    // 9. Vulnerability display
    testWidgets('shows real vulnerability findings with CWE and severity', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'GET',
          pathPrefix: '/apps/2/security',
          body: _assessedResponse(id: 2, vulnerabilities: [
            {'cwe': 'CWE-89', 'type': 'SQL Injection', 'severity': 'HIGH', 'confidence': 91, 'description': 'Unsanitized query concatenation.'},
          ]),
        ),
        FakeRoute(method: 'GET', pathPrefix: '/apps/2/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 2, appName: 'VulnApp', packageName: 'com.example.vuln')),
        repo,
      ));
      await tester.pumpAndSettle();

      expect(find.text('SQL Injection'), findsOneWidget);
      expect(find.textContaining('CWE-89'), findsOneWidget);
      expect(find.text('HIGH'), findsWidgets);
    });

    // 7 (Phase 10A). Reason displayed
    testWidgets('shows the real stored recommendation reason verbatim', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'GET',
          pathPrefix: '/apps/3/security',
          body: _assessedResponse(
            id: 3,
            recommendation: {
              'decision': 'AVOID_INSTALLING',
              'reason': 'The application contains a certificate validation issue detected by the security analysis.',
              'evidence': [],
            },
          ),
        ),
        FakeRoute(method: 'GET', pathPrefix: '/apps/3/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 3, appName: 'CertApp', packageName: 'com.example.cert')),
        repo,
      ));
      await tester.pumpAndSettle();

      expect(find.text('WHY THIS DECISION?'), findsOneWidget);
      expect(find.text('The application contains a certificate validation issue detected by the security analysis.'), findsOneWidget);
    });

    // 8. Missing reason handled
    testWidgets('shows an honest placeholder when no reason was stored, never invented text', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'GET',
          pathPrefix: '/apps/4/security',
          body: _assessedResponse(id: 4, recommendation: {'decision': 'AVOID_INSTALLING', 'reason': null, 'evidence': []}),
        ),
        FakeRoute(method: 'GET', pathPrefix: '/apps/4/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 4, appName: 'NoReasonApp', packageName: 'com.example.noreason')),
        repo,
      ));
      await tester.pumpAndSettle();

      expect(find.text('No explanation was recorded for this assessment.'), findsOneWidget);
    });

    // 9 (Phase 10A). Evidence displayed
    testWidgets('shows evidence entries with CWE, severity and confidence', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'GET',
          pathPrefix: '/apps/5/security',
          body: _assessedResponse(
            id: 5,
            vulnerabilities: [
              {'cwe': 'CWE-295', 'type': 'Certificate Validation', 'severity': 'HIGH', 'confidence': 88, 'source': 'HostnameVerifier.verify', 'sink': 'checkServerTrusted'},
            ],
            recommendation: {
              'decision': 'AVOID_INSTALLING',
              'reason': 'Certificate validation issue detected.',
              'evidence': [
                {'cwe': 'CWE-295', 'type': 'Certificate Validation', 'severity': 'HIGH', 'confidence': 88, 'source': 'HostnameVerifier.verify', 'sink': 'checkServerTrusted'},
              ],
            },
          ),
        ),
        FakeRoute(method: 'GET', pathPrefix: '/apps/5/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 5, appName: 'CertApp2', packageName: 'com.example.cert2')),
        repo,
      ));
      await tester.pumpAndSettle();

      expect(find.text('EVIDENCE'), findsOneWidget);
      expect(find.textContaining('CWE-295'), findsWidgets);
      expect(find.textContaining('88% confidence'), findsOneWidget);
    });

    // 10. Technical details expandable, collapsed by default
    testWidgets('technical details (source/sink) stay hidden until expanded', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'GET',
          pathPrefix: '/apps/6/security',
          body: _assessedResponse(
            id: 6,
            vulnerabilities: [
              {'cwe': 'CWE-295', 'type': 'Certificate Validation', 'severity': 'HIGH', 'confidence': 88, 'source': 'HostnameVerifier.verify', 'sink': 'checkServerTrusted'},
            ],
            recommendation: {
              'decision': 'AVOID_INSTALLING',
              'reason': 'Certificate validation issue detected.',
              'evidence': [
                {'cwe': 'CWE-295', 'type': 'Certificate Validation', 'severity': 'HIGH', 'confidence': 88, 'source': 'HostnameVerifier.verify', 'sink': 'checkServerTrusted'},
              ],
            },
          ),
        ),
        FakeRoute(method: 'GET', pathPrefix: '/apps/6/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 6, appName: 'CertApp3', packageName: 'com.example.cert3')),
        repo,
      ));
      await tester.pumpAndSettle();

      // Collapsed by default - the source -> sink line is not yet visible.
      expect(find.text('Technical details'), findsOneWidget);
      expect(find.textContaining('HostnameVerifier.verify'), findsNothing);

      await tester.ensureVisible(find.text('Technical details'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Technical details'));
      await tester.pumpAndSettle();

      expect(find.textContaining('HostnameVerifier.verify'), findsOneWidget);
      expect(find.textContaining('checkServerTrusted'), findsOneWidget);
    });

    // New: "View details" navigates to the real VulnerabilityDetailScreen
    // for the same real finding (matches the design's dedicated CWE-89/
    // CWE-295 detail screens, without duplicating the finding's own title
    // text so the earlier "SQL Injection" assertion above keeps passing).
    testWidgets('"View details" opens VulnerabilityDetailScreen with the same real finding', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'GET',
          pathPrefix: '/apps/8/security',
          body: _assessedResponse(id: 8, vulnerabilities: [
            {'cwe': 'CWE-89', 'type': 'SQL Injection', 'severity': 'HIGH', 'confidence': 91, 'description': 'Unsanitized query concatenation.'},
          ]),
        ),
        FakeRoute(method: 'GET', pathPrefix: '/apps/8/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 8, appName: 'VulnApp2', packageName: 'com.example.vuln2')),
        repo,
      ));
      await tester.pumpAndSettle();

      // The finding tile is collapsed by default - expand it first so its
      // "View details" action is actually in the tree (same pattern as
      // the "technical details" test above).
      await tester.ensureVisible(find.text('SQL Injection'));
      await tester.tap(find.text('SQL Injection'));
      await tester.pumpAndSettle();

      await tester.ensureVisible(find.text('View details'));
      await tester.tap(find.text('View details'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('SQL Injection — CWE-89'), findsOneWidget);
      expect(find.text('Unsanitized query concatenation.'), findsOneWidget);
    });

    // 11. Backward-compatible response (no "recommendation" field at all,
    // matching a pre-Phase-10A backend) - must not crash, must show the
    // honest no-reason placeholder rather than choking on a missing key.
    testWidgets('renders correctly against a response with no "recommendation" field', (tester) async {
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'GET', pathPrefix: '/apps/7/security', body: _assessedResponse(id: 7)),
        FakeRoute(method: 'GET', pathPrefix: '/apps/7/alternatives', body: {'available': false, 'alternatives': []}),
      ]))));

      await tester.pumpWidget(_wrap(
        const ApplicationDetailsScreen(application: ApplicationSummary(id: 7, appName: 'OldBackendApp', packageName: 'com.example.old')),
        repo,
      ));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No explanation was recorded for this assessment.'), findsOneWidget);
    });
  });
}
