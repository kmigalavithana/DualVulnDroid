import 'package:flutter/material.dart';

import '../models/feedback_model.dart';
import '../theme/app_colors.dart';

/// The four explicit feedback actions (Part 11): Useful / Not useful /
/// Prefer this / Not for me. Purely presentational - persistence lives in
/// FeedbackRepository, called by the parent screen.
class FeedbackButtons extends StatelessWidget {
  final FeedbackType? selected;
  final ValueChanged<FeedbackType> onSelect;

  const FeedbackButtons({super.key, required this.selected, required this.onSelect});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: FeedbackType.values.map((type) {
        final isSelected = selected == type;
        return ChoiceChip(
          label: Text(type.label),
          selected: isSelected,
          onSelected: (_) => onSelect(type),
          avatar: Icon(_iconFor(type), size: 16, color: isSelected ? AppColors.accent : AppColors.textSecondary),
        );
      }).toList(),
    );
  }

  IconData _iconFor(FeedbackType type) => switch (type) {
        FeedbackType.useful => Icons.thumb_up_outlined,
        FeedbackType.notUseful => Icons.thumb_down_outlined,
        FeedbackType.preferThis => Icons.favorite_outline,
        FeedbackType.notForMe => Icons.block_outlined,
      };
}
