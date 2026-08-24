import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// A risk-level label that is ALWAYS icon + text together, never color
/// alone (Phase 9, Part 20). riskLevel is displayed exactly as the
/// backend returned it (upper-cased for display only) - this widget
/// never invents a risk level of its own.
class RiskBadge extends StatelessWidget {
  final String? riskLevel;
  final double iconSize;

  const RiskBadge({super.key, required this.riskLevel, this.iconSize = 18});

  IconData get _icon {
    switch (riskLevel?.toUpperCase()) {
      case 'LOW':
        return Icons.check_circle;
      case 'MEDIUM':
        return Icons.error_outline;
      case 'HIGH':
      case 'CRITICAL':
        return Icons.warning_rounded;
      default:
        return Icons.help_outline;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forRiskLevel(riskLevel);
    final label = riskLevel?.toUpperCase() ?? 'UNKNOWN';
    return Semantics(
      label: 'Risk level: $label',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color, width: 1),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(_icon, color: color, size: iconSize),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
