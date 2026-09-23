import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;

/// Central place for SmartApp's own backend base URL - nothing else in
/// this app should hard-code an http:// address, and NOTHING in this app
/// ever talks to SerpApi (or any third-party Google Play data provider)
/// directly. Flutter/Android networking rules force different loopback
/// addresses depending on where the app is actually running:
///   - Android emulator: the emulator's own loopback is a separate VM,
///     so 127.0.0.1 there means the emulator itself, not the host
///     machine. Android's documented fixed alias for the host's
///     127.0.0.1 is 10.0.2.2.
///   - iOS simulator / desktop / web running on the same machine as the
///     backend: 127.0.0.1 works directly, since there's no separate VM.
///   - A physical device on the same LAN: neither loopback address
///     reaches the host - this must be the host machine's real LAN IP,
///     which is inherently environment-specific and can't be guessed, so
///     it's the one value that must be supplied explicitly below.
class ApiConfig {
  ApiConfig._();

  /// Set this to your host machine's LAN IP (e.g. "192.168.1.23") to run
  /// against a physical device. Left null, the platform-appropriate
  /// loopback address is used instead (emulator/simulator/desktop/web).
  static String? physicalDeviceHost;

  static const int _port = 8000;

  /// The resolved backend base URL for the current platform - the
  /// existing DualVulnDroid FastAPI backend (backend/app.py), which
  /// mounts SmartApp's own isolated routes under /smartapp/*.
  static String get baseUrl {
    if (physicalDeviceHost != null && physicalDeviceHost!.isNotEmpty) {
      return 'http://$physicalDeviceHost:$_port';
    }
    if (kIsWeb) {
      return 'http://127.0.0.1:$_port';
    }
    if (Platform.isAndroid) {
      // Real Android-emulator-only alias, not a LAN address.
      return 'http://10.0.2.2:$_port';
    }
    return 'http://127.0.0.1:$_port';
  }

  static const Duration requestTimeout = Duration(seconds: 20);
}
