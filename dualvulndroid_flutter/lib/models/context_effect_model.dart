/// One kind of real, device-reported condition the recommendation engine
/// can transparently react to (Part 6). Each maps to exactly one genuine
/// [DeviceProfileModel] signal - never inferred from anything else.
enum ContextEffectType { lowStorage, lowRam, lowBattery, offline }

/// One currently-active context effect: a real device condition plus the
/// human-readable explanation of how it is nudging recommendations. Built
/// only when the underlying device signal is actually known and crosses
/// its threshold - never shown speculatively.
class ContextEffect {
  final ContextEffectType type;
  final String message;

  const ContextEffect(this.type, this.message);

  @override
  bool operator ==(Object other) => other is ContextEffect && other.type == type && other.message == message;

  @override
  int get hashCode => Object.hash(type, message);
}
