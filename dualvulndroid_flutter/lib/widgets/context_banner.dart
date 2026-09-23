import 'package:flutter/material.dart';

import '../models/context_effect_model.dart';
import '../theme/app_icons.dart';
import 'smartapp_ui.dart';

/// Transparently surfaces the real, currently-active [ContextEffect]s
/// driving a ranking ("Show context effects transparently. Do not
/// silently change user preferences.") - shown only when at least one
/// effect is actually active, never a permanent fixture.
class ContextBanner extends StatelessWidget {
  final List<ContextEffect> effects;

  const ContextBanner({super.key, required this.effects});

  @override
  Widget build(BuildContext context) {
    if (effects.isEmpty) return const SizedBox.shrink();
    return InsightBanner(
      title: 'Adjusted for your device right now',
      icon: AppIcons.device,
      messages: [for (final effect in effects) effect.message],
    );
  }
}
