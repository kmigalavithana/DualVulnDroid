import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// The SmartApp brand mark: an indigo rounded square holding a 2x2 grid
/// of apps, where one tile is the highlighted "match" (a solid white
/// circle with a cyan core) - discover + smart matching + apps. Drawn in
/// code so it stays crisp at any size; the launcher icon PNGs use the
/// same geometry (tool/generate_launcher_icon.py).
class SmartAppLogo extends StatelessWidget {
  final double size;
  const SmartAppLogo({super.key, this.size = 44});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'SmartApp',
      image: true,
      child: SizedBox.square(dimension: size, child: const CustomPaint(painter: _SmartAppLogoPainter())),
    );
  }
}

class _SmartAppLogoPainter extends CustomPainter {
  const _SmartAppLogoPainter();

  // Shared geometry (fractions of the icon size).
  static const double cornerRadius = 0.28;
  static const double inset = 0.24;
  static const double tile = 0.22;
  static const double gap = 0.08;

  @override
  void paint(Canvas canvas, Size size) {
    final s = size.width;
    final base = RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(s * cornerRadius));
    canvas.drawRRect(base, Paint()..color = AppColors.accent);

    final soft = Paint()..color = Colors.white.withValues(alpha: 0.55);
    final solid = Paint()..color = Colors.white;
    final a = s * inset;
    final b = s * (inset + tile + gap);
    final t = s * tile;
    final r = Radius.circular(s * 0.06);

    // Three regular app tiles.
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(a, a, t, t), r), soft);
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(a, b, t, t), r), soft);
    canvas.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(b, b, t, t), r), soft);

    // The matched app: a solid circle with a cyan core.
    final center = Offset(b + t / 2, a + t / 2);
    canvas.drawCircle(center, t * 0.62, solid);
    canvas.drawCircle(center, t * 0.24, Paint()..color = AppColors.accentCyan);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
