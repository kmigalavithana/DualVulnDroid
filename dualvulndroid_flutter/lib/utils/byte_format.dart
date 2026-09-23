/// Formats a byte count as a human-readable GB/MB string (Part 6's "18.4
/// GB" example). Returns "Unavailable" for `null` - callers should
/// always pass through a real value or `null`, never a fabricated 0.
String formatBytes(int? bytes, {int decimals = 1}) {
  if (bytes == null) return 'Unavailable';
  const gb = 1024 * 1024 * 1024;
  const mb = 1024 * 1024;
  if (bytes >= gb) return '${(bytes / gb).toStringAsFixed(decimals)} GB';
  if (bytes >= mb) return '${(bytes / mb).toStringAsFixed(decimals)} MB';
  return '$bytes B';
}

/// Formats a megabyte value (device_info_plus already reports RAM in MB)
/// the same way, so RAM/storage read consistently on screen.
String formatMb(int? megabytes) {
  if (megabytes == null) return 'Unavailable';
  if (megabytes >= 1024) return '${(megabytes / 1024).toStringAsFixed(1)} GB';
  return '$megabytes MB';
}

/// Formats an app's declared size (already in MB as a double). `null`
/// (unknown - e.g. real Google Play metadata, which does not report
/// install size the way this app's curated demo dataset does) renders as
/// "Unavailable", never a fabricated 0/guessed size.
String formatAppSizeMb(double? sizeMb) {
  if (sizeMb == null) return 'Unavailable';
  if (sizeMb >= 1024) return '${(sizeMb / 1024).toStringAsFixed(1)} GB';
  if (sizeMb == sizeMb.roundToDouble()) return '${sizeMb.toStringAsFixed(0)} MB';
  return '${sizeMb.toStringAsFixed(1)} MB';
}
