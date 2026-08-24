import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:dualvulndroid_flutter/models/compatibility_model.dart';
import 'package:dualvulndroid_flutter/widgets/decision_card.dart';

void main() {
  group('DecisionCard', () {
    // 18. Final recommendation rendering - renders exactly the backend's
    // own recommendation state, never a client-computed verdict.
    for (final entry in {
      'SAFE_TO_INSTALL': 'Safe to install',
      'INSTALL_WITH_CAUTION': 'Install with caution',
      'AVOID_INSTALLING': 'Avoid installing',
      'DO_NOT_INSTALL_ON_THIS_DEVICE': 'Do not install on this device',
      'SECURITY_ASSESSMENT_UNAVAILABLE': 'Security assessment unavailable',
    }.entries) {
      testWidgets('renders ${entry.key} as "${entry.value}"', (tester) async {
        await tester.pumpWidget(MaterialApp(
          home: Scaffold(
            body: DecisionCard(
              recommendation: FinalRecommendation(recommendation: entry.key, reason: 'A real backend-provided reason.'),
            ),
          ),
        ));

        expect(find.text(entry.value), findsOneWidget);
        expect(find.text('A real backend-provided reason.'), findsOneWidget);
      });
    }
  });
}
