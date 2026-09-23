import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';

import '../models/device_profile_model.dart';

/// Reads the CURRENT device's real profile via `device_info_plus`, which
/// itself reads Android's own `Build`, `ActivityManager.MemoryInfo`, and
/// `StatFs` APIs (Part 6: "Do not ask the user to manually enter these
/// values if they can be obtained automatically" / "If a value cannot
/// reliably be obtained, display Unavailable rather than inventing it").
///
/// Never throws: any platform-channel failure (non-Android platform, or
/// the call genuinely failing on-device) is caught and simply leaves the
/// corresponding field(s) `null`, which the UI renders as "Unavailable".
class DeviceInfoService {
  final DeviceInfoPlugin _plugin;

  DeviceInfoService({DeviceInfoPlugin? plugin}) : _plugin = plugin ?? DeviceInfoPlugin();

  Future<DeviceProfileModel> readProfile() async {
    if (kIsWeb) return const DeviceProfileModel();
    try {
      final info = await _plugin.androidInfo;
      return DeviceProfileModel(
        androidSdkInt: info.version.sdkInt,
        androidRelease: info.version.release,
        ramTotalMb: info.physicalRamSize > 0 ? info.physicalRamSize : null,
        ramAvailableMb: info.availableRamSize > 0 ? info.availableRamSize : null,
        isLowRamDevice: info.isLowRamDevice,
        storageTotalBytes: info.totalDiskSize > 0 ? info.totalDiskSize : null,
        storageFreeBytes: info.freeDiskSize > 0 ? info.freeDiskSize : null,
        abis: info.supportedAbis,
        manufacturer: info.manufacturer.isNotEmpty ? info.manufacturer : null,
        model: info.model.isNotEmpty ? info.model : null,
      );
    } catch (_) {
      // Not running on Android, or the platform call failed - an empty
      // profile (every field null/"Unavailable") is the honest result,
      // never a fabricated fallback.
      return const DeviceProfileModel();
    }
  }
}
