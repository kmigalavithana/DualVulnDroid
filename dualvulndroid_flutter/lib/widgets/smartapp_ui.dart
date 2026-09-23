import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';

/// SmartApp's reusable building blocks. Every screen composes these
/// instead of restyling Containers/Text locally, so spacing, radii,
/// typography and colors stay identical across the app.

/// A bordered surface card with optional tap feedback.
class SmartAppCard extends StatelessWidget {
  final Widget child;
  final VoidCallback? onTap;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final Color? borderColor;
  final String? semanticLabel;

  const SmartAppCard({
    super.key,
    required this.child,
    this.onTap,
    this.padding = AppSpacing.cardPadding,
    this.color,
    this.borderColor,
    this.semanticLabel,
  });

  @override
  Widget build(BuildContext context) {
    final content = Padding(padding: padding, child: child);
    return Semantics(
      label: semanticLabel,
      button: onTap != null,
      container: true,
      child: DecoratedBox(
        // Very subtle elevation - a soft 1-2px shadow, no glow.
        decoration: BoxDecoration(
          borderRadius: AppRadius.lgAll,
          boxShadow: const [
            BoxShadow(color: AppColors.shadow, blurRadius: 6, offset: Offset(0, 1)),
          ],
        ),
        child: Material(
          color: color ?? AppColors.surface,
          shape: RoundedRectangleBorder(
            borderRadius: AppRadius.lgAll,
            side: BorderSide(color: borderColor ?? AppColors.border),
          ),
          clipBehavior: Clip.antiAlias,
          child: onTap == null ? content : InkWell(onTap: onTap, child: content),
        ),
      ),
    );
  }
}

/// Section title + optional supporting line + optional trailing action.
class SectionHeader extends StatelessWidget {
  final String title;
  final String? subtitle;
  final String? actionLabel;
  final VoidCallback? onAction;
  final IconData? icon;

  /// A small badge shown next to the title (e.g. a count).
  final Widget? badge;

  const SectionHeader({super.key, required this.title, this.subtitle, this.actionLabel, this.onAction, this.icon, this.badge});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.md),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 20, color: AppColors.accent),
            const SizedBox(width: AppSpacing.sm),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  spacing: AppSpacing.sm,
                  runSpacing: AppSpacing.xxs,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Semantics(header: true, child: Text(title, style: theme.textTheme.titleLarge)),
                    ?badge,
                  ],
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: AppSpacing.xxs),
                  Text(subtitle!, style: theme.textTheme.bodySmall),
                ],
              ],
            ),
          ),
          if (actionLabel != null && onAction != null) TextButton(onPressed: onAction, child: Text(actionLabel!)),
        ],
      ),
    );
  }
}

/// Small uppercase overline ("YOUR DEVICE", "CURRENT APP").
class Overline extends StatelessWidget {
  final String text;
  final Color? color;
  const Overline(this.text, {super.key, this.color});

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall?.copyWith(color: color ?? AppColors.textMuted),
    );
  }
}

/// A rounded, tinted square holding an icon - the one icon container
/// style used across quick actions, list rows and headers.
class IconBadge extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;

  const IconBadge({super.key, required this.icon, this.color = AppColors.accent, this.size = 40});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(color: color.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(size * 0.3)),
      child: Icon(icon, color: color, size: size * 0.52),
    );
  }
}

/// One labeled value (device stats, evaluation metrics).
class MetricCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData? icon;
  final String? caption;
  final bool muted;

  const MetricCard({super.key, required this.label, required this.value, this.icon, this.caption, this.muted = false});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Semantics(
      label: '$label: $value',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.md),
        decoration: BoxDecoration(color: AppColors.surfaceAlt, borderRadius: AppRadius.mdAll),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (icon != null) ...[
                  Icon(icon, size: 15, color: AppColors.textSecondary),
                  const SizedBox(width: AppSpacing.xs),
                ],
                Flexible(child: Overline(label)),
              ],
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: theme.textTheme.titleMedium?.copyWith(color: muted ? AppColors.textMuted : AppColors.textPrimary),
            ),
            if (caption != null) ...[
              const SizedBox(height: 2),
              Text(caption!, style: theme.textTheme.labelSmall?.copyWith(letterSpacing: 0)),
            ],
          ],
        ),
      ),
    );
  }
}

/// Lays children out in [columns] equal-width columns that wrap onto new
/// rows - never a fixed-width card, so nothing overflows on small phones.
class ResponsiveGrid extends StatelessWidget {
  final List<Widget> children;
  final int columns;
  final double spacing;

  const ResponsiveGrid({super.key, required this.children, this.columns = 2, this.spacing = AppSpacing.md});

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final effectiveColumns = constraints.maxWidth < 300 ? 1 : columns;
      final width = (constraints.maxWidth - spacing * (effectiveColumns - 1)) / effectiveColumns;
      return Wrap(
        spacing: spacing,
        runSpacing: spacing,
        children: [for (final child in children) SizedBox(width: width, child: child)],
      );
    });
  }
}

/// A selectable preference chip with an icon (never color alone - a
/// selected chip also shows a check icon). Soft fills only: light gray
/// when off, soft indigo when on - no outlines.
class PreferenceChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool selected;
  final ValueChanged<bool>? onSelected;

  const PreferenceChip({super.key, required this.label, required this.icon, required this.selected, this.onSelected});

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Text(label),
      avatar: Icon(selected ? Icons.check_rounded : icon, size: 18, color: selected ? AppColors.accent : AppColors.textSecondary),
      selected: selected,
      onSelected: onSelected,
      backgroundColor: AppColors.surfaceAlt,
      selectedColor: AppColors.accentSoft,
      labelStyle: TextStyle(
        fontSize: 13,
        fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
        color: selected ? AppColors.accent : AppColors.textSecondary,
      ),
      side: BorderSide.none,
      tooltip: selected ? '$label (selected)' : label,
    );
  }
}

/// A small read-only tag: icon + short text.
class InfoPill extends StatelessWidget {
  final String label;
  final IconData? icon;
  final Color color;

  const InfoPill({super.key, required this.label, this.icon, this.color = AppColors.textSecondary});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.sm, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: AppRadius.pillAll,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 14, color: color),
            const SizedBox(width: 4),
          ],
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: color == AppColors.textSecondary ? AppColors.textPrimary : color),
            ),
          ),
        ],
      ),
    );
  }
}

/// The user/device match percentage - a ring plus the number. The label
/// always says "match" so it's never read as a universal quality score.
class MatchIndicator extends StatelessWidget {
  final int percent;
  final double size;

  const MatchIndicator({super.key, required this.percent, this.size = 52});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forMatchPercent(percent);
    return Semantics(
      label: '$percent percent match for your profile',
      excludeSemantics: true,
      child: SizedBox(
        width: size,
        height: size,
        child: Stack(
          alignment: Alignment.center,
          children: [
            SizedBox.expand(
              child: CircularProgressIndicator(
                value: percent / 100,
                strokeWidth: size * 0.08,
                color: color,
                backgroundColor: AppColors.surfaceAlt,
                strokeCap: StrokeCap.round,
              ),
            ),
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('$percent%', style: TextStyle(fontSize: size * 0.27, fontWeight: FontWeight.w800, color: AppColors.textPrimary, height: 1)),
                if (size >= 52)
                  Text('match', style: TextStyle(fontSize: size * 0.17, color: AppColors.textSecondary, height: 1.2)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Compact inline match label ("87% match") for dense lists.
class MatchPill extends StatelessWidget {
  final int percent;
  const MatchPill({super.key, required this.percent});

  @override
  Widget build(BuildContext context) {
    final color = AppColors.forMatchPercent(percent);
    return Semantics(
      label: '$percent percent match',
      excludeSemantics: true,
      child: InfoPill(label: '$percent% match', icon: AppIcons.recommendations, color: color == AppColors.riskUnknown ? AppColors.textSecondary : color),
    );
  }
}

/// Star + rating (+ review count) - or nothing when no rating exists.
class RatingLabel extends StatelessWidget {
  final double? rating;
  final int? reviewCount;
  const RatingLabel({super.key, required this.rating, this.reviewCount});

  @override
  Widget build(BuildContext context) {
    final value = rating;
    if (value == null) return const SizedBox.shrink();
    return Semantics(
      label: 'Rated ${value.toStringAsFixed(1)} out of 5',
      excludeSemantics: true,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(AppIcons.rating, size: 16, color: AppColors.warning),
          const SizedBox(width: 3),
          Text(value.toStringAsFixed(1), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          if (reviewCount != null) ...[
            const SizedBox(width: 4),
            Text('(${formatCompactCount(reviewCount!)})', style: const TextStyle(color: AppColors.textSecondary, fontSize: 12)),
          ],
        ],
      ),
    );
  }
}

/// 18400 -> "18.4K", 2100000 -> "2.1M".
String formatCompactCount(int value) {
  if (value >= 1000000) return '${(value / 1000000).toStringAsFixed(value >= 10000000 ? 0 : 1)}M';
  if (value >= 1000) return '${(value / 1000).toStringAsFixed(value >= 10000 ? 0 : 1)}K';
  return '$value';
}

/// The strongest action on a screen.
class PrimaryButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool expand;

  const PrimaryButton({super.key, required this.label, this.icon, this.onPressed, this.expand = true});

  @override
  Widget build(BuildContext context) {
    final button = icon == null
        ? FilledButton(onPressed: onPressed, child: Text(label))
        : FilledButton.icon(onPressed: onPressed, icon: Icon(icon, size: 20), label: Text(label));
    return expand ? SizedBox(width: double.infinity, child: button) : button;
  }
}

/// A supporting action paired with [PrimaryButton].
class SecondaryButton extends StatelessWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onPressed;
  final bool expand;

  const SecondaryButton({super.key, required this.label, this.icon, this.onPressed, this.expand = true});

  @override
  Widget build(BuildContext context) {
    final button = icon == null
        ? OutlinedButton(onPressed: onPressed, child: Text(label))
        : OutlinedButton.icon(onPressed: onPressed, icon: Icon(icon, size: 20), label: Text(label));
    return expand ? SizedBox(width: double.infinity, child: button) : button;
  }
}

/// A tappable settings-style row: icon badge, title, subtitle, chevron.
class NavigationRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final VoidCallback onTap;
  final Color iconColor;

  const NavigationRow({
    super.key,
    required this.icon,
    required this.title,
    this.subtitle,
    required this.onTap,
    this.iconColor = AppColors.accent,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return InkWell(
      onTap: onTap,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.md),
        child: Row(
          children: [
            IconBadge(icon: icon, color: iconColor, size: 38),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: theme.textTheme.titleSmall),
                  if (subtitle != null) ...[
                    const SizedBox(height: 2),
                    Text(subtitle!, style: theme.textTheme.bodySmall),
                  ],
                ],
              ),
            ),
            const Icon(AppIcons.chevron, color: AppColors.textMuted),
          ],
        ),
      ),
    );
  }
}

/// A key/value row inside a details card.
class DetailRow extends StatelessWidget {
  final String label;
  final String value;
  final IconData? icon;
  final bool muted;

  const DetailRow({super.key, required this.label, required this.value, this.icon, this.muted = false});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 17, color: AppColors.textMuted),
            const SizedBox(width: AppSpacing.sm),
          ],
          Expanded(child: Text(label, style: Theme.of(context).textTheme.bodySmall)),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Text(
              value,
              textAlign: TextAlign.end,
              style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, color: muted ? AppColors.textMuted : AppColors.textPrimary),
            ),
          ),
        ],
      ),
    );
  }
}

/// A calm, one-idea callout (context effects, smart insights, notes).
class InsightBanner extends StatelessWidget {
  final String title;
  final List<String> messages;
  final IconData icon;
  final Color color;
  final Widget? footer;

  const InsightBanner({
    super.key,
    required this.title,
    required this.messages,
    this.icon = AppIcons.insight,
    this.color = AppColors.accentCyan,
    this.footer,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: AppRadius.lgAll,
        border: Border.all(color: color.withValues(alpha: 0.28)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: theme.textTheme.titleSmall),
                for (final message in messages) ...[
                  const SizedBox(height: AppSpacing.xs),
                  Text(message, style: theme.textTheme.bodySmall?.copyWith(color: AppColors.textPrimary.withValues(alpha: 0.86))),
                ],
                if (footer != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  footer!,
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
