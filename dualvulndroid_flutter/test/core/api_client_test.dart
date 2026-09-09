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

    // Flutter APK Scan implementation phase: multipart upload support.
    test('a 413 response becomes a PayloadTooLargeException carrying the real backend message', () async {
      final client = ApiClient(client: MockClient((request) async {
        return http.Response('{"detail": "APK exceeds the 100MB upload limit."}', 413);
      }));

      await expectLater(
        client.postMultipartFile('/upload-apk', bytes: [1, 2, 3], filename: 'x.apk', fileField: 'file'),
        throwsA(isA<PayloadTooLargeException>().having((e) => e.message, 'message', 'APK exceeds the 100MB upload limit.')),
      );
    });

    test('postMultipartFile sends the real file bytes and filename as multipart form data', () async {
      String? seenFilename;
      List<int>? seenBytes;
      final client = ApiClient(client: MockClient.streaming((request, bodyStream) async {
        final multipart = request as http.MultipartRequest;
        final file = multipart.files.single;
        seenFilename = file.filename;
        seenBytes = await file.finalize().toBytes();
        return http.StreamedResponse(Stream.value('{"scan_id": 1}'.codeUnits), 200);
      }));

      final result = await client.postMultipartFile(
        '/upload-apk',
        bytes: [10, 20, 30],
        filename: 'MyApp.apk',
        fileField: 'file',
      );

      expect(seenFilename, 'MyApp.apk');
      expect(seenBytes, [10, 20, 30]);
      expect(result, {'scan_id': 1});
    });
  });
}
