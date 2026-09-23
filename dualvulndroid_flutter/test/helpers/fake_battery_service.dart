import 'package:dualvulndroid_flutter/services/battery_service.dart';

/// A BatteryService that never touches a real platform channel and
/// resolves synchronously - see FakeDeviceInfoService's doc comment for
/// why widget tests need this (an unfaked real service's platform call
/// would otherwise leave a pending timer/animate a loading spinner
/// forever within a single `pumpAndSettle()`).
class FakeBatteryService implements BatteryService {
  final int? level;
  const FakeBatteryService({this.level = 80});

  @override
  Future<int?> readLevel() async => level;
}
