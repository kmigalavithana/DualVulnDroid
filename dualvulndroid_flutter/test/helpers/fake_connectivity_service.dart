import 'package:dualvulndroid_flutter/models/device_profile_model.dart';
import 'package:dualvulndroid_flutter/services/connectivity_service.dart';

/// A ConnectivityService that never touches a real platform channel and
/// resolves synchronously - see FakeDeviceInfoService's doc comment for
/// why widget tests need this.
class FakeConnectivityService implements ConnectivityService {
  final ConnectivityStatus status;
  const FakeConnectivityService({this.status = ConnectivityStatus.wifi});

  @override
  Future<ConnectivityStatus> readStatus() async => status;
}
