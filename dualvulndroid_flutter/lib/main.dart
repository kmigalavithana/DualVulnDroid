import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/api_client.dart';
import 'core/secure_token_storage.dart';
import 'repositories/apps_repository.dart';
import 'repositories/auth_repository.dart';
import 'repositories/chat_repository.dart';
import 'repositories/device_profile_repository.dart';
import 'repositories/history_repository.dart';
import 'screens/splash_screen.dart';
import 'services/apps_api_service.dart';
import 'services/auth_api_service.dart';
import 'services/chat_api_service.dart';
import 'services/history_api_service.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const DualVulnDroidApp());
}

class DualVulnDroidApp extends StatelessWidget {
  const DualVulnDroidApp({super.key});

  @override
  Widget build(BuildContext context) {
    // ApiClient reads the JWT directly from SecureTokenStorage (Part 3/4)
    // rather than from AuthRepository, so there's no circular dependency
    // between "the client that needs a token" and "the repository that
    // needs a client" - both simply share the same underlying storage.
    final tokenStorage = SecureTokenStorage();
    final apiClient = ApiClient(tokenProvider: tokenStorage.readToken);

    return MultiProvider(
      providers: [
        ChangeNotifierProvider(
          create: (_) => AuthRepository(api: AuthApiService(apiClient), tokenStorage: tokenStorage),
        ),
        Provider(create: (_) => AppsRepository(AppsApiService(apiClient))),
        Provider(create: (_) => HistoryRepository(HistoryApiService(apiClient))),
        Provider(create: (context) => ChatRepository(ChatApiService(apiClient))),
        ChangeNotifierProvider(create: (_) => DeviceProfileRepository()),
      ],
      child: MaterialApp(
        title: 'DualVulnDroid',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.dark,
        home: const SplashScreen(),
      ),
    );
  }
}
