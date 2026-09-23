import '../models/app_info_model.dart';
import '../models/context_effect_model.dart';
import '../models/device_profile_model.dart';
import '../models/user_preferences_model.dart';

/// Detects which real device-context conditions are currently active, and
/// how much each app's own attributes should be nudged in response
/// (Part 6: "Context-aware recommendation" - low storage/RAM/battery,
/// offline connectivity). Pure and stateless: every threshold below is a
/// named constant, every effect is computed only from a genuine
/// [DeviceProfileModel] field, and a `null` signal never triggers an
/// effect (unknown is never treated as "low").
///
/// Deliberately does NOT touch [UserPreferencesModel] - context effects
/// nudge the [ScoreBreakdown.context] addend only, so the user's actual
/// selected preferences are never silently rewritten (Part 6: "Do not
/// silently change user preferences").
class ContextEngine {
  const ContextEngine();

  static const int lowStorageBytesThreshold = 1024 * 1024 * 1024; // 1 GB free
  static const int lowRamMbThreshold = 3072; // 3 GB total
  static const int lowBatteryPercent = 20;

  /// The real, currently-active context effects for [device] - empty when
  /// every relevant signal is either unavailable or not actually low.
  List<ContextEffect> evaluate(DeviceProfileModel device) {
    final effects = <ContextEffect>[];

    final freeStorage = device.storageFreeBytes;
    if (freeStorage != null && freeStorage < lowStorageBytesThreshold) {
      effects.add(const ContextEffect(
        ContextEffectType.lowStorage,
        'Your device is low on storage — smaller apps are prioritized.',
      ));
    }

    final ram = device.ramTotalMb;
    if (device.isLowRamDevice == true || (ram != null && ram < lowRamMbThreshold)) {
      effects.add(const ContextEffect(
        ContextEffectType.lowRam,
        'Your device has limited RAM — lightweight apps are prioritized.',
      ));
    }

    final battery = device.batteryLevel;
    if (battery != null && battery <= lowBatteryPercent) {
      effects.add(const ContextEffect(
        ContextEffectType.lowBattery,
        'Your battery is low — resource-efficient apps are prioritized.',
      ));
    }

    if (device.connectivityStatus == ConnectivityStatus.offline) {
      effects.add(const ContextEffect(
        ContextEffectType.offline,
        'You\'re offline — apps that work without internet are prioritized.',
      ));
    }

    return effects;
  }

  /// A small, bounded (±10), fully-calculated adjustment for [app] given
  /// the currently-[active] effects - added on top of (never replacing)
  /// the five fixed-weight sub-scores. Every term here is a deterministic
  /// function of a real [AppInfo] attribute, so it stays as explainable
  /// and non-fabricated as the rest of the engine.
  /// Every term below returns 0 (no adjustment either way) when the
  /// underlying app attribute is unavailable - unverified data is never
  /// treated as either a good or bad fit for the current context.
  double contextScoreFor(AppInfo app, List<ContextEffect> active) {
    double total = 0;
    for (final effect in active) {
      switch (effect.type) {
        case ContextEffectType.lowStorage:
          final sizeMb = app.sizeMb;
          if (app.satisfies(AppPreference.lowStorageUsage)) {
            total += 3;
          } else if (sizeMb != null && sizeMb > 150) {
            total += -3;
          }
        case ContextEffectType.lowRam:
          total += switch (app.resourceLevel) {
            ResourceLevel.light => 3,
            ResourceLevel.moderate => 0,
            ResourceLevel.heavy => -3,
            null => 0,
          };
        case ContextEffectType.lowBattery:
          total += switch (app.resourceLevel) {
            ResourceLevel.light => 2,
            ResourceLevel.moderate => 0,
            ResourceLevel.heavy => -2,
            null => 0,
          };
        case ContextEffectType.offline:
          if (app.supportsOffline != null) {
            total += app.supportsOffline! ? 3 : -3;
          }
      }
    }
    return total.clamp(-10, 10);
  }
}
