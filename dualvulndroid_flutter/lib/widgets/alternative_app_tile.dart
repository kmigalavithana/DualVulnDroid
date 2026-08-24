import 'package:flutter/material.dart';

import '../models/alternative_app_model.dart';
import '../theme/app_colors.dart';
import 'risk_badge.dart';

/// Phase 9, Part 15 - real fields only: name, risk level, security
/// score/confidence if the backend provided them, and the backend's own
/// transparent reasons. No rating/download-count/popularity field
/// exists on AlternativeApp, so none can appear here.
class AlternativeAppTile extends StatelessWidget {
  final AlternativeApp alternative;

  const AlternativeAppTile({super.key, required this.alternative});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(alternative.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                ),
                RiskBadge(riskLevel: alternative.riskLevel),
              ],
            ),
            if (alternative.packageName != null) ...[
              const SizedBox(height: 2),
              Text(alternative.packageName!, style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
            ],
            if (alternative.securityScore != null || alternative.securityConfidence != null) ...[
              const SizedBox(height: 8),
              Row(
                children: [
                  if (alternative.securityScore != null) Text('Security score: ${alternative.securityScore}', style: const TextStyle(fontSize: 12)),
                  if (alternative.securityScore != null && alternative.securityConfidence != null) const SizedBox(width: 12),
                  if (alternative.securityConfidence != null) Text('Confidence: ${alternative.securityConfidence}%', style: const TextStyle(fontSize: 12)),
                ],
              ),
            ],
            if (alternative.reasons.isNotEmpty) ...[
              const SizedBox(height: 8),
              ...alternative.reasons.map((r) => Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Icon(Icons.check, size: 14, color: AppColors.riskLow),
                        const SizedBox(width: 6),
                        Expanded(child: Text(r, style: const TextStyle(fontSize: 12, color: AppColors.textSecondary))),
                      ],
                    ),
                  )),
            ],
          ],
        ),
      ),
    );
  }
}
