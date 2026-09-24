import 'package:flutter/material.dart';

/// SmartApp's light palette. Semantic colors are always paired with an
/// icon and a text label in the UI (never color alone).
///
/// Usage rules:
///   indigo [accent]      - primary actions, active navigation, match indicators
///   cyan [accentCyan]    - secondary highlights, device/context accents
///   green [success]      - success only
///   orange [warning]     - warnings only
///   red [error]          - errors only
class AppColors {
  AppColors._();

  static const Color background = Color(0xFFF7F9FC);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color surfaceAlt = Color(0xFFF1F4F9);

  static const Color accent = Color(0xFF4F6BFF);

  /// A soft indigo tint for selected chips and gentle highlights.
  static const Color accentSoft = Color(0xFFEEF1FF);

  static const Color accentCyan = Color(0xFF22B8CF);
  static const Color accentCyanSoft = Color(0xFFE7F7FA);

  static const Color textPrimary = Color(0xFF182033);
  static const Color textSecondary = Color(0xFF667085);

  /// Captions, timestamps and other text that should recede further.
  static const Color textMuted = Color(0xFF98A2B3);

  /// Hairline separator / card border.
  static const Color border = Color(0xFFE4E7EC);

  /// Very subtle card shadow color.
  static const Color shadow = Color(0x14101828);

  static const Color riskLow = Color(0xFF12B76A);
  static const Color riskMedium = Color(0xFFF79009);
  static const Color riskHigh = Color(0xFFF04438);
  static const Color riskCritical = Color(0xFFD92D20);
  static const Color riskUnknown = textMuted;

  static const Color success = riskLow;
  static const Color warning = riskMedium;
  static const Color error = riskHigh;

  /// Color for a 0-100 match percentage. A match is a fit for THIS user,
  /// not a verdict on the app, so it is always the brand indigo - never
  /// the success/warning/error colors. The ring's fill shows the amount.
  static Color forMatchPercent(int percent) => accent;

  static Color forRiskLevel(String? riskLevel) {
    switch (riskLevel?.toUpperCase()) {
      case 'LOW':
        return riskLow;
      case 'MEDIUM':
        return riskMedium;
      case 'HIGH':
        return riskHigh;
      case 'CRITICAL':
        return riskCritical;
      default:
        return riskUnknown;
    }
  }

  /// A barely-there indigo wash for the Home hero card.
  static const LinearGradient heroSurfaceGradient = LinearGradient(
    colors: [Color(0xFFF0F3FF), Color(0xFFFFFFFF)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static LinearGradient riskGradient(String? riskLevel) {
    final color = forRiskLevel(riskLevel);
    return LinearGradient(
      colors: [color.withValues(alpha: 0.16), color.withValues(alpha: 0.02)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
  }
}
