import 'package:flutter/foundation.dart';

import '../models/device_profile_model.dart';
import '../services/battery_service.dart';
import '../services/connectivity_service.dart';
import '../services/device_info_service.dart';

/// Holds the current device's real profile for the app's lifetime (Home's
/// device status card + the "My Device" screen + the recommendation
/// engine's context-aware adjustments all read this same instance, so
/// they can never disagree). Detection is attempted once, automatically,
/// on construction - the user is never asked to type in values the
/// platform can report itself (Part 6).
///
/// Composes three independent, single-purpose services (hardware/OS,
/// battery, connectivity) into one [DeviceProfileModel] snapshot rather
/// than duplicating any of their platform-channel logic here.
class DeviceProfileRepository extends ChangeNotifier {
  final DeviceInfoService _service;
  final BatteryService _batteryService;
  final ConnectivityService _connectivityService;

  DeviceProfileModel _profile = const DeviceProfileModel();
  bool _loading = true;

  DeviceProfileRepository({
    DeviceInfoService? service,
    BatteryService? batteryService,
    ConnectivityService? connectivityService,
  })  : _service = service ?? DeviceInfoService(),
        _batteryService = batteryService ?? BatteryService(),
        _connectivityService = connectivityService ?? ConnectivityService() {
    _detect();
  }

  DeviceProfileModel get profile => _profile;
  bool get isLoading => _loading;

  Future<void> _detect() async {
    _loading = true;
    notifyListeners();
    // Each service never throws - a failed/unsupported platform simply
    // yields a null/"unavailable" value for that one signal, rendered
    // honestly by the UI rather than crashing this repository or
    // inventing a fallback.
    final results = await Future.wait([
      _service.readProfile(),
      _batteryService.readLevel(),
      _connectivityService.readStatus(),
    ]);
    final hardware = results[0] as DeviceProfileModel;
    final batteryLevel = results[1] as int?;
    final connectivityStatus = results[2] as ConnectivityStatus;
    _profile = hardware.copyWith(batteryLevel: batteryLevel, connectivityStatus: connectivityStatus);
    _loading = false;
    notifyListeners();
  }

  Future<void> refresh() => _detect();
}
