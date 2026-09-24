/// The device's real, OS-reported network reachability at the moment it
/// was last read (`connectivity_plus`, backed by Android's own
/// `ConnectivityManager`) - not a measurement of internet quality/speed,
/// only whether a transport is currently attached. [unavailable] is the
/// honest state when the platform call itself could not be made (e.g.
/// running on an unsupported platform), distinct from [offline] (the
/// platform was asked and reported no active transport).
enum ConnectivityStatus {
  wifi,
  mobileData,
  offline,
  unavailable;

  String get label => switch (this) {
        ConnectivityStatus.wifi => 'Wi-Fi',
        ConnectivityStatus.mobileData => 'Mobile data',
        ConnectivityStatus.offline => 'Offline',
        ConnectivityStatus.unavailable => 'Unavailable',
      };
}

/// The current device's real, platform-reported hardware/OS/runtime
/// profile - this doubles as SmartApp's "device context" (RAM, Android
/// version, storage, CPU ABIs, connectivity, battery) used both by the
/// Home "MY DEVICE" card / "My Device" screen AND by
/// [RecommendationEngine]/[ContextEngine] for device-aware scoring. Every
/// field is either a genuine value read from a real platform API
/// (`device_info_plus`, `battery_plus`, `connectivity_plus`) or `null`.
/// Nothing here is ever guessed, estimated, or hardcoded - a `null` field
/// means "unavailable" and the UI must show that honestly rather than
/// inventing a placeholder value.
class DeviceProfileModel {
  /// Android's own SDK level (`Build.VERSION.SDK_INT`), e.g. 34.
  final int? androidSdkInt;

  /// The human-readable Android version string (`Build.VERSION.RELEASE`),
  /// e.g. "14".
  final String? androidRelease;

  /// Total physical RAM, in megabytes (`ActivityManager.MemoryInfo.totalMem`).
  final int? ramTotalMb;

  /// Currently unallocated RAM, in megabytes (`ActivityManager.MemoryInfo.availMem`).
  final int? ramAvailableMb;

  /// `true` if Android itself classifies this as a low-RAM device
  /// (`ActivityManager.isLowRamDevice()`) - a real platform signal, not a
  /// threshold this app invented.
  final bool? isLowRamDevice;

  /// Total internal storage, in bytes (`StatFs#getTotalBytes()`).
  final int? storageTotalBytes;

  /// Free internal storage, in bytes (`StatFs#getFreeBytes()`).
  final int? storageFreeBytes;

  /// Supported CPU ABIs (`Build.SUPPORTED_ABIS`), e.g. `[arm64-v8a]`.
  final List<String> abis;

  final String? manufacturer;
  final String? model;

  /// Battery charge, 0-100 (`battery_plus`, reading Android's own
  /// `BatteryManager`). `null` when unavailable rather than assumed full.
  final int? batteryLevel;

  /// Real-time network reachability (`connectivity_plus`). Always
  /// [ConnectivityStatus.unavailable] rather than a guess when the
  /// platform call itself fails.
  final ConnectivityStatus connectivityStatus;

  const DeviceProfileModel({
    this.androidSdkInt,
    this.androidRelease,
    this.ramTotalMb,
    this.ramAvailableMb,
    this.isLowRamDevice,
    this.storageTotalBytes,
    this.storageFreeBytes,
    this.abis = const [],
    this.manufacturer,
    this.model,
    this.batteryLevel,
    this.connectivityStatus = ConnectivityStatus.unavailable,
  });

  bool get hasAnyData =>
      androidSdkInt != null || ramTotalMb != null || storageTotalBytes != null;

  /// A short, honest resource-capability label derived only from real
  /// signals actually available (RAM + Android's own low-RAM flag). This
  /// is descriptive framing, not a performance benchmark or a claim about
  /// real-world app speed (see resourceScore in RecommendationEngine for
  /// where this label's underlying numbers are actually used for
  /// scoring).
  String get resourceProfileLabel {
    if (isLowRamDevice == true) return 'Constrained Resource Device';
    final ram = ramTotalMb;
    if (ram == null) return 'Unknown Resource Profile';
    if (ram >= 6144) return 'High-End Resource Device';
    if (ram >= 3072) return 'Moderate Resource Device';
    return 'Constrained Resource Device';
  }

  DeviceProfileModel copyWith({
    int? androidSdkInt,
    String? androidRelease,
    int? ramTotalMb,
    int? ramAvailableMb,
    bool? isLowRamDevice,
    int? storageTotalBytes,
    int? storageFreeBytes,
    List<String>? abis,
    String? manufacturer,
    String? model,
    int? batteryLevel,
    ConnectivityStatus? connectivityStatus,
  }) {
    return DeviceProfileModel(
      androidSdkInt: androidSdkInt ?? this.androidSdkInt,
      androidRelease: androidRelease ?? this.androidRelease,
      ramTotalMb: ramTotalMb ?? this.ramTotalMb,
      ramAvailableMb: ramAvailableMb ?? this.ramAvailableMb,
      isLowRamDevice: isLowRamDevice ?? this.isLowRamDevice,
      storageTotalBytes: storageTotalBytes ?? this.storageTotalBytes,
      storageFreeBytes: storageFreeBytes ?? this.storageFreeBytes,
      abis: abis ?? this.abis,
      manufacturer: manufacturer ?? this.manufacturer,
      model: model ?? this.model,
      batteryLevel: batteryLevel ?? this.batteryLevel,
      connectivityStatus: connectivityStatus ?? this.connectivityStatus,
    );
  }
}
