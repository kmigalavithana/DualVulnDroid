import 'dart:io';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/repositories/apps_repository.dart';
import 'package:dualvulndroid_flutter/screens/apk_scan_screen.dart';
import 'package:dualvulndroid_flutter/services/apps_api_service.dart';

import '../helpers/fake_http.dart';

/// A settable fake for FilePicker.platform (a public static field the
/// package itself provides for exactly this purpose - see
/// file_picker's FilePicker.platform setter). Each test supplies what
/// picking a file "returns", so no real OS file-picker dialog or
/// platform channel is ever involved.
class _FakeFilePicker extends FilePicker {
  final FilePickerResult? Function() onPick;
  _FakeFilePicker(this.onPick);

  @override
  Future<FilePickerResult?> pickFiles({
    String? dialogTitle,
    String? initialDirectory,
    FileType type = FileType.any,
    List<String>? allowedExtensions,
    Function(FilePickerStatus)? onFileLoading,
    @Deprecated('unused') bool allowCompression = false,
    int compressionQuality = 0,
    bool allowMultiple = false,
    bool withData = false,
    bool withReadStream = false,
    bool lockParentWindow = false,
    bool readSequential = false,
  }) async {
    return onPick();
  }
}

/// ApkScanScreen now reads the picked file's bytes from disk via
/// `file.path` (never via file_picker's `withData`/platform-channel
/// transfer - see apk_scan_screen.dart's own comment on why: it crashes
/// the whole process with a native OutOfMemoryError for a real-sized
/// APK). So the fake picker result needs a REAL file on disk, not just
/// an in-memory `bytes` field, to match what a real pick actually
/// returns and exercise the real read path.
PlatformFile _fakeApkFile({String name = 'MyApp.apk'}) {
  final bytes = Uint8List.fromList([1, 2, 3, 4]);
  final dir = Directory.systemTemp.createTempSync('apk_scan_test_');
  final file = File('${dir.path}/$name')..writeAsBytesSync(bytes);
  return PlatformFile(name: name, size: bytes.length, path: file.path);
}

Widget _wrap(Widget child, AppsRepository repo) {
  return MultiProvider(
    providers: [Provider<AppsRepository>.value(value: repo)],
    child: MaterialApp(home: child),
  );
}

Map<String, dynamic> _uploadResponse({
  String appName = 'MyApp.apk',
  int applicationId = 1,
  String riskLevel = 'high',
  List<Map<String, dynamic>> findings = const [],
}) {
  final cwe89 = findings.where((f) => f['cwe'] == 'CWE-89').length;
  final cwe295 = findings.where((f) => f['cwe'] == 'CWE-295').length;
  return {
    'risk_level': riskLevel,
    'vulnerable': findings.isNotEmpty,
    'app_name': appName,
    'package_name': 'com.example.app',
    'security_score': 50,
    'explanation': 'test',
    'dangerous_permissions': [],
    'malicious_urls': [],
    'scan_id': 42,
    'application': {'id': applicationId, 'packageName': 'com.example.app', 'name': appName},
    'codeAnalysis': {
      'filesScanned': 3,
      'classesTotal': 3,
      'filesSkippedThirdParty': 0,
      'truncated': false,
      'truncationReason': null,
      'totalFindings': findings.length,
      'cwe89Count': cwe89,
      'cwe295Count': cwe295,
      'findings': findings,
      'note': 'decompiled code note',
    },
  };
}

void main() {
  group('ApkScanScreen', () {
    testWidgets('cancelling the file picker leaves the pick state untouched', (tester) async {
      FilePicker.platform = _FakeFilePicker(() => null);
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Choose APK'), findsOneWidget);
      expect(find.text('Scan this APK'), findsNothing);
    });

    testWidgets('picking a non-APK file shows an honest invalid-file error', (tester) async {
      FilePicker.platform = _FakeFilePicker(
        () => FilePickerResult([PlatformFile(name: 'not_an_apk.txt', size: 10, bytes: Uint8List.fromList([1]))]),
      );
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.textContaining('not an APK'), findsOneWidget);
    });

    testWidgets('picking a real APK shows its filename and a scan button', (tester) async {
      FilePicker.platform = _FakeFilePicker(() => FilePickerResult([_fakeApkFile(name: 'BankApp.apk')]));
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('BankApp.apk'), findsOneWidget);
      expect(find.text('Scan this APK'), findsOneWidget);
    });

    testWidgets('a successful scan with findings shows grouped CWE-89/CWE-295 results', (tester) async {
      FilePicker.platform = _FakeFilePicker(() => FilePickerResult([_fakeApkFile()]));
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'POST',
          pathPrefix: '/upload-apk',
          body: _uploadResponse(findings: [
            {'type': 'SQL Injection', 'cwe': 'CWE-89', 'file': 'decompiled/Vuln.java', 'line': 9, 'confidence': 72, 'severity': 'HIGH', 'explanation': ['unsafe query']},
            {'type': 'Certificate Validation', 'cwe': 'CWE-295', 'file': 'decompiled/Cert.java', 'line': 3, 'confidence': 77, 'severity': 'CRITICAL', 'explanation': ['returns true']},
          ]),
        ),
      ]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();
      // ApkScanScreen now reads the picked file's bytes from real disk
      // I/O (dart:io File.readAsBytes) instead of file_picker's in-memory
      // `withData` transfer - a genuine async dart:io operation never
      // completes inside flutter_test's default fake-async zone, so it
      // must run via tester.runAsync() (Flutter's own documented pattern
      // for real I/O/Timers in a widget test). The tap() call itself
      // returns almost immediately (it only synthesizes the pointer
      // event) - the fire-and-forget _startScan() it triggers keeps
      // running afterward, so the callback also waits a real (not
      // fake-zone) beat for that background file-read+upload chain to
      // actually finish before we return to the fake zone; otherwise
      // pumpAndSettle() below would spin forever on a Future that can
      // only ever resolve against the real event loop.
      await tester.runAsync(() async {
        await tester.tap(find.text('Scan this APK'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('SQL Injection — CWE-89'), findsOneWidget);
      expect(find.text('Certificate Validation — CWE-295'), findsOneWidget);
      expect(find.text('decompiled/Vuln.java'), findsOneWidget);
      expect(find.text('decompiled/Cert.java'), findsOneWidget);
      // Phase 7 invariant, visible in the summary row:
      expect(find.text('2'), findsWidgets); // total findings
    });

    testWidgets('a successful scan with zero findings shows the honest empty message', (tester) async {
      FilePicker.platform = _FakeFilePicker(() => FilePickerResult([_fakeApkFile()]));
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/upload-apk', body: _uploadResponse(riskLevel: 'low')),
      ]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();
      // ApkScanScreen now reads the picked file's bytes from real disk
      // I/O (dart:io File.readAsBytes) instead of file_picker's in-memory
      // `withData` transfer - a genuine async dart:io operation never
      // completes inside flutter_test's default fake-async zone, so it
      // must run via tester.runAsync() (Flutter's own documented pattern
      // for real I/O/Timers in a widget test). The tap() call itself
      // returns almost immediately (it only synthesizes the pointer
      // event) - the fire-and-forget _startScan() it triggers keeps
      // running afterward, so the callback also waits a real (not
      // fake-zone) beat for that background file-read+upload chain to
      // actually finish before we return to the fake zone; otherwise
      // pumpAndSettle() below would spin forever on a Future that can
      // only ever resolve against the real event loop.
      await tester.runAsync(() async {
        await tester.tap(find.text('Scan this APK'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('No CWE-89 or CWE-295 vulnerabilities detected.'), findsOneWidget);
      // Must never claim an absolute safety guarantee.
      expect(find.textContaining('SAFE'), findsNothing);
    });

    testWidgets('a backend failure shows a retryable error, not a raw exception', (tester) async {
      FilePicker.platform = _FakeFilePicker(() => FilePickerResult([_fakeApkFile()]));
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/upload-apk', status: 500, body: {'detail': 'boom'}),
      ]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();
      // ApkScanScreen now reads the picked file's bytes from real disk
      // I/O (dart:io File.readAsBytes) instead of file_picker's in-memory
      // `withData` transfer - a genuine async dart:io operation never
      // completes inside flutter_test's default fake-async zone, so it
      // must run via tester.runAsync() (Flutter's own documented pattern
      // for real I/O/Timers in a widget test). The tap() call itself
      // returns almost immediately (it only synthesizes the pointer
      // event) - the fire-and-forget _startScan() it triggers keeps
      // running afterward, so the callback also waits a real (not
      // fake-zone) beat for that background file-read+upload chain to
      // actually finish before we return to the fake zone; otherwise
      // pumpAndSettle() below would spin forever on a Future that can
      // only ever resolve against the real event loop.
      await tester.runAsync(() async {
        await tester.tap(find.text('Scan this APK'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('The security service is currently unavailable. Please try again later.'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });

    testWidgets('an oversized APK shows the real 413 message', (tester) async {
      FilePicker.platform = _FakeFilePicker(() => FilePickerResult([_fakeApkFile()]));
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'POST', pathPrefix: '/upload-apk', status: 413, body: {'detail': 'APK exceeds the 100MB upload limit.'}),
      ]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();
      // ApkScanScreen now reads the picked file's bytes from real disk
      // I/O (dart:io File.readAsBytes) instead of file_picker's in-memory
      // `withData` transfer - a genuine async dart:io operation never
      // completes inside flutter_test's default fake-async zone, so it
      // must run via tester.runAsync() (Flutter's own documented pattern
      // for real I/O/Timers in a widget test). The tap() call itself
      // returns almost immediately (it only synthesizes the pointer
      // event) - the fire-and-forget _startScan() it triggers keeps
      // running afterward, so the callback also waits a real (not
      // fake-zone) beat for that background file-read+upload chain to
      // actually finish before we return to the fake zone; otherwise
      // pumpAndSettle() below would spin forever on a Future that can
      // only ever resolve against the real event loop.
      await tester.runAsync(() async {
        await tester.tap(find.text('Scan this APK'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('APK exceeds the 100MB upload limit.'), findsOneWidget);
    });

    testWidgets('scanning another APK clears the previous result before the new one arrives', (tester) async {
      var pickCount = 0;
      FilePicker.platform = _FakeFilePicker(() {
        pickCount++;
        return FilePickerResult([_fakeApkFile(name: pickCount == 1 ? 'First.apk' : 'Second.apk')]);
      });
      final repo = AppsRepository(AppsApiService(ApiClient(client: buildFakeClient([
        FakeRoute(
          method: 'POST',
          pathPrefix: '/upload-apk',
          body: _uploadResponse(appName: 'First.apk', findings: [
            {'type': 'SQL Injection', 'cwe': 'CWE-89', 'file': 'decompiled/First.java', 'line': 1, 'confidence': 90, 'severity': 'HIGH', 'explanation': []},
          ]),
        ),
      ]))));

      await tester.pumpWidget(_wrap(const ApkScanScreen(), repo));
      await tester.tap(find.text('Choose APK'));
      await tester.pumpAndSettle();
      // ApkScanScreen now reads the picked file's bytes from real disk
      // I/O (dart:io File.readAsBytes) instead of file_picker's in-memory
      // `withData` transfer - a genuine async dart:io operation never
      // completes inside flutter_test's default fake-async zone, so it
      // must run via tester.runAsync() (Flutter's own documented pattern
      // for real I/O/Timers in a widget test). The tap() call itself
      // returns almost immediately (it only synthesizes the pointer
      // event) - the fire-and-forget _startScan() it triggers keeps
      // running afterward, so the callback also waits a real (not
      // fake-zone) beat for that background file-read+upload chain to
      // actually finish before we return to the fake zone; otherwise
      // pumpAndSettle() below would spin forever on a Future that can
      // only ever resolve against the real event loop.
      await tester.runAsync(() async {
        await tester.tap(find.text('Scan this APK'));
        await Future<void>.delayed(const Duration(milliseconds: 200));
      });
      await tester.pumpAndSettle();

      expect(find.text('decompiled/First.java'), findsOneWidget);

      await tester.ensureVisible(find.text('Scan another APK'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Scan another APK'));
      await tester.pumpAndSettle();

      // Back at the pick screen - the previous finding must not still be visible.
      expect(find.text('decompiled/First.java'), findsNothing);
      expect(find.text('Choose APK'), findsOneWidget);
    });
  });
}
