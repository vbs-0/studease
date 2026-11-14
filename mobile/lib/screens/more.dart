import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart' show label;
import '../main.dart' show session, setTheme, themeMode;
import '../theme.dart';
import '../ui/fetch.dart';
import '../ui/kit.dart';
import 'staff.dart';

/// Account, appearance, role-specific tools (exceptions, users, data quality, add student) and sign-out.
class MoreScreen extends StatelessWidget {
  final Me me;
  const MoreScreen({super.key, required this.me});

  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    Widget tile(IconData i, String t, String sub, VoidCallback f) => RowLine(
          onTap: f,
          left: Row(children: [Icon(i, size: 22, color: k.orange), const SizedBox(width: 14), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(t, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)), muted(context, sub)]))]),
          right: const Icon(Icons.chevron_right_rounded),
        );
    void open(Widget w) => Navigator.push(context, MaterialPageRoute(builder: (_) => w));
    final tools = <Widget>[
      if (staffRoles.contains(me.role)) tile(Icons.person_add_alt_1_rounded, 'Add student', 'Enter a student and, optionally, their login', () => open(const AddStudentScreen())),
      if (me.role == 'SUPPORT' || me.role == 'PLATFORM_ADMIN') tile(Icons.report_gmailerrorred_rounded, 'Exceptions', 'The detected billing and reconciliation cases', () => open(ExceptionsScreen(me: me))),
      if (me.role == 'PLATFORM_ADMIN') tile(Icons.manage_accounts_rounded, 'Users', 'Create logins, enable or disable access', () => open(const UsersScreen())),
      if (me.role == 'PLATFORM_ADMIN') tile(Icons.fact_check_outlined, 'Data quality', 'Validation, detection and reproducibility reports', () => open(const QualityScreen())),
    ];
    return ListPage([
      Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(me.email, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
        const SizedBox(height: 6),
        Wrap(spacing: 8, children: [Stamp(label(me.role), k.orange), if (me.studentId != null) Stamp(me.studentId!, k.muted), if (me.programId != null) Stamp(me.programId!, k.muted)]),
      ])),
      if (tools.isNotEmpty) Panel(title: 'Tools', child: Column(children: tools)),
      Panel(title: 'Appearance', child: ValueListenableBuilder<ThemeMode>(
        valueListenable: themeMode,
        builder: (_, m, _) => SegmentedButton<ThemeMode>(
          segments: const [ButtonSegment(value: ThemeMode.system, label: Text('System')), ButtonSegment(value: ThemeMode.light, label: Text('Light')), ButtonSegment(value: ThemeMode.dark, label: Text('Dark'))],
          selected: {m}, onSelectionChanged: (s) => setTheme(s.first),
        ),
      )),
      const _Password(),
      Panel(title: 'About', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('StudEase 1.0.0', style: TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 4),
        muted(context, 'Tuition, scholarships, payments and reconciled student balances. Every figure is synthetic.'),
        const SizedBox(height: 4),
        muted(context, 'Server: ${apiBase.replaceAll('/api/v1', '')}'),
      ])),
      OutlinedButton.icon(
        onPressed: () async { await Api.instance.signOut(); session.value = null; },
        icon: const Icon(Icons.logout_rounded), label: const Text('Sign out'),
      ),
    ]);
  }
}

class _Password extends StatefulWidget {
  const _Password();
  @override
  State<_Password> createState() => _PasswordState();
}

class _PasswordState extends State<_Password> {
  final _cur = TextEditingController(), _new = TextEditingController();
  @override
  Widget build(BuildContext context) => Panel(title: 'Change password', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Field('Current password', _cur, obscure: true),
        Field('New password (12+ characters)', _new, obscure: true),
        SizedBox(width: double.infinity, child: SubmitButton('Change password', outlined: true, onPressed: () async {
          if (_new.text.length < 12) { toast(context, 'Use a new password of at least 12 characters.'); return; }
          final ok = await attempt(context, () async { await Api.instance.post('/auth/change-password', {'current_password': _cur.text, 'new_password': _new.text}); });
          if (ok) { _cur.clear(); _new.clear(); if (context.mounted) toast(context, 'Password changed'); }
        })),
      ]));
}
