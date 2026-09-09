import '../models/alternative_app_model.dart';
import '../models/apk_scan_result_model.dart';
import '../models/application_summary.dart';
import '../models/compatibility_model.dart';
import '../models/device_profile_model.dart';
import '../models/security_assessment_model.dart';
import '../services/apps_api_service.dart';

/// Repository layer over AppsApiService (Part 1). Today this is a thin
/// pass-through - there's no local caching/derived state yet - but it's
/// kept as its own layer (rather than screens calling AppsApiService
/// directly) so that can be added later without moving call sites in
/// every screen, and so tests can mock this one seam.
class AppsRepository {
  final AppsApiService _api;

  AppsRepository(this._api);

  Future<List<ApplicationSummary>> search(String query) => _api.search(query);

  Future<ApplicationSummary> getApplication(int id) => _api.getApplication(id);

  Future<SecurityAssessment> getSecurity(int id) => _api.getSecurity(id);

  Future<CompatibilityResponse> checkCompatibility(int id, DeviceProfileModel device) =>
      _api.checkCompatibility(id, device);

  Future<(bool, List<AlternativeApp>)> getAlternatives(int id) => _api.getAlternatives(id);

  Future<ApkScanResult> uploadApk(List<int> bytes, String filename) => _api.uploadApk(bytes, filename);
}
