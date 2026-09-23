import 'package:flutter/material.dart';

import '../models/user_preferences_model.dart';
import '../routing/app_router.dart';
import '../theme/app_spacing.dart';
import '../widgets/category_card.dart';
import '../widgets/smartapp_ui.dart';

/// "What are you looking for?" - pick a category to see ranked live matches.
class CategorySelectionScreen extends StatelessWidget {
  const CategorySelectionScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Browse categories')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(AppSpacing.page, AppSpacing.xs, AppSpacing.page, AppSpacing.section),
        children: [
          const SectionHeader(
            title: 'What are you looking for?',
            subtitle: 'Pick a category and we\'ll rank apps by how well they fit your preferences and device.',
          ),
          ResponsiveGrid(
            columns: 3,
            children: [
              for (final category in AppCategory.values)
                CategoryCard(category: category, onTap: () => AppRouter.toResultsForCategory(context, category)),
            ],
          ),
        ],
      ),
    );
  }
}
