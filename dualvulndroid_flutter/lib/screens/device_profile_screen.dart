import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../engines/recommendation_engine.dart';
import '../repositories/device_profile_repository.dart';
import '../theme/app_icons.dart';
import '../theme/app_spacing.dart';
import '../utils/byte_format.dart';
import '../widgets/context_banner.dart';
import '../widgets/device_summary_card.dart';
import '../widgets/smartapp_ui.dart';

/// "My Device" - the full device profile, sourced entirely from real
/// platform APIs via DeviceProfileRepository. Any field the platform
/// couldn't report is shown as "Unavailable", never invented.
class DeviceProfileScreen extends StatelessWidget {
  const DeviceProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final repo = context.watch<DeviceProfileRepository>();
    final profile = repo.profile;
    final theme = Theme.of(context);
    const unavailable = 'Unavailable';

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Device'),
        actions: [
          IconButton(
            tooltip: 'Refresh device data',
            icon: const Icon(AppIcons.refresh),
            onPressed: repo.isLoading ? null : () => repo.refresh(),
          ),
        ],
      ),
      body: ListView(
        padding: AppSpacing.pagePadding,
        children: [
          DeviceSummaryCard(profile: profile, loading: repo.isLoading, showProfileLabel: true),
          const SizedBox(height: AppSpacing.md),
          ContextBanner(effects: const RecommendationEngine().contextEffectsFor(profile)),
          const SizedBox(height: AppSpacing.xl),
          if (profile.manufacturer != null || profile.model != null)
            _InfoSection(
              title: 'Device',
              rows: [
                if (profile.manufacturer != null) DetailRow(label: 'Manufacturer', value: profile.manufacturer!, icon: Icons.business_outlined),
                if (profile.model != null) DetailRow(label: 'Model', value: profile.model!, icon: AppIcons.device),
              ],
            ),
          _InfoSection(
            title: 'Memory',
            rows: [
              DetailRow(label: 'Total RAM', value: formatMb(profile.ramTotalMb), icon: AppIcons.ram, muted: profile.ramTotalMb == null),
              DetailRow(label: 'Available RAM', value: formatMb(profile.ramAvailableMb), icon: AppIcons.ram, muted: profile.ramAvailableMb == null),
              DetailRow(
                label: 'Low-RAM device',
                value: profile.isLowRamDevice == null ? unavailable : (profile.isLowRamDevice! ? 'Yes' : 'No'),
                icon: AppIcons.performance,
                muted: profile.isLowRamDevice == null,
              ),
            ],
          ),
          _InfoSection(
            title: 'Storage',
            rows: [
              DetailRow(label: 'Total storage', value: formatBytes(profile.storageTotalBytes), icon: AppIcons.storage, muted: profile.storageTotalBytes == null),
              DetailRow(label: 'Free storage', value: formatBytes(profile.storageFreeBytes), icon: AppIcons.storage, muted: profile.storageFreeBytes == null),
            ],
          ),
          _InfoSection(
            title: 'System',
            rows: [
              DetailRow(label: 'Android version', value: profile.androidRelease ?? unavailable, icon: AppIcons.android, muted: profile.androidRelease == null),
              DetailRow(label: 'API level', value: profile.androidSdkInt?.toString() ?? unavailable, icon: AppIcons.android, muted: profile.androidSdkInt == null),
              DetailRow(
                label: 'CPU architecture',
                value: profile.abis.isNotEmpty ? profile.abis.join(', ') : unavailable,
                icon: AppIcons.cpu,
                muted: profile.abis.isEmpty,
              ),
            ],
          ),
          _InfoSection(
            title: 'Right now',
            rows: [
              DetailRow(
                label: 'Battery',
                value: profile.batteryLevel != null ? '${profile.batteryLevel}%' : unavailable,
                icon: AppIcons.battery,
                muted: profile.batteryLevel == null,
              ),
              DetailRow(label: 'Connectivity', value: profile.connectivityStatus.label, icon: AppIcons.network),
            ],
          ),
          Text(
            'This information comes directly from your device\'s operating system and is used only to suggest apps '
            'that fit your hardware better. No performance benchmark is implied.',
            style: theme.textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _InfoSection extends StatelessWidget {
  final String title;
  final List<Widget> rows;
  const _InfoSection({required this.title, required this.rows});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(padding: const EdgeInsets.only(bottom: AppSpacing.sm, left: AppSpacing.xxs), child: Overline(title)),
          SmartAppCard(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg, vertical: AppSpacing.sm),
            child: Column(children: rows),
          ),
        ],
      ),
    );
  }
}
