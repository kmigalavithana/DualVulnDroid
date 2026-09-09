import '../core/api_client.dart';
import '../models/alternative_app_model.dart';
import '../models/apk_scan_result_model.dart';
import '../models/application_summary.dart';
import '../models/compatibility_model.dart';
import '../models/device_profile_model.dart';
import '../models/security_assessment_model.dart';

/// Thin wrapper around the real /apps/* endpoints. Every method returns
/// parsed models built only from what the backend actually sent - no
/// method here invents a field, a default risk level, or a fake
/// candidate (Phase 7-8C's "never fabricate" rule, carried through to
/// the client).
class AppsApiService {
  final ApiClient _client;

  AppsApiService(this._client);

  Future<List<ApplicationSummary>> search(String query) async {
    final json = await _client.get('/apps/search', query: {'q': query}) as Map<String, dynamic>;
    final results = json['results'] as List<dynamic>? ?? const [];
    return results.map((r) => ApplicationSummary.fromSearchJson(r as Map<String, dynamic>)).toList();
  }

  Future<ApplicationSummary> getApplication(int id) async {
    final json = await _client.get('/apps/$id') as Map<String, dynamic>;
    return ApplicationSummary.fromDetailJson(json);
  }

  Future<SecurityAssessment> getSecurity(int id) async {
    final json = await _client.get('/apps/$id/security') as Map<String, dynamic>;
    return SecurityAssessment.fromJson(json);
  }

  Future<CompatibilityResponse> checkCompatibility(int id, DeviceProfileModel device) async {
    final json = await _client.post('/apps/$id/compatibility', body: device.toJson()) as Map<String, dynamic>;
    return CompatibilityResponse.fromJson(json);
  }

  /// Returns (available, alternatives) - matches
  /// {"available": bool, "alternatives": [...]}.
  Future<(bool, List<AlternativeApp>)> getAlternatives(int id) async {
    final json = await _client.get('/apps/$id/alternatives') as Map<String, dynamic>;
    final available = json['available'] as bool? ?? false;
    final list = (json['alternatives'] as List<dynamic>? ?? const [])
        .map((a) => AlternativeApp.fromJson(a as Map<String, dynamic>))
        .toList();
    return (available, list);
  }

  /// Uploads a real APK for direct analysis (POST /upload-apk) - the
  /// backend both persists the scan and returns the full result in one
  /// response, so no follow-up GET is needed to display it.
  Future<ApkScanResult> uploadApk(List<int> bytes, String filename) async {
    final json = await _client.postMultipartFile(
      '/upload-apk',
      bytes: bytes,
      filename: filename,
      fileField: 'file',
    ) as Map<String, dynamic>;
    return ApkScanResult.fromJson(json);
  }
}
