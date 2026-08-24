/// One turn in the security chat (Part 17). The "reply" text always
/// comes straight from the backend's /ai-chat response - this app never
/// generates or edits chatbot text itself.
class ChatMessage {
  final String text;
  final bool fromUser;
  final DateTime sentAt;

  ChatMessage({required this.text, required this.fromUser, DateTime? sentAt}) : sentAt = sentAt ?? DateTime.now();
}
