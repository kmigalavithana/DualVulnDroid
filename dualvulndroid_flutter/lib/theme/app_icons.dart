import 'package:flutter/material.dart';

import '../models/user_preferences_model.dart';

/// One place for every meaningful icon in SmartApp, so the same concept
/// always shows the same Material icon on every screen.
class AppIcons {
  AppIcons._();

  // Navigation / features
  static const IconData home = Icons.home_outlined;
  static const IconData homeFilled = Icons.home_rounded;
  static const IconData discover = Icons.explore_outlined;
  static const IconData discoverFilled = Icons.explore_rounded;
  static const IconData search = Icons.search_rounded;
  static const IconData recommendations = Icons.auto_awesome_outlined;
  static const IconData history = Icons.history_rounded;
  static const IconData profile = Icons.person_outline_rounded;
  static const IconData profileFilled = Icons.person_rounded;
  static const IconData favorites = Icons.favorite_border_rounded;
  static const IconData favoritesFilled = Icons.favorite_rounded;
  static const IconData alternatives = Icons.swap_horiz_rounded;
  static const IconData installedApps = Icons.apps_rounded;
  static const IconData settings = Icons.settings_outlined;
  static const IconData whatIf = Icons.tune_rounded;
  static const IconData evaluation = Icons.analytics_outlined;
  static const IconData insight = Icons.lightbulb_outline_rounded;
  static const IconData playStore = Icons.shop_outlined;
  static const IconData liveData = Icons.cloud_done_outlined;
  static const IconData demoData = Icons.science_outlined;
  static const IconData chevron = Icons.chevron_right_rounded;
  static const IconData clear = Icons.close_rounded;
  static const IconData delete = Icons.delete_outline_rounded;
  static const IconData refresh = Icons.refresh_rounded;
  static const IconData rating = Icons.star_rounded;
  static const IconData info = Icons.info_outline_rounded;
  static const IconData check = Icons.check_circle_outline_rounded;
  static const IconData calendar = Icons.event_outlined;
  static const IconData timer = Icons.timer_outlined;

  // Device
  static const IconData device = Icons.phone_android_rounded;
  static const IconData ram = Icons.memory_rounded;
  static const IconData android = Icons.android_rounded;
  static const IconData storage = Icons.sd_storage_outlined;
  static const IconData battery = Icons.battery_std_rounded;
  static const IconData network = Icons.wifi_rounded;
  static const IconData cpu = Icons.developer_board_outlined;

  // Recommendation factors
  static const IconData preferences = Icons.tune_rounded;
  static const IconData privacy = Icons.shield_outlined;
  static const IconData performance = Icons.speed_rounded;
  static const IconData offline = Icons.cloud_off_rounded;

  /// Icon for each "Why this app?" factor, in [RecommendationResult.explanationFactors] order.
  static const List<IconData> factorIcons = [preferences, device, privacy, performance, rating];

  static IconData forPreference(AppPreference preference) => switch (preference) {
        AppPreference.lightweight => Icons.bolt_rounded,
        AppPreference.privacyFriendly => privacy,
        AppPreference.noAds => Icons.block_rounded,
        AppPreference.offlineSupport => offline,
        AppPreference.free => Icons.money_off_rounded,
        AppPreference.openSource => Icons.code_rounded,
        AppPreference.lowStorageUsage => storage,
      };
}
