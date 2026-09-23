import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/app_info_model.dart';
import '../services/api_config.dart';

/// Base type for every real failure calling SmartApp's own backend - a
/// screen must show one of these honestly (Part 7/17), never silently
/// fall back to fake/cached data.
sealed class AppRepositoryException implements Exception {
  final String message;
  const AppRepositoryException(this.message);

  @override
  String toString() => message;
}

/// The backend itself could not be reached, or returned a server-side
/// (5xx) error - including SmartApp's own 502 when the upstream Google
/// Play provider call failed (Part 17: "SmartApp service unavailable.").
class AppServiceUnavailableException extends AppRepositoryException {
  const AppServiceUnavailableException([super.message = 'SmartApp service unavailable.']);
}

/// The backend reached us fine and explicitly said "not found" (404) -
/// e.g. no Google Play app exists for a given package name.
class AppNotFoundException extends AppRepositoryException {
  const AppNotFoundException(super.message);
}

/// Any other non-2xx response (e.g. a malformed request) or a response
/// body that couldn't be parsed.
class AppRequestException extends AppRepositoryException {
  const AppRequestException(super.message);
}

/// SmartApp's real Google Play data access - calls ONLY SmartApp's own
/// backend (GET /smartapp/apps/search, GET /smartapp/apps/details/{id}),
/// never SerpApi or any other third-party provider directly (Part 6/18:
/// the provider API key lives only on the backend). Every [AppInfo]
/// returned here has `isLiveData = true` and `dataSource = "google_play"`
/// - this repository never fabricates a result or falls back to demo
/// data on failure; it throws a typed [AppRepositoryException] instead,
/// which the calling screen must show honestly (loading/error/empty -
/// Part 17).
class AppRepository {
  final http.Client _client;
  final String baseUrl;

  AppRepository({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        baseUrl = baseUrl ?? ApiConfig.baseUrl;

  Future<List<AppInfo>> searchApps({String? query, String? category, int limit = 20}) async {
    final trimmedQuery = query?.trim();
    final params = <String, String>{
      if (trimmedQuery != null && trimmedQuery.isNotEmpty) 'q': trimmedQuery,
      if (category != null && category.isNotEmpty) 'category': category,
      'limit': '$limit',
    };
    final uri = Uri.parse('$baseUrl/smartapp/apps/search').replace(queryParameters: params);
    final body = await _get(uri);
    final rawApps = (body['apps'] as List?) ?? const [];
    return rawApps.whereType<Map<String, dynamic>>().map(AppInfo.fromSmartAppJson).toList();
  }

  /// Returns `null` when the provider genuinely has no such app (a real
  /// 404), never a fabricated placeholder. Any other failure (offline,
  /// backend down, upstream provider error) throws instead, so the
  /// caller can distinguish "confirmed not found" from "couldn't check".
  Future<AppInfo?> getAppDetails(String packageName) async {
    final uri = Uri.parse('$baseUrl/smartapp/apps/details/${Uri.encodeComponent(packageName)}');
    try {
      final body = await _get(uri);
      final raw = body['app'] as Map<String, dynamic>?;
      return raw == null ? null : AppInfo.fromSmartAppJson(raw);
    } on AppNotFoundException {
      return null;
    }
  }

  Future<Map<String, dynamic>> _get(Uri uri) async {
    final http.Response response;
    try {
      response = await _client.get(uri).timeout(ApiConfig.requestTimeout);
    } on TimeoutException {
      throw const AppServiceUnavailableException();
    } catch (e) {
      throw AppServiceUnavailableException('Could not reach SmartApp service: $e');
    }

    if (response.statusCode == 404) {
      throw AppNotFoundException(_detailFrom(response) ?? 'Not found.');
    }
    if (response.statusCode >= 500) {
      throw AppServiceUnavailableException(_detailFrom(response) ?? 'SmartApp service unavailable.');
    }
    if (response.statusCode >= 400) {
      throw AppRequestException(_detailFrom(response) ?? 'Request failed (${response.statusCode}).');
    }

    try {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } catch (_) {
      throw const AppRequestException('Could not parse the SmartApp service response.');
    }
  }

  String? _detailFrom(http.Response response) {
    try {
      final decoded = jsonDecode(response.body);
      if (decoded is Map && decoded['detail'] is String) return decoded['detail'] as String;
    } catch (_) {
      // Non-JSON error body - fall through to the generic message.
    }
    return null;
  }

  void dispose() => _client.close();
}
