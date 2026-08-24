import 'dart:async';
import 'dart:convert';
import 'dart:io' show SocketException;

import 'package:http/http.dart' as http;

import 'api_config.dart';
import 'api_exceptions.dart';

/// Centralized HTTP client (Phase 9, Part 4). Every backend call in this
/// app goes through here - no widget or screen ever calls `http.*`
/// directly (Part 1). Automatically attaches an `Authorization: Bearer`
/// JWT header when a token is available, and translates every failure mode
/// into one of the typed exceptions in api_exceptions.dart, so nothing
/// above this layer ever sees a raw status code or stack trace.
///
/// The underlying http.Client and the token supplier are both injected,
/// so tests can substitute http.testing.MockClient and a fake token
/// provider without touching real network/storage (Part 22: "do not
/// depend on a live backend for unit/widget tests").
class ApiClient {
  final http.Client _client;
  final Future<String?> Function() _tokenProvider;

  ApiClient({
    http.Client? client,
    Future<String?> Function()? tokenProvider,
  })  : _client = client ?? http.Client(),
        _tokenProvider = tokenProvider ?? (() async => null);

  Future<Map<String, String>> _headers({bool json = true}) async {
    final headers = <String, String>{};
    if (json) headers['Content-Type'] = 'application/json';
    final token = await _tokenProvider();
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) {
    final base = Uri.parse(ApiConfig.baseUrl + path);
    if (query == null || query.isEmpty) return base;
    return base.replace(queryParameters: {
      ...base.queryParameters,
      for (final entry in query.entries)
        if (entry.value != null) entry.key: entry.value.toString(),
    });
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async {
    final headers = await _headers(json: false);
    return _send(() => _client.get(_uri(path, query), headers: headers).timeout(ApiConfig.requestTimeout));
  }

  Future<dynamic> post(String path, {Map<String, dynamic>? body}) async {
    final headers = await _headers();
    return _send(() => _client
        .post(_uri(path), headers: headers, body: body == null ? null : jsonEncode(body))
        .timeout(ApiConfig.requestTimeout));
  }

  Future<dynamic> _send(Future<http.Response> Function() request) async {
    http.Response response;
    try {
      response = await request();
    } on TimeoutException {
      throw const NetworkException();
    } on SocketException {
      throw const NetworkException();
    } on http.ClientException {
      throw const NetworkException();
    }

    final status = response.statusCode;
    dynamic decoded;
    try {
      decoded = response.body.isEmpty ? null : jsonDecode(response.body);
    } catch (_) {
      decoded = null;
    }

    if (status == 200 || status == 201) {
      return decoded;
    }

    final serverMessage = (decoded is Map && decoded['detail'] is String) ? decoded['detail'] as String : null;

    switch (status) {
      case 401:
        throw UnauthorizedException(serverMessage ?? 'Your session has expired. Please log in again.');
      case 404:
        throw NotFoundException(serverMessage ?? 'The requested item could not be found.');
      case 400:
      case 422:
        throw ValidationException(serverMessage ?? 'The request could not be processed.');
      default:
        throw const ServerException();
    }
  }
}
