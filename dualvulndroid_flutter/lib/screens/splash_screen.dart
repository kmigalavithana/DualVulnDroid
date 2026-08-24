import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../repositories/auth_repository.dart';
import '../routing/app_router.dart';
import '../theme/app_colors.dart';

/// Restores any existing session (Part 3: a real stored JWT, if one
/// exists) then routes to the dashboard or login accordingly - never a
/// fixed timer pretending to "load" something real isn't happening.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _resolve());
  }

  Future<void> _resolve() async {
    final auth = context.read<AuthRepository>();
    await auth.restoreSession();
    if (!mounted) return;
    if (auth.isAuthenticated) {
      AppRouter.toDashboard(context);
    } else {
      AppRouter.toLogin(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: RadialGradient(
            center: Alignment(0, -0.2),
            radius: 1.1,
            colors: [AppColors.surface, AppColors.background],
          ),
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 112,
                height: 112,
                padding: const EdgeInsets.all(3),
                decoration: const BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: AppColors.heroGradient,
                ),
                child: Container(
                  decoration: const BoxDecoration(
                    shape: BoxShape.circle,
                    color: AppColors.accentSoft,
                  ),
                  child: const Icon(Icons.security, size: 54, color: AppColors.accent),
                ),
              ),
              const SizedBox(height: 20),
              Text('DualVulnDroid', style: Theme.of(context).textTheme.headlineMedium?.copyWith(letterSpacing: 0.2)),
              const SizedBox(height: 6),
              Text(
                'Real-time SQL injection & certificate\nvalidation detection for Android',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: AppColors.textSecondary, height: 1.4),
              ),
              const SizedBox(height: 28),
              const SizedBox(width: 28, height: 28, child: CircularProgressIndicator(strokeWidth: 2.5)),
            ],
          ),
        ),
      ),
    );
  }
}
