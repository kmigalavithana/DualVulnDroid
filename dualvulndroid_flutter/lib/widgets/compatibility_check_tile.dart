import 'package:flutter/material.dart';

import '../models/compatibility_model.dart';
import 'compatibility_badge.dart';

/// One row inside the compatibility breakdown (Part 12: "Show individual
/// checks: Android version, Required features, ABI").
class CompatibilityCheckTile extends StatelessWidget {
  final String label;
  final CompatibilityCheck check;

  const CompatibilityCheckTile({super.key, required this.label, required this.check});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label, style: const TextStyle(fontSize: 14))),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              CompatibilityBadge(status: check.status),
              if (check.missing.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    'Missing: ${check.missing.join(", ")}',
                    style: const TextStyle(fontSize: 11, color: Colors.grey),
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
