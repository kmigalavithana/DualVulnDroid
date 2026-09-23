import 'package:flutter/material.dart';

import '../models/user_preferences_model.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import 'category_icons.dart';
import 'smartapp_ui.dart';

/// One category tile - icon badge plus label.
class CategoryCard extends StatelessWidget {
  final AppCategory category;
  final VoidCallback onTap;
  final bool selected;

  const CategoryCard({super.key, required this.category, required this.onTap, this.selected = false});

  @override
  Widget build(BuildContext context) {
    return SmartAppCard(
      onTap: onTap,
      color: selected ? AppColors.accentSoft : null,
      borderColor: selected ? AppColors.accent : null,
      semanticLabel: '${category.label} apps',
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.lg, horizontal: AppSpacing.sm),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          IconBadge(icon: resolveIconKey(category.iconKey)),
          const SizedBox(height: AppSpacing.sm),
          Text(
            category.label,
            textAlign: TextAlign.center,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(fontSize: 13),
          ),
        ],
      ),
    );
  }
}
