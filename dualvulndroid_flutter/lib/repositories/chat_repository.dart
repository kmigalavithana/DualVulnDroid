import '../models/application_summary.dart';
import '../models/chat_message_model.dart';
import '../services/chat_api_service.dart';

/// Forwards the user's message exactly as typed, plus the real, already-
/// fetched application id when the chat was opened from an app's details
/// screen (Part 12: "Context should include the currently selected
/// application when appropriate").
///
/// A prior version of this repository tried to pass app context by
/// prepending free text like 'Regarding the application "X" ...: ' to
/// the message. The backend's intent/app-name parsing could never match
/// that shape, so the context was silently discarded on every message -
/// a real bug. Sending the app's real id instead lets the backend look
/// up its own current, real data (GET /ai-chat now accepts app_id) -
/// this client never restates or invents app facts itself.
class ChatRepository {
  final ChatApiService _api;

  ChatRepository(this._api);

  Future<String> sendMessage(
    String message, {
    int? userId,
    int? androidVersion,
    ApplicationSummary? selectedApplication,
  }) {
    return _api.sendMessage(
      message,
      userId: userId,
      androidVersion: androidVersion,
      appId: selectedApplication?.id,
    );
  }

  /// The authenticated user's own real, previously-persisted chat
  /// history (Phase 14C). Requires a signed-in session - the backend
  /// endpoint itself enforces this via the JWT.
  Future<List<ChatMessage>> getHistory() => _api.getHistory();
}
