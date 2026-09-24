import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../repositories/preferences_repository.dart';
import '../routing/app_router.dart';
import '../widgets/smartapp_logo.dart';

/// Branded launch screen. Waits only for local preferences to finish
/// loading from disk (fast, no network) then routes straight to
/// onboarding (first run) or the main app shell - no login, no backend
/// health check.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _proceedWhenReady();
  }

  Future<void> _proceedWhenReady() async {
    final repo = context.read<PreferencesRepository>();
    // A short, deliberate minimum so the brand is actually visible even
    // when local prefs load instantly - never blocked on anything remote.
    final minimumDelay = Future.delayed(const Duration(milliseconds: 600));
    while (repo.isLoading) {
      await Future.delayed(const Duration(milliseconds: 30));
      if (!mounted) return;
    }
    await minimumDelay;
    if (!mounted) return;
    if (repo.hasCompletedOnboarding) {
      AppRouter.toHome(context);
    } else {
      AppRouter.toOnboarding(context);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SmartAppLogo(size: 88),
            const SizedBox(height: 20),
            Text('SmartApp', style: Theme.of(context).textTheme.displaySmall),
            const SizedBox(height: 6),
            Text('Find apps that fit your preferences and your device.', style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 32),
            const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5)),
          ],
        ),
      ),
    );
  }
}
