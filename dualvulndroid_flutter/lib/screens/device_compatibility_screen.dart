import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/compatibility_model.dart';
import '../models/device_profile_model.dart';
import '../repositories/apps_repository.dart';
import '../repositories/device_profile_repository.dart';
import '../theme/app_colors.dart';
import '../widgets/compatibility_badge.dart';
import '../widgets/compatibility_check_tile.dart';
import '../widgets/decision_card.dart';
import '../widgets/state_views.dart';

/// Phase 9, Part 12/13/14. Lets the user provide (or auto-detect) a real
/// device profile, then calls POST /apps/{id}/compatibility and shows
/// the backend's own combined result plus its finalRecommendation - this
/// screen never computes compatibility or a recommendation itself.
class DeviceCompatibilityScreen extends StatefulWidget {
  final int applicationId;
  final String? applicationName;

  const DeviceCompatibilityScreen({super.key, required this.applicationId, this.applicationName});

  @override
  State<DeviceCompatibilityScreen> createState() => _DeviceCompatibilityScreenState();
}

class _DeviceCompatibilityScreenState extends State<DeviceCompatibilityScreen> {
  Future<CompatibilityResponse>? _resultFuture;

  Future<void> _autoDetect() async {
    await context.read<DeviceProfileRepository>().tryAutoDetect();
  }

  void _check() {
    final profile = context.read<DeviceProfileRepository>().profile;
    setState(() {
      _resultFuture = context.read<AppsRepository>().checkCompatibility(widget.applicationId, profile);
    });
  }

  @override
  Widget build(BuildContext context) {
    final deviceRepo = context.watch<DeviceProfileRepository>();
    final profile = deviceRepo.profile;

    return Scaffold(
      appBar: AppBar(title: Text('Device compatibility${widget.applicationName != null ? ' — ${widget.applicationName}' : ''}')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Why we ask', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 6),
                  const Text(
                    'This checks whether your Android version and hardware/CPU capabilities meet what this application actually declares needing in its manifest. '
                    'We never ask for your device\'s RAM, since the backend does not use it to assess compatibility.',
                    style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.phonelink_setup),
                    label: Text(deviceRepo.wasAutoDetected ? 'Re-detect from this device' : 'Detect automatically'),
                    onPressed: _autoDetect,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          _DeviceProfileForm(profile: profile, repo: deviceRepo),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            icon: const Icon(Icons.fact_check_outlined),
            label: const Text('Check compatibility'),
            onPressed: _check,
          ),
          const SizedBox(height: 20),
          if (_resultFuture != null)
            FutureBuilder<CompatibilityResponse>(
              future: _resultFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const LoadingView(message: 'Checking compatibility...');
                }
                if (snapshot.hasError) {
                  final message = snapshot.error is ApiException ? (snapshot.error as ApiException).message : 'Could not check compatibility.';
                  return ErrorStateView(message: message, onRetry: _check);
                }
                final result = snapshot.data!;
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              children: [
                                Text('Overall compatibility', style: Theme.of(context).textTheme.titleMedium),
                                CompatibilityBadge(status: result.compatibility.status),
                              ],
                            ),
                            const Divider(height: 24),
                            CompatibilityCheckTile(label: 'Android version', check: result.compatibility.androidVersion),
                            CompatibilityCheckTile(label: 'Required features', check: result.compatibility.requiredFeatures),
                            CompatibilityCheckTile(label: 'CPU architecture (ABI)', check: result.compatibility.abi),
                            CompatibilityCheckTile(
                              label: 'Hardware (RAM/CPU model)',
                              check: CompatibilityCheck(status: result.hardwareCompatibility.status),
                            ),
                            if (result.compatibility.reasons.isNotEmpty) ...[
                              const Divider(height: 24),
                              ...result.compatibility.reasons.map((r) => Padding(
                                    padding: const EdgeInsets.only(bottom: 4),
                                    child: Text('• $r', style: const TextStyle(fontSize: 13)),
                                  )),
                            ],
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text('Final recommendation', style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: 10),
                    DecisionCard(recommendation: result.finalRecommendation),
                  ],
                );
              },
            ),
        ],
      ),
    );
  }
}

class _DeviceProfileForm extends StatefulWidget {
  final DeviceProfileModel profile;
  final DeviceProfileRepository repo;
  const _DeviceProfileForm({required this.profile, required this.repo});

  @override
  State<_DeviceProfileForm> createState() => _DeviceProfileFormState();
}

class _DeviceProfileFormState extends State<_DeviceProfileForm> {
  late final TextEditingController _androidVersionController;

  @override
  void initState() {
    super.initState();
    _androidVersionController = TextEditingController(text: widget.profile.androidVersion?.toString() ?? '');
  }

  @override
  void didUpdateWidget(_DeviceProfileForm oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Only overwrite the field's text for a real external change (e.g. "Detect
    // automatically") - never on every keystroke, or typing a 2nd digit would
    // fight this update and get silently dropped (the bug this replaces).
    final newValue = widget.profile.androidVersion?.toString() ?? '';
    if (oldWidget.profile.androidVersion != widget.profile.androidVersion && _androidVersionController.text != newValue) {
      _androidVersionController.text = newValue;
    }
  }

  @override
  void dispose() {
    _androidVersionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final profile = widget.profile;
    final repo = widget.repo;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Your device profile', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 12),
            TextFormField(
              controller: _androidVersionController,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Android version (API level)', hintText: 'e.g. 33'),
              onChanged: (value) => repo.updateAndroidVersion(int.tryParse(value)),
            ),
            const SizedBox(height: 16),
            const Text('Supported hardware features', style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: kCommonHardwareFeatures.map((f) => FilterChip(
                    label: Text(f.replaceFirst('android.hardware.', ''), style: const TextStyle(fontSize: 11)),
                    selected: profile.features.contains(f),
                    onSelected: (selected) => repo.toggleFeature(f, selected),
                  )).toList(),
            ),
            const SizedBox(height: 16),
            const Text('Supported CPU architectures (ABIs)', style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: kKnownAbis.map((a) => FilterChip(
                    label: Text(a, style: const TextStyle(fontSize: 11)),
                    selected: profile.abis.contains(a),
                    onSelected: (selected) => repo.toggleAbi(a, selected),
                  )).toList(),
            ),
          ],
        ),
      ),
    );
  }
}
