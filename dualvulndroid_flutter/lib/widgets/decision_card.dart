import 'package:flutter/material.dart';

import '../models/compatibility_model.dart';
import '../theme/app_colors.dart';

/// Renders the backend's own FinalRecommendation as-is (Phase 9, Part
/// 14) - this widget never computes a verdict itself, only presents
/// whichever of the backend's explicit states was actually returned:
/// SAFE_TO_INSTALL, INSTALL_WITH_CAUTION, AVOID_INSTALLING,
/// DO_NOT_INSTALL_ON_THIS_DEVICE, SECURITY_ASSESSMENT_UNAVAILABLE, or
/// MANUAL_REVIEW (the decision engine's existing catch-all).
class DecisionCard extends StatelessWidget {
  final FinalRecommendation recommendation;

  const DecisionCard({super.key, required this.recommendation});

  (Color, IconData, String) get _presentation {
    switch (recommendation.recommendation) {
      case 'SAFE_TO_INSTALL':
        return (AppColors.riskLow, Icons.verified, 'Safe to install');
      case 'INSTALL_WITH_CAUTION':
        return (AppColors.riskMedium, Icons.error_outline, 'Install with caution');
      case 'AVOID_INSTALLING':
        return (AppColors.riskHigh, Icons.warning_rounded, 'Avoid installing');
      case 'DO_NOT_INSTALL_ON_THIS_DEVICE':
        return (AppColors.riskMedium, Icons.phonelink_erase, 'Do not install on this device');
      case 'SECURITY_ASSESSMENT_UNAVAILABLE':
        return (AppColors.riskUnknown, Icons.help_outline, 'Security assessment unavailable');
      case 'MANUAL_REVIEW':
        return (AppColors.riskUnknown, Icons.search, 'Needs manual review');
      default:
        return (AppColors.riskUnknown, Icons.help_outline, recommendation.recommendation);
    }
  }

  @override
  Widget build(BuildContext context) {
    final (color, icon, label) = _presentation;
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: color, width: 1.5),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Icon(icon, color: color, size: 36),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: TextStyle(color: color, fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                  if (recommendation.reason.isNotEmpty) ...[
                    const SizedBox(height: 6),
                    Text(recommendation.reason, style: const TextStyle(color: AppColors.textSecondary, fontSize: 13)),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
