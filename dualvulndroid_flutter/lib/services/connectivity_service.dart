import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';

import '../models/device_profile_model.dart';

/// Reads the device's real, current network reachability via
/// `connectivity_plus` (Android's own `ConnectivityManager`) - never an
/// actual network request, only whether a transport is currently
/// attached. Never throws: an unsupported platform or a failed platform
/// call yields [ConnectivityStatus.unavailable], never a guessed state.
class ConnectivityService {
  final Connectivity _connectivity;

  ConnectivityService({Connectivity? connectivity}) : _connectivity = connectivity ?? Connectivity();

  Future<ConnectivityStatus> readStatus() async {
    if (kIsWeb) return ConnectivityStatus.unavailable;
    try {
      // Bounded so an unresponsive/unregistered platform channel degrades
      // to "unavailable" rather than blocking device-context detection
      // indefinitely.
      final results = await _connectivity.checkConnectivity().timeout(const Duration(seconds: 3));
      return _statusFor(results);
    } catch (_) {
      return ConnectivityStatus.unavailable;
    }
  }

  ConnectivityStatus _statusFor(List<ConnectivityResult> results) {
    if (results.contains(ConnectivityResult.wifi) || results.contains(ConnectivityResult.ethernet)) {
      return ConnectivityStatus.wifi;
    }
    if (results.contains(ConnectivityResult.mobile)) {
      return ConnectivityStatus.mobileData;
    }
    if (results.isEmpty || results.every((r) => r == ConnectivityResult.none)) {
      return ConnectivityStatus.offline;
    }
    // Some other recognized transport (vpn/bluetooth/other) is attached -
    // treat as connected without over-claiming a specific transport type.
    return ConnectivityStatus.mobileData;
  }
}
