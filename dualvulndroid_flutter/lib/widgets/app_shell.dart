import 'package:flutter/material.dart';

import '../screens/assessment_history_screen.dart';
import '../screens/dashboard_screen.dart';
import '../screens/search_application_screen.dart';
import '../screens/security_chat_screen.dart';

/// The design's persistent bottom navigation (Home/Search/History/Chat -
/// reduced from the design's original 5-tab set: no "Installed Apps" or
/// "Profile" tab, since neither has any real capability behind it).
///
/// Each of the 4 tab screens keeps its own Scaffold/AppBar/state exactly
/// as it already had before this shell existed (nested Scaffolds) - this
/// widget only supplies the outer bottomNavigationBar and switches which
/// tab's full screen is visible.
///
/// Tabs are built lazily: only the first-visited tab's widget is created,
/// so opening the shell fires exactly the one real network call Dashboard
/// already made before this shell existed, not the 3 extra real calls
/// (History's own getHistory(), Chat's own chat-history fetch) that a
/// naive eagerly-built IndexedStack would trigger on every app launch.
/// Once a tab has been built its State stays alive across further
/// switches (no re-fetch flash when tapping back to it).
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;
  final List<Widget?> _tabs = List<Widget?>.filled(4, null);

  static const _icons = [Icons.dashboard_outlined, Icons.search, Icons.history, Icons.smart_toy_outlined];
  static const _selectedIcons = [Icons.dashboard, Icons.search, Icons.history, Icons.smart_toy];
  static const _labels = ['Home', 'Search', 'History', 'Chat'];

  Widget _buildTab(int index) {
    switch (index) {
      case 0:
        return const DashboardScreen();
      case 1:
        return const SearchApplicationScreen();
      case 2:
        return const AssessmentHistoryScreen();
      case 3:
      default:
        return const SecurityChatScreen();
    }
  }

  @override
  void initState() {
    super.initState();
    _tabs[0] = _buildTab(0);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: List.generate(4, (i) => _tabs[i] ?? const SizedBox.shrink()),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() {
          _tabs[i] ??= _buildTab(i);
          _index = i;
        }),
        destinations: List.generate(
          4,
          (i) => NavigationDestination(icon: Icon(_icons[i]), selectedIcon: Icon(_selectedIcons[i]), label: _labels[i]),
        ),
      ),
    );
  }
}
