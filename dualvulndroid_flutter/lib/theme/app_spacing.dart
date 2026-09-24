import 'package:flutter/widgets.dart';

/// SmartApp's spacing scale - every gap/padding in the UI is one of these
/// steps, so screens line up with each other instead of each picking its
/// own numbers.
class AppSpacing {
  AppSpacing._();

  static const double xxs = 4;
  static const double xs = 6;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double xxl = 24;
  static const double section = 28;

  /// Standard horizontal page gutter.
  static const double page = 20;

  static const EdgeInsets pagePadding = EdgeInsets.fromLTRB(page, lg, page, section);
  static const EdgeInsets cardPadding = EdgeInsets.all(lg);
}

/// Corner radii - small controls, cards, and large hero surfaces.
class AppRadius {
  AppRadius._();

  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double xl = 20;
  static const double pill = 999;

  static final BorderRadius smAll = BorderRadius.circular(sm);
  static final BorderRadius mdAll = BorderRadius.circular(md);
  static final BorderRadius lgAll = BorderRadius.circular(lg);
  static final BorderRadius xlAll = BorderRadius.circular(xl);
  static final BorderRadius pillAll = BorderRadius.circular(pill);
}
