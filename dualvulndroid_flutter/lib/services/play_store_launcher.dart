import 'package:url_launcher/url_launcher.dart';

/// Opens a REAL Play Store listing URL (Part 15) - never constructs or
/// guesses a URL from a package name; only ever opens
/// [AppInfo.playStoreUrl] exactly as stored in the dataset. Callers must
/// check `app.playStoreUrl != null` themselves before showing the
/// button at all (Part 15: "If no valid URL exists, hide the button").
class PlayStoreLauncher {
  /// Returns `true` if the URL was successfully handed off to the
  /// platform, `false` otherwise (never throws) - callers show a
  /// friendly "Couldn't open the store link" message on `false`.
  Future<bool> open(String url) async {
    try {
      final uri = Uri.tryParse(url);
      if (uri == null) return false;
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      return false;
    }
  }
}
