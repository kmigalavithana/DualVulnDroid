import '../core/api_client.dart';
import '../models/history_item_model.dart';

/// GET /user/history - JWT-derived, always only the authenticated user's
/// own scans (the backend never trusts a client-supplied user id here;
/// see app.py's get_current_user dependency).
class HistoryApiService {
  final ApiClient _client;

  HistoryApiService(this._client);

  Future<List<HistoryItem>> getHistory() async {
    final json = await _client.get('/user/history') as Map<String, dynamic>;
    final items = json['history'] as List<dynamic>? ?? const [];
    return items.map((h) => HistoryItem.fromJson(h as Map<String, dynamic>)).toList();
  }
}
