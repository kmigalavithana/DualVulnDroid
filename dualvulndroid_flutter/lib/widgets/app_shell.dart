import 'package:flutter/material.dart';

import '../screens/discover_screen.dart';
import '../screens/history_screen.dart';
import '../screens/home_screen.dart';
import '../screens/profile_screen.dart';
import '../theme/app_colors.dart';
import '../theme/app_icons.dart';

/// The four top-level destinations, in bottom-navigation order.
enum ShellTab { home, discover, history, profile }

/// SmartApp's persistent bottom navigation: Home / Discover / History /
/// Profile. Alternatives, Favorites, Installed Apps, What-If and
/// Evaluation are pushed on top of it as normal routes.
///
/// Back behaves like a real Android app: the shell remembers which tabs
/// you came through (no duplicates), so system back / the app-bar back
/// arrow returns to the previous tab - ultimately Home - and only Back on
/// Home leaves the app. Tabs are built lazily and kept alive
/// (IndexedStack), so returning to a tab never resets it.
class AppShell extends StatefulWidget {
  const AppShell({super.key});

  static _AppShellState? _mounted;

  /// Switches to [tab] if the shell is on screen (recorded in the tab
  /// history, so Back returns to where the user was). Returns false when
  /// there is no shell (e.g. a screen shown on its own in a test).
  static bool select(ShellTab tab) {
    final shell = _mounted;
    if (shell == null || !shell.mounted) return false;
    shell._select(tab.index);
    return true;
  }

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  int _index = 0;
  final List<int> _history = [];
  final List<Widget?> _tabs = List<Widget?>.filled(ShellTab.values.length, null);

  static const _icons = [AppIcons.home, AppIcons.discover, AppIcons.history, AppIcons.profile];
  static const _selectedIcons = [AppIcons.homeFilled, AppIcons.discoverFilled, AppIcons.history, AppIcons.profileFilled];
  static const _labels = ['Home', 'Discover', 'History', 'Profile'];

  Widget _buildTab(int index) {
    switch (ShellTab.values[index]) {
      case ShellTab.home:
        return const HomeScreen();
      case ShellTab.discover:
        return const DiscoverScreen();
      case ShellTab.history:
        return const HistoryScreen();
      case ShellTab.profile:
        return const ProfileScreen();
    }
  }

  bool get _canGoBack => _index != ShellTab.home.index || _history.isNotEmpty;

  void _select(int index) {
    if (index == _index) return;
    setState(() {
      _history
        ..remove(index)
        ..remove(_index)
        ..add(_index);
      _tabs[index] ??= _buildTab(index);
      _index = index;
    });
  }

  void _goBack() {
    setState(() {
      final target = _history.isNotEmpty ? _history.removeLast() : ShellTab.home.index;
      _tabs[target] ??= _buildTab(target);
      _index = target;
    });
  }

  @override
  void initState() {
    super.initState();
    AppShell._mounted = this;
    _tabs[0] = _buildTab(0);
  }

  @override
  void dispose() {
    if (AppShell._mounted == this) AppShell._mounted = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_canGoBack,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _goBack();
      },
      child: ShellScope(
        index: _index,
        canGoBack: _canGoBack,
        goBack: _goBack,
        child: Scaffold(
          body: IndexedStack(
            index: _index,
            children: List.generate(_tabs.length, (i) => _tabs[i] ?? const SizedBox.shrink()),
          ),
          bottomNavigationBar: DecoratedBox(
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: AppColors.border)),
            ),
            child: NavigationBar(
              selectedIndex: _index,
              onDestinationSelected: _select,
              destinations: List.generate(
                _tabs.length,
                (i) => NavigationDestination(
                  icon: Icon(_icons[i]),
                  selectedIcon: Icon(_selectedIcons[i]),
                  label: _labels[i],
                  tooltip: _labels[i],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Lets a tab screen show an app-bar back arrow that returns to the
/// previous tab (the same action as the Android system back button).
class ShellScope extends InheritedWidget {
  final int index;
  final bool canGoBack;
  final VoidCallback goBack;

  const ShellScope({super.key, required this.index, required this.canGoBack, required this.goBack, required super.child});

  static ShellScope? maybeOf(BuildContext context) => context.dependOnInheritedWidgetOfExactType<ShellScope>();

  /// A back button for [tab]'s app bar - or null when [tab] isn't the
  /// visible shell tab or there is nowhere to go back to (Home at the
  /// root). Outside the shell (a pushed copy) Flutter's own automatic
  /// back button applies.
  static Widget? backButtonFor(BuildContext context, ShellTab tab) {
    final scope = maybeOf(context);
    if (scope == null || scope.index != tab.index || !scope.canGoBack) return null;
    return BackButton(onPressed: scope.goBack);
  }

  @override
  bool updateShouldNotify(ShellScope oldWidget) => oldWidget.index != index || oldWidget.canGoBack != canGoBack;
}
