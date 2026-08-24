import '../models/history_item_model.dart';
import '../services/history_api_service.dart';

class HistoryRepository {
  final HistoryApiService _api;

  HistoryRepository(this._api);

  Future<List<HistoryItem>> getHistory() => _api.getHistory();
}
