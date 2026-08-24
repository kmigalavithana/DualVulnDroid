import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_exceptions.dart';
import '../models/application_summary.dart';
import '../models/chat_message_model.dart';
import '../repositories/auth_repository.dart';
import '../repositories/chat_repository.dart';
import '../theme/app_colors.dart';
import '../widgets/state_views.dart';

/// Phase 9, Part 17. Uses the existing /ai-chat endpoint only - every
/// reply shown here is exactly what the backend returned, never edited
/// or supplemented client-side.
class SecurityChatScreen extends StatefulWidget {
  final ApplicationSummary? selectedApplication;

  const SecurityChatScreen({super.key, this.selectedApplication});

  @override
  State<SecurityChatScreen> createState() => _SecurityChatScreenState();
}

class _SecurityChatScreenState extends State<SecurityChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isSending = false;
  bool _isLoadingHistory = true;

  static const _examples = [
    'Why is this app high risk?',
    'What does CWE-295 mean?',
    "Why can't I install this on my phone?",
    'Is there a safer alternative?',
  ];

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  // Phase 14C: loads the authenticated user's own real, previously-saved
  // chat history so it's actually observable, not just written and
  // forgotten. Never invents a transcript - an unauthenticated user or a
  // failed fetch just leaves the screen at its normal empty-suggestions
  // state, same as before this existed.
  Future<void> _loadHistory() async {
    final userId = context.read<AuthRepository>().currentUser?.id;
    if (userId == null) {
      setState(() => _isLoadingHistory = false);
      return;
    }
    try {
      final history = await context.read<ChatRepository>().getHistory();
      if (!mounted) return;
      setState(() {
        _messages.addAll(history);
        _isLoadingHistory = false;
      });
      _scrollToBottom();
    } on ApiException catch (_) {
      if (!mounted) return;
      setState(() => _isLoadingHistory = false);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _send([String? presetText]) async {
    final text = (presetText ?? _controller.text).trim();
    if (text.isEmpty || _isSending) return;

    setState(() {
      _messages.add(ChatMessage(text: text, fromUser: true));
      _isSending = true;
      _controller.clear();
    });
    _scrollToBottom();

    try {
      final reply = await context.read<ChatRepository>().sendMessage(
            text,
            userId: context.read<AuthRepository>().currentUser?.id,
            selectedApplication: widget.selectedApplication,
          );
      if (!mounted) return;
      setState(() => _messages.add(ChatMessage(text: reply, fromUser: false)));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _messages.add(ChatMessage(text: e.message, fromUser: false)));
    } finally {
      if (mounted) setState(() => _isSending = false);
      _scrollToBottom();
    }
  }

  /// Interleaves a DateTime day-separator marker before the first message
  /// of each real calendar day (by local time), comparing each message's
  /// own real ChatMessage.sentAt - no message content or timestamp is
  /// invented, only grouped.
  List<Object> _buildTimelineItems(List<ChatMessage> messages) {
    final items = <Object>[];
    DateTime? lastDay;
    for (final message in messages) {
      final day = DateTime(message.sentAt.year, message.sentAt.month, message.sentAt.day);
      if (lastDay == null || day != lastDay) {
        items.add(day);
        lastDay = day;
      }
      items.add(message);
    }
    return items;
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(_scrollController.position.maxScrollExtent, duration: const Duration(milliseconds: 250), curve: Curves.easeOut);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final app = widget.selectedApplication;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Security assistant'),
        bottom: app != null
            ? PreferredSize(
                preferredSize: const Size.fromHeight(36),
                child: Container(
                  width: double.infinity,
                  color: AppColors.surfaceAlt,
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: Row(
                    children: [
                      const Icon(Icons.apps, size: 14, color: AppColors.textSecondary),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          'Chatting about: ${app.appName}',
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                        ),
                      ),
                    ],
                  ),
                ),
              )
            : null,
      ),
      body: Column(
        children: [
          Expanded(
            child: _isLoadingHistory
                ? const LoadingView(message: 'Loading your conversation...')
                : _messages.isEmpty
                ? _EmptyChatSuggestions(onTap: _send, examples: _examples)
                : Builder(builder: (context) {
                    // Real per-message timestamps grouped into day separators
                    // ("Today"/"Yesterday"/literal date) - every timestamp
                    // here is the real ChatMessage.sentAt already parsed from
                    // the backend's own created_at; this only changes how
                    // existing real data is grouped for display, it never
                    // invents a discrete "conversation" the backend doesn't
                    // have a concept of.
                    final items = _buildTimelineItems(_messages);
                    return ListView.builder(
                      controller: _scrollController,
                      padding: const EdgeInsets.fromLTRB(12, 16, 12, 16),
                      itemCount: items.length,
                      itemBuilder: (context, index) {
                        final item = items[index];
                        if (item is DateTime) {
                          return _DateSeparator(date: item);
                        }
                        return _MessageBubble(message: item as ChatMessage);
                      },
                    );
                  }),
          ),
          if (_isSending) const LinearProgressIndicator(minHeight: 2),
          SafeArea(
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: const BoxDecoration(
                border: Border(top: BorderSide(color: AppColors.border)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Expanded(
                    child: TextField(
                      controller: _controller,
                      minLines: 1,
                      maxLines: 4,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: const InputDecoration(hintText: 'Ask a question...'),
                      onSubmitted: (_) => _send(),
                      textInputAction: TextInputAction.send,
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    icon: const Icon(Icons.send),
                    onPressed: _isSending ? null : () => _send(),
                    tooltip: 'Send',
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EmptyChatSuggestions extends StatelessWidget {
  final List<String> examples;
  final void Function(String) onTap;
  const _EmptyChatSuggestions({required this.examples, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 72,
              height: 72,
              decoration: const BoxDecoration(shape: BoxShape.circle, color: AppColors.accentSoft),
              child: const Icon(Icons.smart_toy_outlined, size: 34, color: AppColors.accent),
            ),
            const SizedBox(height: 16),
            const Text('Ask about app security, risk, or compatibility.', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            const Text(
              'Answers are grounded in real, stored assessment data.',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary, fontSize: 12),
            ),
            const SizedBox(height: 18),
            Wrap(
              alignment: WrapAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: examples.map((e) => ActionChip(
                    avatar: const Icon(Icons.chat_bubble_outline, size: 15, color: AppColors.accent),
                    label: Text(e),
                    onPressed: () => onTap(e),
                  )).toList(),
            ),
          ],
        ),
      ),
    );
  }
}

class _DateSeparator extends StatelessWidget {
  final DateTime date;
  const _DateSeparator({required this.date});

  String _label() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    if (date == today) return 'Today';
    if (date == yesterday) return 'Yesterday';
    return '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
          decoration: BoxDecoration(color: AppColors.surfaceAlt, borderRadius: BorderRadius.circular(20)),
          child: Text(_label(), style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppColors.textSecondary)),
        ),
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  final ChatMessage message;
  const _MessageBubble({required this.message});

  String _formatTime(DateTime dt) {
    final hour = dt.hour % 12 == 0 ? 12 : dt.hour % 12;
    final minute = dt.minute.toString().padLeft(2, '0');
    final period = dt.hour >= 12 ? 'PM' : 'AM';
    return '$hour:$minute $period';
  }

  @override
  Widget build(BuildContext context) {
    final isUser = message.fromUser;
    final avatar = CircleAvatar(
      radius: 14,
      backgroundColor: isUser ? AppColors.accentSoft : AppColors.surfaceAlt,
      child: Icon(
        isUser ? Icons.person_outline : Icons.shield_outlined,
        size: 16,
        color: isUser ? AppColors.accent : AppColors.textSecondary,
      ),
    );

    final bubble = Container(
      margin: const EdgeInsets.symmetric(vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.7),
      decoration: BoxDecoration(
        color: isUser ? AppColors.accent.withValues(alpha: 0.22) : AppColors.surface,
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(14),
          topRight: const Radius.circular(14),
          bottomLeft: Radius.circular(isUser ? 14 : 4),
          bottomRight: Radius.circular(isUser ? 4 : 14),
        ),
        border: isUser ? null : Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // SelectableText keeps long explanations (SHAP/CWE detail,
          // vulnerability descriptions) copyable and always wraps rather
          // than overflowing the bubble/screen width set above.
          SelectableText(message.text, style: const TextStyle(fontSize: 14, height: 1.35)),
          const SizedBox(height: 4),
          Text(_formatTime(message.sentAt), style: const TextStyle(fontSize: 10, color: AppColors.textSecondary)),
        ],
      ),
    );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: isUser
            ? [Flexible(child: bubble), const SizedBox(width: 8), avatar]
            : [avatar, const SizedBox(width: 8), Flexible(child: bubble)],
      ),
    );
  }
}
