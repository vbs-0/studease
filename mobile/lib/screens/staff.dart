import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../main.dart' show session;
import '../theme.dart';
import '../ui/fetch.dart';
import '../ui/kit.dart';
import 'student.dart';

typedef J = Map<String, dynamic>;

/// Keyset-paged list: the first page loads at once, "Load more" follows the cursor.
class PagedList extends StatefulWidget {
  final String path;
  final Map<String, String?> query;
  final Widget Function(BuildContext, J) item;
  final String empty;
  final void Function(J firstPage)? onFirst;
  const PagedList({super.key, required this.path, this.query = const {}, required this.item, this.empty = 'Nothing here.', this.onFirst});
  @override
  State<PagedList> createState() => _PagedListState();
}

class _PagedListState extends State<PagedList> {
  final List<J> _rows = [];
  String? _next;
  Object? _error;
  bool _loading = true;

  @override
  void initState() { super.initState(); _first(); Api.instance.epoch.addListener(_first); }

  @override
  void dispose() { Api.instance.epoch.removeListener(_first); super.dispose(); }

  @override
  void didUpdateWidget(PagedList old) {
    super.didUpdateWidget(old);
    if (old.path != widget.path || old.query.toString() != widget.query.toString()) { _loading = true; _first(); }
  }

  Future<void> _first() async {
    try {
      final p = await Api.instance.get(widget.path, {...widget.query, 'limit': '40'}) as J;
      widget.onFirst?.call(p);
      if (mounted) setState(() { _rows..clear()..addAll((p['items'] as List).cast<J>()); _next = p['next']; _error = null; _loading = false; });
    } catch (e) { if (mounted) setState(() { _error = e; _loading = false; }); }
  }

  Future<void> _loadMore() async {
    try {
      final p = await Api.instance.get(widget.path, {...widget.query, 'limit': '40', 'after': _next}) as J;
      if (mounted) setState(() { _rows.addAll((p['items'] as List).cast<J>()); _next = p['next']; });
    } on ApiException catch (e) { if (mounted) toast(context, e.message); }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Column(children: [Skeleton(height: 60), SizedBox(height: 8), Skeleton(height: 60), SizedBox(height: 8), Skeleton(height: 60)]);
    if (_error != null) return ErrorBox(_error!, retry: () { setState(() => _loading = true); _first(); });
    if (_rows.isEmpty) return Empty(widget.empty);
    return Column(children: [
      for (final r in _rows) widget.item(context, r),
      if (_next != null) Padding(padding: const EdgeInsets.only(top: 10), child: SubmitButton('Load more', outlined: true, onPressed: _loadMore)),
    ]);
  }
}

// ------------------------------------------------------------------ overview
class OverviewScreen extends StatelessWidget {
  final Me me;
  const OverviewScreen({super.key, required this.me});
  @override
  Widget build(BuildContext context) => Fetch<J>(
        load: () async => await Api.instance.get('/metrics/overview') as J,
        builder: (c, d, reload) {
          final billed = (d['charged_paise'] as num) + (d['credits_paise'] as num);
          final collection = billed > 0 ? ((d['paid_paise'] as num) / billed * 1000).round() / 10 : 0;
          final byProgram = (d['by_program'] as List).cast<J>();
          final maxProg = byProgram.fold<num>(1, (a, p) => (p['balance_paise'] as num).abs() > a ? (p['balance_paise'] as num).abs() : a);
          final months = (d['by_month'] as List).cast<J>();
          final status = (d['invoice_status'] as Map).entries.toList()..sort((a, b) => (b.value as num).compareTo(a.value as num));
          final openBy = (d['open_by_type'] as Map).cast<String, dynamic>();
          return ListPage([
            PageTitle('Overview', lead: 'The books as of ${d['as_of']}. Money is held in integer paise and shown in rupees.',
                action: ExportButton(name: 'studease-overview-by-program', rows: () async => [['Program', 'Name', 'Students', 'Balance (paise)'], for (final p in byProgram) [p['program_id'], p['name'], p['students'], p['balance_paise']]])),
            MetricGrid([
              Metric(kind: Kind.hero, title: 'Net billed', value: inr(billed), note: '${inr(d['charged_paise'])} charged, ${inr(-(d['credits_paise'] as num))} credits'),
              Metric(title: 'Collected', value: inr((d['paid_paise'] as num) - (d['refunded_paise'] as num)), note: '$collection% of net billed, after ${inr(d['refunded_paise'])} refunds'),
              Metric(kind: Kind.ink, title: 'Owed by students', value: inr(d['owed_paise']), note: '${inr(d['credit_held_paise'])} held as credit'),
              Metric(kind: Kind.mint, title: 'Open exceptions', value: '${d['open_exceptions']}', note: me.role == 'ACADEMIC_ADMIN' ? 'Awaiting support review' : 'Awaiting review'),
            ]),
            Panel(title: 'Charged and collected by month', child: months.length < 2 ? const Empty('Not enough months yet.') : LineChart(
              curve: true, height: 230, format: crore,
              labels: [for (final m in months) m['month']],
              series: [
                LineSeries('Charged', Palette.chart[0], [for (final m in months) (m['charged_paise'] as num).toDouble()]),
                LineSeries('Collected', Palette.chart[1], [for (final m in months) (m['paid_paise'] as num).toDouble()]),
                LineSeries('Refunded', Palette.chart[4], [for (final m in months) (m['refunded_paise'] as num).toDouble()]),
              ],
            )),
            Panel(title: 'Invoices by status', child: Donut(slices: [for (final e in status) Slice(e.key, e.value as num)], centre: '${d['invoices']}', sub: 'invoices')),
            Panel(title: 'Net billed by term', child: TermBars([for (final t in (d['by_term'] as List).cast<J>()) (label(t['term_name']), t['net_billed_paise'] as num)], crore)),
            Panel(title: 'Open exceptions by type', child: openBy.isEmpty ? const Empty('None open.') : Column(children: [
              for (final e in openBy.entries) PillBar(text: label(e.key), value: e.value as num, max: d['open_exceptions'] as num, display: '${e.value}', red: true),
            ])),
            Panel(title: 'Balance by program', child: Column(children: [
              for (final p in byProgram) PillBar(text: p['name'], value: p['balance_paise'] as num, max: maxProg, display: inrShort(p['balance_paise']), red: (p['balance_paise'] as num) < 0),
            ])),
          ]);
        },
      );
}

// ------------------------------------------------------------------ students
class StudentsScreen extends StatefulWidget {
  final Me me;
  const StudentsScreen({super.key, required this.me});
  @override
  State<StudentsScreen> createState() => _StudentsState();
}

class _StudentsState extends State<StudentsScreen> {
  final _q = TextEditingController();
  String _term = '', _filter = '';
  Timer? _t;

  @override
  void dispose() { _t?.cancel(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final me = widget.me, money = me.seesMoney;
    final k = Palette.of(context);
    final canAdd = staffRoles.contains(me.role);
    return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 28), physics: const AlwaysScrollableScrollPhysics(), children: [
      PageTitle('Students', lead: money ? 'Search by id, name or email. Balance is positive when the student owes money.' : 'Students of your program, with enrollment status.'),
      const SizedBox(height: 12),
      Wrap(spacing: 10, runSpacing: 8, children: [
        if (canAdd) FilledButton.icon(style: FilledButton.styleFrom(minimumSize: const Size(0, 44)), onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const AddStudentScreen())), icon: const Icon(Icons.person_add_alt_1_rounded, size: 18), label: const Text('Add student')),
        if (money) ExportButton(name: 'studease-students', rows: () async {
          final all = await Api.instance.all('/students', {'q': _term, 'owing': _filter == 'owing' ? 'true' : null, 'flagged': _filter == 'flagged' ? 'true' : null});
          return [['Student', 'Name', 'Email', 'Program', 'Balance (paise)', 'Charged (paise)', 'Paid (paise)', 'Open exceptions'], for (final r in all) [r['student_id'], r['full_name'], r['email'], r['program_id'], r['balance_paise'], r['charged_paise'], r['paid_paise'], r['open_exceptions']]];
        }),
      ]),
      const SizedBox(height: 12),
      TextField(controller: _q, decoration: const InputDecoration(hintText: 'Search id, name or email', prefixIcon: Icon(Icons.search_rounded)), onChanged: (v) {
        _t?.cancel();
        _t = Timer(const Duration(milliseconds: 300), () { if (mounted) setState(() => _term = v.trim()); });
      }),
      if (money) Padding(padding: const EdgeInsets.only(top: 10), child: Wrap(spacing: 8, children: [
        for (final f in const [('', 'All'), ('owing', 'Owing money'), ('flagged', 'Open exception')]) ChoiceChip(label: Text(f.$2), selected: _filter == f.$1, onSelected: (_) => setState(() => _filter = f.$1),
            selectedColor: k.orange, labelStyle: TextStyle(color: _filter == f.$1 ? Colors.white : k.ink, fontWeight: FontWeight.w600)),
      ])),
      const SizedBox(height: 12),
      Panel(padding: const EdgeInsets.fromLTRB(16, 6, 16, 14), child: PagedList(
        path: '/students', query: {'q': _term, 'owing': _filter == 'owing' ? 'true' : null, 'flagged': _filter == 'flagged' ? 'true' : null}, empty: 'No student matches.',
        item: (c, s) => RowLine(
          onTap: () => Navigator.push(c, MaterialPageRoute(builder: (_) => StudentScreen(id: s['student_id'], me: me))),
          left: Text(s['full_name'], style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
          right: money ? Money(s['balance_paise']) : null,
          below: Row(children: [Expanded(child: muted(c, '${s['student_id']} · ${s['program_id']}')), if (money && (s['open_exceptions'] ?? 0) > 0) Stamp('${s['open_exceptions']} open', k.red)]),
        ),
      )),
    ]);
  }
}

class AddStudentScreen extends StatefulWidget {
  const AddStudentScreen({super.key});
  @override
  State<AddStudentScreen> createState() => _AddStudentState();
}

class _AddStudentState extends State<AddStudentScreen> {
  final _name = TextEditingController(), _gpa = TextEditingController(), _email = TextEditingController(), _pw = TextEditingController();
  String _program = 'PRG-01', _res = 'DOMESTIC', _band = 'MID', _waiver = '';
  bool _sports = false, _hostel = false, _login = false;
  List<(String, String)> _programs = const [('PRG-01', 'PRG-01')];

  @override
  void initState() {
    super.initState();
    Api.instance.get('/programs').then((d) { if (mounted) setState(() => _programs = [for (final p in ((d as J)['items'] as List).cast<J>()) (p['program_id'] as String, '${p['program_id']} ${p['name']}')]); }).catchError((_) {});
  }

  Future<void> _go() async {
    final gpa = double.tryParse(_gpa.text);
    if (_name.text.trim().length < 2) { toast(context, 'Enter the full name.'); return; }
    if (gpa == null || gpa < 0 || gpa > 10) { toast(context, 'GPA must be a number from 0 to 10.'); return; }
    if (_login && (_email.text.trim().isEmpty || _pw.text.length < 12)) { toast(context, 'A sign-in needs an email and a password of 12+ characters.'); return; }
    String? id;
    final ok = await attempt(context, () async {
      final r = await Api.instance.post('/students', {'full_name': _name.text.trim(), 'program_id': _program, 'residency': _res, 'gpa': gpa, 'income_band': _band, 'sports_quota': _sports,
        'hostel_resident': _hostel, 'waiver_type': _waiver.isEmpty ? null : _waiver, if (_login) 'login_email': _email.text.trim(), if (_login) 'login_password': _pw.text}, true) as J;
      id = r['student_id'];
    });
    if (ok && mounted) { toast(context, 'Added $id'); Navigator.pop(context); }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Add student')),
        body: ListPage([
          const PageTitle('Add a student', lead: 'Staff data entry. The student starts with a zero balance; enrol them in a term from their page.'),
          Panel(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Field('Full name', _name),
            Pick<String>('Program', _program, _programs, (v) => setState(() => _program = v)),
            Pick<String>('Residency', _res, const [('DOMESTIC', 'Domestic'), ('INTERNATIONAL', 'International')], (v) => setState(() => _res = v)),
            Field('GPA (0 to 10)', _gpa, number: true),
            Pick<String>('Income band', _band, const [('LOW', 'Low'), ('MID', 'Mid'), ('HIGH', 'High'), ('AFFLUENT', 'Affluent')], (v) => setState(() => _band = v)),
            Pick<String>('Waiver', _waiver, const [('', 'None'), ('STAFF_WARD', 'Staff ward'), ('SIBLING', 'Sibling'), ('HARDSHIP', 'Hardship')], (v) => setState(() => _waiver = v)),
            Check('Sports quota', _sports, (v) => setState(() => _sports = v)),
            Check('Hostel resident', _hostel, (v) => setState(() => _hostel = v)),
            Check('Also create a learner sign-in', _login, (v) => setState(() => _login = v)),
            if (_login) ...[Field('Sign-in email', _email, keyboard: TextInputType.emailAddress), Field('Initial password (12+ characters)', _pw, obscure: true)],
            const SizedBox(height: 8),
            SizedBox(width: double.infinity, child: SubmitButton('Add student', onPressed: _go)),
          ])),
        ]),
      );
}

// ------------------------------------------------------------------ fee schedules
class FeesScreen extends StatefulWidget {
  final Me me;
  const FeesScreen({super.key, required this.me});
  @override
  State<FeesScreen> createState() => _FeesState();
}

class _FeesState extends State<FeesScreen> {
  String _program = 'PRG-01', _term = 'TERM-2026-FALL';

  @override
  Widget build(BuildContext context) => Fetch<J>(
        load: () async => {'programs': await Api.instance.get('/programs'), 'terms': await Api.instance.get('/terms'), 'fees': await Api.instance.get('/fee-schedules', {'program_id': _program, 'term_id': _term})},
        refreshKey: '$_program$_term',
        builder: (c, d, reload) {
          final programs = ((d['programs'] as J)['items'] as List).cast<J>(), terms = ((d['terms'] as J)['items'] as List).cast<J>(), fees = ((d['fees'] as J)['items'] as List).cast<J>();
          final canEdit = widget.me.role == 'ACADEMIC_ADMIN' || widget.me.role == 'PLATFORM_ADMIN';
          return ListPage([
            PageTitle('Fee schedules', lead: 'Every price carries a version and an effective date. Only the version in force on the issue date is billed.',
                action: ExportButton(name: 'fee-schedule-$_program-$_term', rows: () async => [['Fee schedule', 'Fee', 'Applies to', 'Amount (paise)', 'Version', 'From', 'To', 'Scholarship eligible'], for (final f in fees) [f['fee_schedule_id'], f['fee_type'], f['applies_to'], f['amount_paise'], f['version'], f['effective_from'], f['effective_to'], f['scholarship_eligible']]])),
            Panel(child: Column(children: [
              Pick<String>('Program', _program, [for (final p in programs) (p['program_id'] as String, '${p['program_id']} ${p['name']}')], (v) => setState(() => _program = v)),
              Pick<String>('Term', _term, [for (final t in terms) (t['term_id'] as String, '${label(t['term_name'])} ${t['year']}')], (v) => setState(() => _term = v)),
            ])),
            if (canEdit) _NewFee(program: _program, term: _term),
            Panel(title: '${fees.length} fee versions', child: fees.isEmpty ? const Empty('No fees for this program and term.') : Column(children: [
              for (final f in fees) RowLine(
                left: Text('${label(f['fee_type'])}${f['applies_to'] == 'ALL' ? '' : ' (${label(f['applies_to'])})'}', style: const TextStyle(fontWeight: FontWeight.w700)),
                right: Money(f['amount_paise'], big: true),
                below: muted(c, 'v${f['version']} · from ${shortDate(f['effective_from'])} to ${shortDate(f['effective_to'])} · ${f['scholarship_eligible'] == true ? 'scholarship eligible' : 'no scholarship'}'),
              ),
            ])),
          ]);
        },
      );
}

class _NewFee extends StatefulWidget {
  final String program, term;
  const _NewFee({required this.program, required this.term});
  @override
  State<_NewFee> createState() => _NewFeeState();
}

class _NewFeeState extends State<_NewFee> {
  final _amount = TextEditingController();
  String _type = 'TUITION', _applies = 'ALL';
  DateTime? _from;
  bool _eligible = true;

  @override
  Widget build(BuildContext context) => Panel(title: 'Publish a new fee version', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        muted(context, 'For ${widget.program} in ${widget.term}. The previous version of the same fee closes the day before. Invoices already issued keep their old price.'),
        const SizedBox(height: 10),
        Pick<String>('Fee', _type, [for (final t in const ['TUITION', 'LAB', 'LIBRARY', 'TECHNOLOGY', 'EXAM', 'INTL_SURCHARGE', 'HOSTEL']) (t, label(t))], (v) => setState(() => _type = v)),
        Pick<String>('Applies to', _applies, const [('ALL', 'Everyone'), ('INTERNATIONAL', 'International'), ('HOSTEL', 'Hostel residents')], (v) => setState(() => _applies = v)),
        Field('Amount (rupees)', _amount, number: true),
        Padding(padding: const EdgeInsets.only(bottom: 12), child: OutlinedButton.icon(
          icon: const Icon(Icons.event_rounded, size: 18),
          label: Text(_from == null ? 'Choose the effective date' : 'Effective from ${shortDate(_from!.toIso8601String())}'),
          onPressed: () async {
            final d = await showDatePicker(context: context, initialDate: DateTime.now(), firstDate: DateTime(2020), lastDate: DateTime(2035));
            if (d != null) setState(() => _from = d);
          },
        )),
        Check('Scholarships may apply to this fee', _eligible, (v) => setState(() => _eligible = v)),
        const SizedBox(height: 8),
        SizedBox(width: double.infinity, child: SubmitButton('Publish version', onPressed: () async {
          final a = double.tryParse(_amount.text);
          if (a == null || a < 1) { toast(context, 'Enter an amount of at least Re 1.'); return; }
          if (_from == null) { toast(context, 'Choose the effective date.'); return; }
          final ok = await attempt(context, () async {
            final r = await Api.instance.post('/fee-schedules', {'program_id': widget.program, 'term_id': widget.term, 'fee_type': _type, 'applies_to': _applies, 'amount_paise': (a * 100).round(),
              'effective_from': _from!.toIso8601String().substring(0, 10), 'scholarship_eligible': _eligible}) as J;
            if (mounted) toast(context, 'Published ${r['fee_schedule_id']}');
          });
          if (ok) _amount.clear();
        })),
      ]));
}

// ------------------------------------------------------------------ scholarships
class AwardsScreen extends StatefulWidget {
  const AwardsScreen({super.key});
  @override
  State<AwardsScreen> createState() => _AwardsState();
}

class _AwardsState extends State<AwardsScreen> {
  String _scheme = '';
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return Fetch<J>(
      load: () async => {'schemes': await Api.instance.get('/scholarship-schemes'), 'summary': await Api.instance.get('/scholarships/summary')},
      builder: (c, d, reload) {
        final schemes = ((d['schemes'] as J)['items'] as List).cast<J>(), summary = ((d['summary'] as J)['items'] as List).cast<J>();
        final count = summary.fold<num>(0, (a, i) => a + (i['awards'] as num)), money = summary.fold<num>(0, (a, i) => a + (i['awarded_paise'] as num));
        return ListPage([
          PageTitle('Scholarships', lead: 'An award never exceeds the eligible fees. Ties between schemes go to the lowest priority number.',
              action: ExportButton(name: 'scholarship-awards', rows: () async {
                final all = await Api.instance.all('/scholarships', {'scheme_code': _scheme});
                return [['Award', 'Student', 'Scheme', 'Eligible fees (paise)', 'Awarded (paise)', 'Status'], for (final a in all) [a['scholarship_id'], a['student_id'], a['scheme_code'], a['eligible_fees_paise'], a['amount_paise'], a['status']]];
              })),
          Panel(title: 'Awards by scheme', child: Donut(slices: [for (final i in summary.where((i) => i['awards'] > 0)) Slice(i['name'], i['awards'] as num)], centre: '$count', sub: 'awards')),
          Panel(title: 'Money awarded by scheme', child: Donut(format: (n) => inrShort(n), slices: [for (final i in summary.where((i) => i['awarded_paise'] > 0)) Slice(i['name'], i['awarded_paise'] as num)], centre: crore(money).replaceAll(' ', ''), sub: 'awarded')),
          Panel(title: 'Schemes', child: Column(children: [
            for (final s in schemes) RowLine(
              left: Text('${s['priority']}. ${s['name']}', style: const TextStyle(fontWeight: FontWeight.w700)),
              right: Text(s['award_type'] == 'PERCENT' ? '${(s['award_bp'] as num) / 100}%' : inr(s['award_fixed_paise']), style: const TextStyle(fontWeight: FontWeight.w700, fontFeatures: tabular)),
              below: muted(c, 'Min GPA ${s['min_gpa']} · income ${s['required_income_band'] ?? 'any'}${s['requires_sports_quota'] == true ? ' · sports quota' : ''}${s['requires_international'] == true ? ' · international' : ''}'),
            ),
          ])),
          Panel(title: 'Awards', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Pick<String>('Scheme', _scheme, [('', 'All schemes'), for (final s in schemes) (s['scheme_code'] as String, s['name'] as String)], (v) => setState(() => _scheme = v)),
            PagedList(path: '/scholarships', query: {'scheme_code': _scheme}, empty: 'No awards.', item: (c, a) => RowLine(
              onTap: () => Navigator.push(c, MaterialPageRoute(builder: (_) => StudentScreen(id: a['student_id'], me: session.value!))),
              left: Text('${a['student_id']} · ${label(a['scheme_code'])}', style: const TextStyle(fontWeight: FontWeight.w600)),
              right: (a['amount_paise'] as num) > (a['eligible_fees_paise'] as num) ? Text(((a['amount_paise'] as num) / 100).toStringAsFixed(0), style: TextStyle(color: k.red, decoration: TextDecoration.lineThrough)) : Money(a['amount_paise']),
              below: Row(children: [statusStamp(c, a['status']), const SizedBox(width: 8), Expanded(child: muted(c, '${a['scholarship_id']} · eligible ${inr(a['eligible_fees_paise'])}'))]),
            )),
          ])),
        ]);
      },
    );
  }
}

// ------------------------------------------------------------------ exceptions
class ExceptionsScreen extends StatefulWidget {
  final Me me;
  const ExceptionsScreen({super.key, required this.me});
  @override
  State<ExceptionsScreen> createState() => _ExceptionsState();
}

class _ExceptionsState extends State<ExceptionsScreen> {
  String _status = 'OPEN', _type = '';
  J _counts = {}, _types = {};
  static const _typeList = ['ALLOC_EXCEEDS_PAYMENT', 'SCHOLARSHIP_EXCEEDS_ELIGIBLE', 'DUPLICATE_INVOICE', 'REFUND_EXCEEDS_NET_PAID', 'BALANCE_LEDGER_MISMATCH'];

  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Exceptions')),
      body: ListPage([
        PageTitle('Exceptions', lead: 'Found by the detectors from the books alone. Each case names what the rules expect and what the data holds.',
            action: ExportButton(name: 'exceptions', rows: () async {
              final all = await Api.instance.all('/exceptions', {'status': _status, 'exception_type': _type});
              return [['Case', 'Type', 'Student', 'Entity', 'Expected (paise)', 'Found (paise)', 'Suggested decision', 'Status', 'Note'], for (final e in all) [e['exception_id'], e['exception_type'], e['student_id'], e['entity_id'], e['expected_paise'], e['found_paise'], e['recommended_decision'], e['status'], e['note']]];
            })),
        if (_types.isNotEmpty) Panel(title: 'By type', child: Donut(slices: [for (final e in _types.entries) Slice(e.key, e.value as num)], centre: '${_types.values.fold<num>(0, (a, b) => a + (b as num))}', sub: label(_status))),
        Panel(child: Column(children: [
          Pick<String>('Status', _status, [for (final s in const ['OPEN', 'RESOLVED', 'DISMISSED']) (s, '${label(s)} (${_counts[s] ?? 0})')], (v) => setState(() => _status = v)),
          Pick<String>('Type', _type, [('', 'All types'), for (final t in _typeList) (t, label(t))], (v) => setState(() => _type = v)),
        ])),
        Panel(padding: const EdgeInsets.fromLTRB(16, 6, 16, 14), child: PagedList(
          path: '/exceptions', query: {'status': _status, 'exception_type': _type}, empty: 'Nothing here.',
          onFirst: (p) { WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted) setState(() { _counts = (p['counts'] as J?) ?? {}; _types = (p['types'] as J?) ?? {}; }); }); },
          item: (c, e) => _ExceptionRow(e: e, canResolve: widget.me.role == 'SUPPORT', k: k, me: widget.me),
        )),
      ]),
    );
  }
}

class _ExceptionRow extends StatefulWidget {
  final J e;
  final bool canResolve;
  final Palette k;
  final Me me;
  const _ExceptionRow({required this.e, required this.canResolve, required this.k, required this.me});
  @override
  State<_ExceptionRow> createState() => _ExceptionRowState();
}

class _ExceptionRowState extends State<_ExceptionRow> {
  bool _open = false;
  final _note = TextEditingController();

  Future<void> _close(String status) async {
    if (_note.text.trim().isEmpty) { toast(context, 'A note is required.'); return; }
    final ok = await attempt(context, () async { await Api.instance.post('/exceptions/${widget.e['exception_id']}/resolve', {'status': status, 'note': _note.text.trim()}); });
    if (ok && mounted) toast(context, status == 'RESOLVED' ? 'Resolved' : 'Dismissed');
  }

  @override
  Widget build(BuildContext context) {
    final e = widget.e;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      RowLine(
        onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => StudentScreen(id: e['student_id'], me: widget.me))),
        left: Text('${label(e['exception_type'])}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
        right: statusStamp(context, e['status']),
        below: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          muted(context, '${e['exception_id']} · ${e['student_id']}'),
          const SizedBox(height: 4),
          Wrap(spacing: 14, children: [
            Text('Expected ${inr(e['expected_paise'])}', style: const TextStyle(fontSize: 13)),
            Text('Found ${inr(e['found_paise'])}', style: TextStyle(fontSize: 13, color: e['found_paise'] != e['expected_paise'] ? widget.k.red : null, decoration: e['found_paise'] != e['expected_paise'] ? TextDecoration.lineThrough : null)),
          ]),
          muted(context, 'Suggested: ${label(e['recommended_decision'])}'),
          if (e['status'] == 'OPEN' && widget.canResolve) TextButton(onPressed: () => setState(() => _open = !_open), child: Text(_open ? 'Close' : 'Review')),
        ]),
      ),
      if (_open) Padding(padding: const EdgeInsets.only(bottom: 10), child: Column(children: [
        TextField(controller: _note, maxLength: 400, decoration: const InputDecoration(hintText: 'Note (required)')),
        Row(children: [Expanded(child: SubmitButton('Resolve', onPressed: () => _close('RESOLVED'))), const SizedBox(width: 10), Expanded(child: SubmitButton('Dismiss', outlined: true, onPressed: () => _close('DISMISSED')))]),
      ])),
    ]);
  }
}

// ------------------------------------------------------------------ users
class UsersScreen extends StatefulWidget {
  const UsersScreen({super.key});
  @override
  State<UsersScreen> createState() => _UsersState();
}

class _UsersState extends State<UsersScreen> {
  final _email = TextEditingController(), _pw = TextEditingController(), _student = TextEditingController();
  String _role = 'SUPPORT', _program = 'PRG-01';

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Users')),
        body: Fetch<J>(
          load: () async => {'users': await Api.instance.get('/admin/users'), 'programs': await Api.instance.get('/programs')},
          builder: (c, d, reload) {
            final users = ((d['users'] as J)['items'] as List).cast<J>(), programs = ((d['programs'] as J)['items'] as List).cast<J>();
            return ListPage([
              PageTitle('Users', lead: 'Who can sign in, and as what. A disabled account is refused on its next request, even with a valid token.',
                  action: ExportButton(name: 'users', rows: () async => [['Id', 'Email', 'Role', 'Student', 'Program', 'Enabled'], for (final u in users) [u['app_user_id'], u['email'], u['role'], u['student_id'], u['program_id'], u['enabled']]])),
              Panel(title: 'Create an account', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Field('Email', _email, keyboard: TextInputType.emailAddress),
                Field('Password (12+ characters)', _pw, obscure: true),
                Pick<String>('Role', _role, const [('SUPPORT', 'Support'), ('ACADEMIC_ADMIN', 'Academic admin'), ('PLATFORM_ADMIN', 'Platform admin'), ('INSTRUCTOR', 'Instructor'), ('LEARNER', 'Learner')], (v) => setState(() => _role = v)),
                if (_role == 'LEARNER') Field('Student id', _student, hint: 'STU-000001'),
                if (_role == 'INSTRUCTOR') Pick<String>('Program', _program, [for (final p in programs) (p['program_id'] as String, '${p['program_id']} ${p['name']}')], (v) => setState(() => _program = v)),
                SizedBox(width: double.infinity, child: SubmitButton('Create account', onPressed: () async {
                  if (_email.text.trim().isEmpty || _pw.text.length < 12) { toast(c, 'Enter an email and a password of 12+ characters.'); return; }
                  final ok = await attempt(c, () async {
                    await Api.instance.post('/admin/users', {'email': _email.text.trim(), 'password': _pw.text, 'role': _role, if (_role == 'LEARNER') 'student_id': _student.text.trim(), if (_role == 'INSTRUCTOR') 'program_id': _program});
                  });
                  if (ok) { _email.clear(); _pw.clear(); _student.clear(); if (c.mounted) toast(c, 'Account created'); }
                })),
              ])),
              Panel(title: '${users.length} accounts', child: Column(children: [
                for (final u in users) RowLine(
                  left: Text(u['email'], style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
                  right: statusStamp(c, u['enabled'] == true ? 'COMPLETED' : 'REVOKED'),
                  below: Row(children: [
                    Expanded(child: muted(c, '${u['app_user_id']} · ${label(u['role'])} · ${u['student_id'] ?? u['program_id'] ?? '-'}')),
                    TextButton(onPressed: () async {
                      final ok = await attempt(c, () async { await Api.instance.post('/admin/users/${u['app_user_id']}/enabled', {'enabled': !(u['enabled'] == true)}); });
                      if (ok) await reload();
                    }, child: Text(u['enabled'] == true ? 'Disable' : 'Enable')),
                  ]),
                ),
              ])),
            ]);
          },
        ),
      );
}

// ------------------------------------------------------------------ data quality
class QualityScreen extends StatelessWidget {
  const QualityScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Data quality')),
        body: Fetch<J>(
          load: () async => await Api.instance.get('/quality') as J,
          builder: (c, q, reload) {
            final v = q['validation'] as J?, e = q['evaluation'] as J?, r = q['repro'] as J?;
            final det = e?['detection'] as J?;
            final k = Palette.of(c);
            return ListPage([
              PageTitle('Data quality', lead: 'Reports for the ${q['scale']} dataset, produced by the generator and the evaluation run, not by this page.'),
              MetricGrid([
                Metric(kind: Kind.hero, title: 'Validation', value: v == null ? '-' : (v['ok'] == true ? 'Passed' : 'Failed'), note: v == null ? 'No report' : '${v['labels']} labelled cases'),
                Metric(title: 'Reproducible', value: r == null ? '-' : (r['identical'] == true ? 'Yes' : 'No'), note: r == null ? 'No report' : 'Two runs, identical checksums'),
                Metric(kind: Kind.ink, title: 'Detection F1', value: '${det?['macro_f1'] ?? '-'}', note: det == null ? 'No report' : 'precision ${det['overall']['precision']}, recall ${det['overall']['recall']}'),
                Metric(kind: Kind.mint, title: 'Reconciliation rate', value: e == null ? '-' : '${((e['business']['reconciliation_rate'] as num) * 100).toStringAsFixed(1)}%', note: 'Students whose three balances agree'),
              ]),
              if (v != null) Panel(title: 'Validation checks', child: Column(children: [
                for (final ch in (v['checks'] as List).cast<J>()) RowLine(
                  left: Text('${ch['id']} ${ch['name']}', style: const TextStyle(fontSize: 13.5)),
                  right: (ch['unexpected'] as num) > 0 ? Stamp('${ch['unexpected']} unexpected', k.red) : Stamp('ok', k.green),
                  below: muted(c, '${ch['rows_checked']} rows · ${ch['violations']} violations · ${ch['expected']} explained by a label'),
                ),
              ])),
              if (det != null) Panel(title: 'Detection against ground truth', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                for (final t in (det['per_type'] as Map).entries) RowLine(
                  left: Text(label(t.key), style: const TextStyle(fontWeight: FontWeight.w600)),
                  right: Text('F1 ${t.value['f1']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                  below: muted(c, 'labelled ${t.value['labelled']} · reported ${t.value['reported']} · precision ${t.value['precision']} · recall ${t.value['recall']}'),
                ),
                const SizedBox(height: 8),
                muted(c, 'The detectors never see the ground truth, but they recompute the same rules the generator used, so a perfect score is expected by construction. It proves the rules are implemented consistently, not that they would find unknown faults in real data.'),
              ])),
            ]);
          },
        ),
      );
}
