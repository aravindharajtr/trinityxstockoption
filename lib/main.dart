import 'package:flutter/material.dart';
import 'theme/app_theme.dart';
import 'screens/dashboard_screen.dart';
import 'screens/positions_screen.dart';
import 'screens/settings_screen.dart';

void main() {
  runApp(const TrinityXApp());
}

class TrinityXApp extends StatelessWidget {
  const TrinityXApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TrinityX',
      debugShowCheckedModeBanner: false,
      theme: buildAppTheme(),
      home: const RootShell(),
    );
  }
}

class RootShell extends StatefulWidget {
  const RootShell({super.key});

  @override
  State<RootShell> createState() => _RootShellState();
}

class _RootShellState extends State<RootShell> {
  int _index = 0;

  static const List<Widget> _screens = [
    DashboardScreen(),
    PositionsScreen(),
    SettingsScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        backgroundColor: AppColors.slate,
        selectedItemColor: AppColors.trinity,
        unselectedItemColor: AppColors.mist,
        type: BottomNavigationBarType.fixed,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.dashboard_outlined), label: 'Dashboard'),
          BottomNavigationBarItem(icon: Icon(Icons.show_chart), label: 'Positions'),
          BottomNavigationBarItem(icon: Icon(Icons.tune), label: 'Strategy'),
        ],
      ),
    );
  }
}
