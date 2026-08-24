import 'package:flutter/material.dart';

import '../models/compatibility_model.dart';
import '../theme/app_colors.dart';

class CompatibilityBadge extends StatelessWidget {
  final CompatibilityStatus status;

  const CompatibilityBadge({super.key, required this.status});

  (Color, IconData, String) get _presentation {
    switch (status) {
      case CompatibilityStatus.compatible:
        return (AppColors.riskLow, Icons.check_circle, 'COMPATIBLE');
      case CompatibilityStatus.incompatible:
        return (AppColors.riskHigh, Icons.cancel, 'INCOMPATIBLE');
      case CompatibilityStatus.notAvailable:
      case CompatibilityStatus.unknown:
        return (AppColors.riskUnknown, Icons.help_outline, 'NOT AVAILABLE');
    }
  }

  @override
  Widget build(BuildContext context) {
    final (color, icon, label) = _presentation;
    return Semantics(
      label: 'Compatibility: $label',
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
            Icon(icon, color: color, size: 18),
            const SizedBox(width: 6),
            Text(label, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 13)),
          ],
        ),
      ),
    );
  }
}
