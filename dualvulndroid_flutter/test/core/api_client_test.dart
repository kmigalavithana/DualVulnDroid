import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/core/api_exceptions.dart';

void main() {
  group('ApiClient', () {
    // 17. Network error
    test('a connection failure becomes a NetworkException, never a raw exception', () async {
      final client = ApiClient(client: MockClient((request) async {
        throw const SocketException('Connection refused');
      }));

      await expectLater(client.get('/apps/search', query: {'q': 'x'}), throwsA(isA<NetworkException>()));
    });

    // 16. 401 handling, at the client layer
    test('a 401 response becomes an UnauthorizedException carrying the real backend message', () async {
      final client = ApiClient(client: MockClient((request) async {
        return http.Response('{"detail": "Invalid email or password."}', 401);
      }));

      await expectLater(
        client.post('/login', body: {'email': 'a@b.com', 'password': 'wrong'}),
        throwsA(isA<UnauthorizedException>().having((e) => e.message, 'message', 'Invalid email or password.')),
      );
    });

    test('a 404 response becomes a NotFoundException', () async {
      final client = ApiClient(client: MockClient((request) async {
        return http.Response('{"detail": "No application with id 999."}', 404);
      }));

      await expectLater(client.get('/apps/999'), throwsA(isA<NotFoundException>()));
    });

    test('a 500 response becomes a ServerException, not a leaked stack trace', () async {
      final client = ApiClient(client: MockClient((request) async {
        return http.Response('Internal Server Error', 500);
      }));

      await expectLater(client.get('/apps/search', query: {'q': 'x'}), throwsA(isA<ServerException>()));
    });

    test('a successful GET attaches the Authorization header when a token is available', () async {
      String? seenAuthHeader;
      final client = ApiClient(
        client: MockClient((request) async {
          seenAuthHeader = request.headers['Authorization'];
          return http.Response('{"history": []}', 200);
        }),
        tokenProvider: () async => 'real-jwt-token',
      );

      await client.get('/user/history');

      expect(seenAuthHeader, 'Bearer real-jwt-token');
    });
  });
}
