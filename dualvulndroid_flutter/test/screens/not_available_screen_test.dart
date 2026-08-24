import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/screens/not_available_screen.dart';

void main() {
  group('NotAvailableScreen', () {
    testWidgets('Installed Apps copy: only the honest message renders, no app-list content', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: NotAvailableScreen(
          title: 'Installed Apps',
          message: 'On-device app scanning is not available in this version. Use Search to look up an application instead.',
        ),
      ));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Installed Apps'), findsOneWidget);
      expect(find.text('On-device app scanning is not available in this version. Use Search to look up an application instead.'),
          findsOneWidget);
      // No fabricated placeholder app names anywhere on this screen.
      for (final fakeName in ['WhatsApp', 'TikTok', 'Chrome', 'Facebook', 'Instagram']) {
        expect(find.textContaining(fakeName), findsNothing);
      }
    });

    testWidgets('Upload APK copy: only the honest message renders', (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: NotAvailableScreen(
          title: 'Upload APK',
          message: 'Uploading an APK for direct analysis is not available in this version. Use Search to look up an already-analyzed application instead.',
        ),
      ));
      await tester.pumpAndSettle();

      expect(tester.takeException(), isNull);
      expect(find.text('Upload APK'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });
  });
}
