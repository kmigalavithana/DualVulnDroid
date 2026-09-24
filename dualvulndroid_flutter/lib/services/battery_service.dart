import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/foundation.dart';

/// Reads the device's real, current battery charge via `battery_plus`
/// (itself backed by Android's `BatteryManager`). Never throws and never
/// guesses: an unsupported platform or a failed platform call yields
/// `null`, which the UI/engine must treat as "unavailable", not as a full
/// or empty battery.
class BatteryService {
  final Battery _battery;

  BatteryService({Battery? battery}) : _battery = battery ?? Battery();

  Future<int?> readLevel() async {
    if (kIsWeb) return null;
    try {
      // Bounded so an unresponsive/unregistered platform channel (e.g. no
      // battery plugin implementation available) degrades to "unavailable"
      // rather than blocking device-context detection indefinitely.
      final level = await _battery.batteryLevel.timeout(const Duration(seconds: 3));
      return (level >= 0 && level <= 100) ? level : null;
    } catch (_) {
      return null;
    }
  }
}
