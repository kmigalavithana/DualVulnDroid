import 'package:flutter/material.dart';

import '../models/device_profile_model.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../utils/byte_format.dart';
import 'smartapp_ui.dart';

/// "YOUR DEVICE": the real RAM / Android / free storage reported by the
/// OS, plus battery and network ONLY when the platform actually reported
/// them. Any missing core value reads "Unavailable" - never a placeholder.
class DeviceSummaryCard extends StatelessWidget {
  final DeviceProfileModel profile;
  final bool loading;
  final VoidCallback? onTap;

  /// Shows the resource-profile line under the stats.
  final bool showProfileLabel;

  /// Hides the "YOUR DEVICE" overline when the screen already has a heading.
  final bool showHeader;

  const DeviceSummaryCard({
    super.key,
    required this.profile,
    this.loading = false,
    this.onTap,
    this.showProfileLabel = false,
    this.showHeader = true,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final android = profile.androidRelease ?? (profile.androidSdkInt != null ? 'API ${profile.androidSdkInt}' : 'Unavailable');
    final stats = <Widget>[
      MetricCard(label: 'RAM', value: formatMb(profile.ramTotalMb), icon: AppIcons.ram, muted: profile.ramTotalMb == null),
      MetricCard(label: 'Android', value: android, icon: AppIcons.android, muted: android == 'Unavailable'),
      MetricCard(
        label: 'Storage',
        value: formatBytes(profile.storageFreeBytes),
        icon: AppIcons.storage,
        muted: profile.storageFreeBytes == null,
      ),
      if (profile.batteryLevel != null) MetricCard(label: 'Battery', value: '${profile.batteryLevel}%', icon: AppIcons.battery),
      if (profile.connectivityStatus != ConnectivityStatus.unavailable)
        MetricCard(
          label: 'Network',
          value: profile.connectivityStatus.label,
          icon: profile.connectivityStatus == ConnectivityStatus.offline ? AppIcons.offline : AppIcons.network,
        ),
    ];

    return SmartAppCard(
      onTap: onTap,
      semanticLabel: onTap != null ? 'Your device. Open device details' : null,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (showHeader) ...[
            Row(
              children: [
                const Icon(AppIcons.device, size: 18, color: AppColors.accent),
                const SizedBox(width: AppSpacing.sm),
                const Expanded(child: Overline('Your device')),
                if (loading)
                  const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                else if (onTap != null)
                  const Icon(AppIcons.chevron, color: AppColors.textMuted, size: 20),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          ResponsiveGrid(columns: 3, spacing: AppSpacing.sm, children: stats),
          if (showProfileLabel) ...[
            const SizedBox(height: AppSpacing.md),
            Row(
              children: [
                const Icon(AppIcons.performance, size: 16, color: AppColors.textSecondary),
                const SizedBox(width: AppSpacing.sm),
                Expanded(child: Text(profile.resourceProfileLabel, style: theme.textTheme.titleSmall)),
              ],
            ),
          ],
        ],
      ),
    );
  }
}
