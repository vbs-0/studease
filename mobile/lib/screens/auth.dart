import 'package:flutter/material.dart';

import '../api.dart';
import '../main.dart' show session;
import '../theme.dart';
import '../ui/kit.dart';

const _demo = [('learner', 'Learner'), ('instructor', 'Instructor'), ('academic', 'Academic admin'), ('support', 'Support'), ('admin', 'Platform admin')];

/// The orange hero card with the page headline, then the form in a white panel: the website's sign-in layout.
class _Frame extends StatelessWidget {
  final String title, lead;
  final List<Widget> children;
  const _Frame({required this.title, required this.lead, required this.children});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return Scaffold(
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          SlideUp(child: Container(
            padding: const EdgeInsets.fromLTRB(22, 22, 22, 26),
            decoration: BoxDecoration(color: k.orange, borderRadius: BorderRadius.circular(28)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [Image.asset('assets/logo.png', width: 26, height: 26), const SizedBox(width: 8), const Text('STUDEASE', style: TextStyle(color: Color(0xFF111111), fontWeight: FontWeight.w800, letterSpacing: 2, fontSize: 12))]),
              const SizedBox(height: 22),
              Text(title.toUpperCase(), style: const TextStyle(color: Color(0xFF111111), fontFamily: serif, fontSize: 52, height: .95)),
              const SizedBox(height: 12),
              Text(lead, style: const TextStyle(color: Color(0xFF111111), fontFamily: serif, fontSize: 19, height: 1.15)),
              const SizedBox(height: 14),
              const Text('Every figure is synthetic. Every balance is checked three ways against an append-only ledger.', style: TextStyle(color: Color(0xCC111111), fontSize: 12.5)),
            ]),
          )),
          const SizedBox(height: 14),
          SlideUp(index: 1, child: Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: children))),
        ]),
      ),
    );
  }
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginState();
}

class _LoginState extends State<LoginScreen> {
  final _email = TextEditingController(), _pw = TextEditingController();
  String? _error;

  Future<void> _go() async {
    setState(() => _error = null);
    try { session.value = await Api.instance.login(_email.text.trim(), _pw.text); } on ApiException catch (e) { setState(() => _error = e.message); }
  }

  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return _Frame(title: 'Tuition, reconciled.', lead: 'Fees, scholarships and payments for ten thousand students, with every balance accounted for.', children: [
      const Text('Sign in', style: TextStyle(fontFamily: serif, fontSize: 30)),
      const SizedBox(height: 10),
      Field('Email', _email, keyboard: TextInputType.emailAddress),
      Field('Password', _pw, obscure: true),
      if (_error != null) Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(_error!, style: TextStyle(color: k.red, fontWeight: FontWeight.w600))),
      SizedBox(width: double.infinity, child: SubmitButton('Sign in', onPressed: _go)),
      const SizedBox(height: 10),
      SizedBox(width: double.infinity, child: OutlinedButton(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SignupScreen())), child: const Text('Create a new account'))),
      Center(child: TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ForgotScreen())), child: Text('Forgot your password?', style: TextStyle(color: k.ink)))),
      const Divider(height: 28),
      Text('DEMO ACCOUNTS (ONE PER ROLE)', style: TextStyle(color: k.muted, fontSize: 11, letterSpacing: 1.2, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      Wrap(spacing: 8, runSpacing: 4, children: [for (final d in _demo) ActionChip(label: Text(d.$2), onPressed: () => setState(() => _email.text = '${d.$1}@example.edu'))]),
      const SizedBox(height: 6),
      muted(context, 'Pick a role, then enter the demo password you were given.'),
    ]);
  }
}

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});
  @override
  State<SignupScreen> createState() => _SignupState();
}

class _SignupState extends State<SignupScreen> {
  final _name = TextEditingController(), _email = TextEditingController(), _pw = TextEditingController(), _gpa = TextEditingController(text: '8.0');
  String _program = 'PRG-01', _res = 'DOMESTIC', _band = 'MID';
  bool _sports = false, _hostel = false;
  String? _error;
  List<Map<String, dynamic>> _programs = [];

  @override
  void initState() {
    super.initState();
    Api.instance.get('/auth/programs').then((d) { if (mounted) setState(() => _programs = ((d as Map)['items'] as List).cast<Map<String, dynamic>>()); }).catchError((_) {});
  }

  Future<void> _go() async {
    setState(() => _error = null);
    final gpa = double.tryParse(_gpa.text);
    if (gpa == null || gpa < 0 || gpa > 10) { setState(() => _error = 'GPA must be a number from 0 to 10.'); return; }
    if (_name.text.trim().length < 2) { setState(() => _error = 'Enter your full name.'); return; }
    if (_pw.text.length < 10) { setState(() => _error = 'Use a password of at least 10 characters.'); return; }
    try {
      session.value = await Api.instance.signup({'full_name': _name.text.trim(), 'email': _email.text.trim(), 'password': _pw.text, 'program_id': _program,
        'residency': _res, 'gpa': gpa, 'income_band': _band, 'sports_quota': _sports, 'hostel_resident': _hostel});
      if (mounted) Navigator.popUntil(context, (r) => r.isFirst);
    } on ApiException catch (e) { setState(() => _error = e.message); }
  }

  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return _Frame(title: 'Join in a minute.', lead: 'Create a learner account, enrol in the current term and see your fees, scholarship and balance.', children: [
      const Text('Create account', style: TextStyle(fontFamily: serif, fontSize: 30)),
      const SizedBox(height: 10),
      Field('Full name', _name),
      Field('Email', _email, keyboard: TextInputType.emailAddress),
      Field('Password (10+ characters)', _pw, obscure: true),
      Pick<String>('Program', _program, _programs.isEmpty ? [('PRG-01', 'PRG-01')] : [for (final p in _programs) (p['program_id'] as String, '${p['name']} (${p['level']})')], (v) => setState(() => _program = v)),
      Row(children: [
        Expanded(child: Pick<String>('Residency', _res, const [('DOMESTIC', 'Domestic'), ('INTERNATIONAL', 'International')], (v) => setState(() => _res = v))),
        const SizedBox(width: 12),
        Expanded(child: Field('GPA (0 to 10)', _gpa, number: true)),
      ]),
      Pick<String>('Household income band', _band, const [('LOW', 'Low'), ('MID', 'Mid'), ('HIGH', 'High'), ('AFFLUENT', 'Affluent')], (v) => setState(() => _band = v)),
      Check('Sports quota', _sports, (v) => setState(() => _sports = v)),
      Check('Hostel resident', _hostel, (v) => setState(() => _hostel = v)),
      muted(context, 'This is a demonstration with synthetic data: use a throwaway email and password.'),
      const SizedBox(height: 10),
      if (_error != null) Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(_error!, style: TextStyle(color: k.red, fontWeight: FontWeight.w600))),
      SizedBox(width: double.infinity, child: SubmitButton('Create account', onPressed: _go)),
      Center(child: TextButton(onPressed: () => Navigator.pop(context), child: Text('I already have an account', style: TextStyle(color: k.ink)))),
    ]);
  }
}

class ForgotScreen extends StatefulWidget {
  const ForgotScreen({super.key});
  @override
  State<ForgotScreen> createState() => _ForgotState();
}

class _ForgotState extends State<ForgotScreen> {
  final _email = TextEditingController(), _token = TextEditingController(), _pw = TextEditingController();
  String? _msg, _error;
  bool _haveCode = false;

  Future<void> _send() async {
    setState(() { _msg = null; _error = null; });
    try { final r = await Api.instance.post('/auth/forgot', {'email': _email.text.trim()}); setState(() { _msg = (r as Map)['message']?.toString() ?? 'If that email has an account, a link is on its way.'; _haveCode = true; }); }
    on ApiException catch (e) { setState(() => _error = e.message); }
  }

  Future<void> _reset() async {
    setState(() { _msg = null; _error = null; });
    try {
      await Api.instance.post('/auth/reset', {'token': _token.text.trim(), 'new_password': _pw.text});
      if (!mounted) return;
      toast(context, 'Password changed. Sign in with the new one.');
      Navigator.pop(context);
    } on ApiException catch (e) { setState(() => _error = e.message); }
  }

  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return _Frame(title: 'Reset access.', lead: 'Enter your email. If it has an account, a single-use link arrives within a minute.', children: [
      Field('Email', _email, keyboard: TextInputType.emailAddress),
      if (_msg != null) Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(_msg!, style: TextStyle(color: k.green, fontWeight: FontWeight.w600))),
      SizedBox(width: double.infinity, child: SubmitButton('Send link', onPressed: _send)),
      TextButton(onPressed: () => setState(() => _haveCode = !_haveCode), child: Text(_haveCode ? 'Hide reset code' : 'I have a reset code', style: TextStyle(color: k.ink))),
      if (_haveCode) ...[
        Field('Reset code (the token in the email link)', _token),
        Field('New password (12+ characters)', _pw, obscure: true),
        SizedBox(width: double.infinity, child: SubmitButton('Change password', onPressed: _reset, outlined: true)),
      ],
      if (_error != null) Padding(padding: const EdgeInsets.only(top: 10), child: Text(_error!, style: TextStyle(color: k.red, fontWeight: FontWeight.w600))),
      Center(child: TextButton(onPressed: () => Navigator.pop(context), child: Text('Back to sign in', style: TextStyle(color: k.ink)))),
    ]);
  }
}
