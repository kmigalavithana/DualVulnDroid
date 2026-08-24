import 'package:flutter/foundation.dart';
import 'package:device_info_plus/device_info_plus.dart';

import '../models/device_profile_model.dart';

/// Holds the user's device profile for the current session (Part 13).
/// Held in memory only, scoped to the app's lifetime - this phase does
/// not add persistent local storage for it (no strong requirement for
/// it to survive an app restart yet, and adding a storage dependency
/// for that is left for a later phase rather than done speculatively).
///
/// androidVersion/abis MAY be pre-filled from a real platform API
/// (device_info_plus's Build.VERSION.SDK_INT / Build.SUPPORTED_ABIS) on
/// an actual Android device - both are genuine values the OS reports,
/// never guessed. features is NEVER auto-detected: there is no simple,
/// reliable Flutter API surfacing PackageManager.hasSystemFeature()
/// results, so auto-filling it would mean guessing, which Part 13
/// explicitly forbids ("Do not guess unsupported feature information").
/// The user always CAN edit every field manually regardless of whether
/// auto-detection ran.
class DeviceProfileRepository extends ChangeNotifier {
  DeviceProfileModel _profile = const DeviceProfileModel();
  bool _autoDetected = false;

  final DeviceInfoPlugin _deviceInfo;

  DeviceProfileRepository({DeviceInfoPlugin? deviceInfo}) : _deviceInfo = deviceInfo ?? DeviceInfoPlugin();

  DeviceProfileModel get profile => _profile;
  bool get wasAutoDetected => _autoDetected;

  /// Attempts real device detection. Silently does nothing (leaves the
  /// profile exactly as it was) if not running on a real Android device,
  /// or if the plugin call fails for any reason - never falls back to a
  /// fabricated value.
  Future<void> tryAutoDetect() async {
    if (kIsWeb) return;
    try {
      final androidInfo = await _deviceInfo.androidInfo;
      _profile = _profile.copyWith(
        androidVersion: androidInfo.version.sdkInt,
        abis: androidInfo.supportedAbis,
      );
      _autoDetected = true;
      notifyListeners();
    } catch (_) {
      // Not an Android device, or the platform channel isn't available
      // (e.g. running as a desktop/web build) - leave the profile as-is
      // rather than guessing.
    }
  }

  void updateAndroidVersion(int? version) {
    _profile = _profile.copyWith(androidVersion: version);
    notifyListeners();
  }

  void toggleFeature(String feature, bool enabled) {
    final updated = List<String>.from(_profile.features);
    if (enabled && !updated.contains(feature)) {
      updated.add(feature);
    } else if (!enabled) {
      updated.remove(feature);
    }
    _profile = _profile.copyWith(features: updated);
    notifyListeners();
  }

  void toggleAbi(String abi, bool enabled) {
    final updated = List<String>.from(_profile.abis);
    if (enabled && !updated.contains(abi)) {
      updated.add(abi);
    } else if (!enabled) {
      updated.remove(abi);
    }
    _profile = _profile.copyWith(abis: updated);
    notifyListeners();
  }
}
