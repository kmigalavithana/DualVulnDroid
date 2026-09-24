import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/services/device_info_service.dart';

/// A DeviceInfoService that never touches a real platform channel -
/// widget tests run with no device_info_plus platform implementation
/// registered, so the real service's plugin call would otherwise hang
/// indefinitely (an unresolved Future keeps DeviceProfileRepository's
/// loading spinner animating forever, which makes `pumpAndSettle()`
/// time out). Returns a fixed, realistic profile synchronously instead.
class FakeDeviceInfoService implements DeviceInfoService {
  final DeviceProfileModel profile;
  const FakeDeviceInfoService({
    this.profile = const DeviceProfileModel(
      androidSdkInt: 34,
      androidRelease: '14',
      ramTotalMb: 6144,
      ramAvailableMb: 2048,
      isLowRamDevice: false,
      storageTotalBytes: 64000000000,
      storageFreeBytes: 16000000000,
      abis: ['arm64-v8a'],
      manufacturer: 'Google',
      model: 'Pixel Test',
    ),
  });

  @override
  Future<DeviceProfileModel> readProfile() async => profile;
}
