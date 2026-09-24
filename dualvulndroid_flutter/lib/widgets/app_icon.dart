import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import 'category_icons.dart';

/// One app's icon: a real Google Play icon image when [iconUrl] is
/// available, falling back to a plain Material icon (via [iconKey]) when
/// there is no URL or the image fails to load - never a fabricated photo
/// standing in for a real app's actual icon.
class AppIcon extends StatelessWidget {
  final String? iconUrl;
  final String iconKey;
  final double size;

  const AppIcon({super.key, required this.iconUrl, required this.iconKey, this.size = 44});

  @override
  Widget build(BuildContext context) {
    final url = iconUrl;
    return Container(
      width: size,
      height: size,
      clipBehavior: Clip.antiAlias,
      decoration: BoxDecoration(color: AppColors.surfaceAlt, borderRadius: BorderRadius.circular(size / 3.6)),
      child: url == null
          ? _fallbackIcon()
          : Image.network(
              url,
              width: size,
              height: size,
              fit: BoxFit.cover,
              errorBuilder: (context, error, stackTrace) => _fallbackIcon(),
              loadingBuilder: (context, child, progress) => progress == null
                  ? child
                  : Center(
                      child: SizedBox(
                        width: size * 0.4,
                        height: size * 0.4,
                        child: const CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
            ),
    );
  }

  Widget _fallbackIcon() => Center(child: Icon(resolveIconKey(iconKey), color: AppColors.accent, size: size * 0.5));
}
