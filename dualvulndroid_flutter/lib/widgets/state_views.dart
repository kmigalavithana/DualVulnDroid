import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import 'smartapp_ui.dart';

/// The three non-content states every data screen handles - loading,
/// empty, and error - in one consistent style. Never filled with
/// placeholder "content": a skeleton is visibly a skeleton, and an empty
/// state explains why there is nothing to show.

class LoadingView extends StatelessWidget {
  final String? message;
  const LoadingView({super.key, this.message});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Semantics(
        liveRegion: true,
        label: message ?? 'Loading',
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(width: 32, height: 32, child: CircularProgressIndicator(strokeWidth: 3)),
            if (message != null) ...[
              const SizedBox(height: AppSpacing.lg),
              Text(message!, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
            ],
          ],
        ),
      ),
    );
  }
}

/// Lightweight shimmer-free skeleton rows shown while a list loads - the
/// same shape as the real app rows, so the layout doesn't jump.
class SkeletonList extends StatefulWidget {
  final int count;
  final String semanticLabel;
  const SkeletonList({super.key, this.count = 5, this.semanticLabel = 'Loading apps'});

  @override
  State<SkeletonList> createState() => _SkeletonListState();
}

class _SkeletonListState extends State<SkeletonList> with SingleTickerProviderStateMixin {
  late final AnimationController _controller =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 900))..repeat(reverse: true);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: widget.semanticLabel,
      liveRegion: true,
      excludeSemantics: true,
      child: FadeTransition(
        opacity: Tween<double>(begin: 0.45, end: 0.9).animate(_controller),
        child: Column(
          children: List.generate(
            widget.count,
            (_) => Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.md),
              child: SmartAppCard(
                child: Row(
                  children: [
                    _block(width: 48, height: 48, radius: 14),
                    const SizedBox(width: AppSpacing.md),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _block(width: double.infinity, height: 14),
                          const SizedBox(height: AppSpacing.sm),
                          _block(width: 120, height: 11),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _block({required double width, required double height, double radius = 6}) => Container(
        width: width,
        height: height,
        decoration: BoxDecoration(color: AppColors.surfaceAlt, borderRadius: BorderRadius.circular(radius)),
      );
}

class EmptyStateView extends StatelessWidget {
  final String message;
  final IconData icon;
  final String? title;
  final String? actionLabel;
  final IconData? actionIcon;
  final VoidCallback? onAction;
  const EmptyStateView({
    super.key,
    required this.message,
    this.icon = Icons.inbox_outlined,
    this.title,
    this.actionLabel,
    this.actionIcon,
    this.onAction,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxl, vertical: AppSpacing.section),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            IconBadge(icon: icon, color: AppColors.textSecondary, size: 64),
            const SizedBox(height: AppSpacing.lg),
            if (title != null) ...[
              Text(title!, textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
              const SizedBox(height: AppSpacing.sm),
            ],
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 360),
              child: Text(message, textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: AppSpacing.xl),
              PrimaryButton(label: actionLabel!, icon: actionIcon, onPressed: onAction, expand: false),
            ],
          ],
        ),
      ),
    );
  }
}

/// A real, user-facing error message (never a raw exception/stack trace)
/// with a retry action.
class ErrorStateView extends StatelessWidget {
  final String message;
  final String? title;
  final VoidCallback? onRetry;
  const ErrorStateView({super.key, required this.message, this.title, this.onRetry});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxl, vertical: AppSpacing.section),
        child: Semantics(
          liveRegion: true,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const IconBadge(icon: Icons.cloud_off_rounded, color: AppColors.error, size: 64),
              const SizedBox(height: AppSpacing.lg),
              Text(title ?? 'Something went wrong', textAlign: TextAlign.center, style: theme.textTheme.titleMedium),
              const SizedBox(height: AppSpacing.sm),
              Text(message, textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
              if (onRetry != null) ...[
                const SizedBox(height: AppSpacing.xl),
                SecondaryButton(label: 'Retry', icon: AppIcons.refresh, onPressed: onRetry, expand: false),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
