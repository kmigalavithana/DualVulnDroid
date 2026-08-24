/// The user's device profile for POST /apps/{id}/compatibility (Phase 9,
/// Part 13). Deliberately has NO ram field - the backend never uses RAM
/// as a compatibility signal (Part E/8C: "do not use RAM as a
/// compatibility signal"), so asking for it would just be theater.
///
/// androidVersion/abis may be pre-filled from a real platform API
/// (device_info_plus's Build.VERSION.SDK_INT / Build.SUPPORTED_ABIS) on
/// an actual Android device - see DeviceProfileRepository. features is
/// never auto-detected (no reliable, simple platform API surfaces
/// PackageManager.hasSystemFeature() results), so it's always manually
/// entered by the user; the app is honest about that distinction in the
/// UI rather than pretending it detected hardware capabilities it
/// didn't.
class DeviceProfileModel {
  final int? androidVersion;
  final List<String> features;
  final List<String> abis;

  const DeviceProfileModel({
    this.androidVersion,
    this.features = const [],
    this.abis = const [],
  });

  DeviceProfileModel copyWith({int? androidVersion, List<String>? features, List<String>? abis}) {
    return DeviceProfileModel(
      androidVersion: androidVersion ?? this.androidVersion,
      features: features ?? this.features,
      abis: abis ?? this.abis,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      if (androidVersion != null) 'androidVersion': androidVersion,
      if (features.isNotEmpty) 'features': features,
      if (abis.isNotEmpty) 'abis': abis,
    };
  }
}

/// A curated, non-exhaustive list of well-known android.hardware.*
/// feature strings for the manual-entry checklist (Part 13/12). This is
/// UI convenience only - it is not claimed to be device-detected, and
/// the user can still type any other feature name manually.
const List<String> kCommonHardwareFeatures = [
  'android.hardware.camera',
  'android.hardware.camera.autofocus',
  'android.hardware.location.gps',
  'android.hardware.bluetooth',
  'android.hardware.bluetooth_le',
  'android.hardware.telephony',
  'android.hardware.wifi',
  'android.hardware.nfc',
  'android.hardware.sensor.accelerometer',
  'android.hardware.sensor.gyroscope',
  'android.hardware.fingerprint',
];

/// The real, standard Android ABI names (matches apk_scanner.py's
/// _KNOWN_ABIS on the backend) for the manual/detected ABI checklist.
const List<String> kKnownAbis = [
  'arm64-v8a',
  'armeabi-v7a',
  'armeabi',
  'x86',
  'x86_64',
];
