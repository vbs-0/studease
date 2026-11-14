import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api.dart';
import 'screens/auth.dart';
import 'screens/learner.dart';
import 'screens/more.dart';
import 'screens/staff.dart';
import 'screens/student.dart';
import 'theme.dart';
import 'ui/kit.dart';

final themeMode = ValueNotifier<ThemeMode>(ThemeMode.system);
final session = ValueNotifier<Me?>(null);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    final p = await SharedPreferences.getInstance();
    themeMode.value = {'light': ThemeMode.light, 'dark': ThemeMode.dark}[p.getString('theme')] ?? ThemeMode.system;
  } catch (_) {}
  Api.instance.onSignedOut = () => session.value = null;
  runApp(const StudEaseApp());
}

Future<void> setTheme(ThemeMode m) async {
  themeMode.value = m;
  try { await (await SharedPreferences.getInstance()).setString('theme', m.name); } catch (_) {}
}

class StudEaseApp extends StatelessWidget {
  const StudEaseApp({super.key});
  @override
  Widget build(BuildContext context) => ValueListenableBuilder<ThemeMode>(
        valueListenable: themeMode,
        builder: (_, mode, _) => MaterialApp(
          title: 'StudEase',
          debugShowCheckedModeBanner: false,
          theme: buildTheme(Brightness.light),
          darkTheme: buildTheme(Brightness.dark),
          themeMode: mode,
          home: const Gate(),
        ),
      );
}

/// Splash while the stored token is checked, then sign-in or the app.
class Gate extends StatefulWidget {
  const Gate({super.key});
  @override
  State<Gate> createState() => _GateState();
}

class _GateState extends State<Gate> {
  bool _checking = true;
  @override
  void initState() { super.initState(); _boot(); }

  Future<void> _boot() async {
    if (await Api.instance.restore()) {
      try { session.value = await Api.instance.me(); } on ApiException catch (e) {
        if (e.status != 0) { await Api.instance.signOut(); }
      }
    }
    if (mounted) setState(() => _checking = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) return const Splash();
    return ValueListenableBuilder<Me?>(
      valueListenable: session,
      builder: (_, me, _) => AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        child: me == null ? const LoginScreen(key: ValueKey('login')) : Shell(key: ValueKey(me.id), me: me),
      ),
    );
  }
}

class Splash extends StatelessWidget {
  const Splash({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TweenAnimationBuilder<double>(
              tween: Tween(begin: .85, end: 1), duration: const Duration(milliseconds: 900), curve: Curves.easeInOutSine,
              builder: (_, v, child) => Transform.scale(scale: v, child: child),
              child: Image.asset('assets/logo.png', width: 96, height: 96),
            ),
            const SizedBox(height: 14),
            const Text('STUDEASE', style: TextStyle(fontWeight: FontWeight.w800, letterSpacing: 4, fontSize: 14)),
            const SizedBox(height: 18),
            const SizedBox(width: 120, child: LinearProgressIndicator(minHeight: 3, borderRadius: BorderRadius.all(Radius.circular(3)))),
          ]),
        ),
      );
}

class Tab {
  final String label;
  final IconData icon, selected;
  final Widget Function() page;
  const Tab(this.label, this.icon, this.selected, this.page);
}

/// Bottom navigation by role: learners see their account, enrolment, awards and fees; staff see the books; instructors see students.
class Shell extends StatefulWidget {
  final Me me;
  const Shell({super.key, required this.me});
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _i = 0;
  late final List<Tab> _tabs = _build(widget.me);

  List<Tab> _build(Me me) {
    final more = Tab('More', Icons.menu_rounded, Icons.menu_rounded, () => MoreScreen(me: me));
    if (me.learner) {
      return [
        Tab('Account', Icons.account_balance_wallet_outlined, Icons.account_balance_wallet, () => StudentScreen(id: me.studentId!, me: me, own: true)),
        Tab('Enrol', Icons.edit_calendar_outlined, Icons.edit_calendar, () => const EnrollScreen()),
        Tab('Awards', Icons.workspace_premium_outlined, Icons.workspace_premium, () => const MyAwardsScreen()),
        Tab('Fees', Icons.receipt_long_outlined, Icons.receipt_long, () => const MyFeesScreen()),
        more,
      ];
    }
    if (me.instructor) return [Tab('Students', Icons.groups_outlined, Icons.groups, () => StudentsScreen(me: me)), more];
    return [
      Tab('Overview', Icons.insights_outlined, Icons.insights, () => OverviewScreen(me: me)),
      Tab('Students', Icons.groups_outlined, Icons.groups, () => StudentsScreen(me: me)),
      Tab('Fees', Icons.receipt_long_outlined, Icons.receipt_long, () => FeesScreen(me: me)),
      Tab('Awards', Icons.workspace_premium_outlined, Icons.workspace_premium, () => const AwardsScreen()),
      more,
    ];
  }

  late final List<Widget?> _pages = List.filled(_tabs.length, null);

  @override
  Widget build(BuildContext context) {
    _pages[_i] ??= _tabs[_i].page();
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: Row(children: [Image.asset('assets/logo.png', width: 30, height: 30), const SizedBox(width: 10), const Text('StudEase')]),
        actions: [ValueListenableBuilder<bool>(
          valueListenable: Api.instance.offline,
          builder: (_, off, _) => off ? Padding(padding: const EdgeInsets.only(right: 14), child: Stamp('Offline copy', Palette.of(context).amber)) : const SizedBox(),
        )],
      ),
      body: IndexedStack(index: _i, children: [for (final p in _pages) p ?? const SizedBox()]),
      bottomNavigationBar: _tabs.length < 2 ? null : NavigationBar(
        selectedIndex: _i,
        onDestinationSelected: (v) => setState(() => _i = v),
        destinations: [for (final t in _tabs) NavigationDestination(icon: Icon(t.icon), selectedIcon: Icon(t.selected), label: t.label)],
      ),
    );
  }
}
