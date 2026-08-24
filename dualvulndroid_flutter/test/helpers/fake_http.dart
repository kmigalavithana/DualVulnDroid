import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// A tiny routed fake backend for tests (Part 22: "Do not depend on a
/// live backend for unit/widget tests"). Each test registers exact
/// method+path matches with a canned status/body; anything unmatched
/// returns 404 so a test can't accidentally "pass" against a request it
/// never intended to make.
class FakeRoute {
  final String method;
  final String pathPrefix;
  final int status;
  final Object? body;

  const FakeRoute({required this.method, required this.pathPrefix, this.status = 200, this.body});
}

MockClient buildFakeClient(List<FakeRoute> routes) {
  return MockClient((request) async {
    for (final route in routes) {
      if (request.method == route.method && request.url.path == route.pathPrefix) {
        return http.Response(route.body == null ? '' : jsonEncode(route.body), route.status,
            headers: {'content-type': 'application/json'});
      }
    }
    return http.Response(jsonEncode({'detail': 'unmatched fake route: ${request.method} ${request.url.path}'}), 404);
  });
}
