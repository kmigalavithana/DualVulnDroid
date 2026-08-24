import 'package:flutter/material.dart';

/// Semantic colors for risk/compatibility states. These are always
/// paired with an icon and a text label in the UI (Part 20:
/// "Do not communicate risk using color alone") - this file only defines
/// the color half of that pairing; see widgets/risk_badge.dart for the
/// icon pairing.
class AppColors {
  AppColors._();

  static const Color background = Color(0xFF0B0E14);
  static const Color surface = Color(0xFF161A23);
  static const Color surfaceAlt = Color(0xFF1E2430);
  static const Color accent = Color(0xFF4C8DFF);
  static const Color accentSoft = Color(0xFF1B2740);

  /// Secondary accent (design brief: "cyan secondary accent"), paired with
  /// [accent] the same way [accentSoft] pairs with it - used sparingly for
  /// hero/gradient treatments, never as a second semantic color.
  static const Color accentCyan = Color(0xFF22D3EE);
  static const Color accentCyanSoft = Color(0xFF10303A);

  static const Color textPrimary = Color(0xFFF2F4F8);
  static const Color textSecondary = Color(0xFFA6ADBB);

  /// A hairline separator/card border - flat (elevation 0) cards and app
  /// bars otherwise have no depth cue against the near-identical
  /// background, so this gives every surface a subtle, consistent edge.
  static const Color border = Color(0xFF262D3B);

  static const Color riskLow = Color(0xFF3DDC84);
  static const Color riskMedium = Color(0xFFFFB020);
  static const Color riskHigh = Color(0xFFFF5A5F);
  static const Color riskCritical = Color(0xFFD32F2F);
  static const Color riskUnknown = Color(0xFF8A93A6);

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

  /// Subtle diagonal wash for splash/hero surfaces - the design brief's
  /// "subtle gradients", kept to the existing accent/cyan pair rather than
  /// introducing new colors.
  static const LinearGradient heroGradient = LinearGradient(
    colors: [accent, accentCyan],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  /// A two-stop wash of the real risk color for a given assessment, used
  /// as a large status-card background. Always derived from the same
  /// [forRiskLevel] color used everywhere else - never a separate palette.
  static LinearGradient riskGradient(String? riskLevel) {
    final color = forRiskLevel(riskLevel);
    return LinearGradient(
      colors: [color.withValues(alpha: 0.28), color.withValues(alpha: 0.04)],
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
    );
  }
}
