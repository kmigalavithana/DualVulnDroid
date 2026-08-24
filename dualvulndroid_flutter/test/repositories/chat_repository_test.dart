import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:dualvulndroid_flutter/core/api_client.dart';
import 'package:dualvulndroid_flutter/models/application_summary.dart';
import 'package:dualvulndroid_flutter/repositories/chat_repository.dart';
import 'package:dualvulndroid_flutter/services/chat_api_service.dart';

import '../helpers/fake_http.dart';

/// Captures the last request this fake backend received, so tests can
/// assert on the real JSON body sent to /ai-chat - not just the reply
/// coming back. This is what proves the old bug (Part 12: a prior
/// version of ChatRepository silently mangled the user's message with
/// unparseable free-text app context) is actually fixed, rather than
/// just no longer throwing.
class _CapturingClient {
  Map<String, dynamic>? lastBody;

  MockClient build(Map<String, dynamic> replyBody) {
    return MockClient((request) async {
      lastBody = jsonDecode(request.body) as Map<String, dynamic>;
      return http.Response(jsonEncode(replyBody), 200, headers: {'content-type': 'application/json'});
    });
  }
}

void main() {
  group('ChatRepository', () {
    test('sends the user message unmodified, with no app selected', () async {
      final capture = _CapturingClient();
      final repo = ChatRepository(ChatApiService(ApiClient(client: capture.build({'reply': 'hi'}))));

      final reply = await repo.sendMessage('What is CWE-89?', userId: 5);

      expect(reply, 'hi');
      expect(capture.lastBody!['message'], 'What is CWE-89?');
      expect(capture.lastBody!.containsKey('app_id'), isFalse);
      expect(capture.lastBody!['user_id'], 5);
    });

    test('sends the real app_id when an application is selected, message untouched', () async {
      final capture = _CapturingClient();
      final repo = ChatRepository(ChatApiService(ApiClient(client: capture.build({'reply': 'It is flagged HIGH risk.'}))));

      const app = ApplicationSummary(id: 42, appName: 'RiskyBank', packageName: 'com.example.riskybank');
      final reply = await repo.sendMessage('Why is this app risky?', selectedApplication: app);

      expect(reply, 'It is flagged HIGH risk.');
      // The message itself is never rewritten with app facts client-side -
      // the backend resolves app_id to its own real, current data.
      expect(capture.lastBody!['message'], 'Why is this app risky?');
      expect(capture.lastBody!['app_id'], 42);
    });

    test('forwards androidVersion when supplied', () async {
      final capture = _CapturingClient();
      final repo = ChatRepository(ChatApiService(ApiClient(client: capture.build({'reply': 'ok'}))));

      await repo.sendMessage('hello', androidVersion: 30);

      expect(capture.lastBody!['user_android_version'], 30);
    });

    test('an empty backend reply field returns an empty string, never null/crash', () async {
      final capture = _CapturingClient();
      final repo = ChatRepository(ChatApiService(ApiClient(client: capture.build({}))));

      final reply = await repo.sendMessage('hello');

      expect(reply, '');
    });

    // Phase 14C: the read side of chat history (GET /user/chat-history).
    test('getHistory() expands each real {question, answer} row into two ordered messages', () async {
      final repo = ChatRepository(ChatApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'GET', pathPrefix: '/user/chat-history', body: {
          'history': [
            {'id': 1, 'question': 'What is CWE-89?', 'answer': 'CWE-89 is SQL Injection.', 'created_at': '2026-01-01T10:00:00'},
            {'id': 2, 'question': 'What is CWE-295?', 'answer': 'CWE-295 is Improper Certificate Validation.', 'created_at': '2026-01-01T10:01:00'},
          ],
        }),
      ]))));

      final messages = await repo.getHistory();

      expect(messages, hasLength(4));
      expect(messages[0].fromUser, isTrue);
      expect(messages[0].text, 'What is CWE-89?');
      expect(messages[1].fromUser, isFalse);
      expect(messages[1].text, 'CWE-89 is SQL Injection.');
      expect(messages[2].fromUser, isTrue);
      expect(messages[2].text, 'What is CWE-295?');
      expect(messages[3].fromUser, isFalse);
      expect(messages[3].text, 'CWE-295 is Improper Certificate Validation.');
    });

    test('getHistory() on an empty history returns an empty list, not an error', () async {
      final repo = ChatRepository(ChatApiService(ApiClient(client: buildFakeClient([
        FakeRoute(method: 'GET', pathPrefix: '/user/chat-history', body: {'history': []}),
      ]))));

      final messages = await repo.getHistory();

      expect(messages, isEmpty);
    });
  });
}
