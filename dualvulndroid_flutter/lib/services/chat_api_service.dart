import '../core/api_client.dart';
import '../models/chat_message_model.dart';

/// Wraps the existing /ai-chat endpoint (Part 17: "Do NOT build a new ML
/// chatbot model. Use the existing /chat, /ai-chat"). This app never
/// generates or edits the reply text - whatever the backend returns is
/// shown verbatim.
///
/// /ai-chat's request model (backend/app.py's ChatMessage) also accepts
/// user_ram_mb/user_android_version with server-side defaults (2048MB /
/// Android 10) from a pre-Phase-8 version of this project. This client
/// never fabricates a RAM value to send (Part 12: RAM is never requested
/// from the user), so those fields are simply omitted here and the
/// backend's own existing defaults apply unchanged - not a backend
/// behavior change, just not supplying a value this app was never asked
/// to collect.
class ChatApiService {
  final ApiClient _client;

  ChatApiService(this._client);

  /// [appId] is the real, already-fetched application id (Part 12): when
  /// the chat was opened from an app's details screen, the backend can
  /// look up that app's REAL current assessment by id instead of the
  /// client trying to guess/restate app facts in free text.
  Future<String> sendMessage(String message, {int? userId, int? androidVersion, int? appId}) async {
    final json = await _client.post('/ai-chat', body: {
      'message': message,
      if (userId != null) 'user_id': userId,
      if (androidVersion != null) 'user_android_version': androidVersion,
      if (appId != null) 'app_id': appId,
    }) as Map<String, dynamic>;
    return json['reply'] as String? ?? '';
  }

  /// GET /user/chat-history (Phase 14C) - JWT-derived, always only the
  /// authenticated user's own messages (same security pattern as
  /// HistoryApiService.getHistory(); the backend never trusts a
  /// client-supplied user id here - see app.py's get_current_user
  /// dependency). Each stored {question, answer} row expands into two
  /// real ChatMessage turns, in the same chronological order the backend
  /// already returns.
  Future<List<ChatMessage>> getHistory() async {
    final json = await _client.get('/user/chat-history') as Map<String, dynamic>;
    final rows = json['history'] as List<dynamic>? ?? const [];
    final messages = <ChatMessage>[];
    for (final row in rows) {
      final map = row as Map<String, dynamic>;
      final sentAt = map['created_at'] != null ? DateTime.tryParse(map['created_at'] as String) : null;
      messages.add(ChatMessage(text: map['question'] as String? ?? '', fromUser: true, sentAt: sentAt));
      messages.add(ChatMessage(text: map['answer'] as String? ?? '', fromUser: false, sentAt: sentAt));
    }
    return messages;
  }
}
