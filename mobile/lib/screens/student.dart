import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../theme.dart';
import '../ui/fetch.dart';
import '../ui/kit.dart';
import 'invoice.dart';

typedef J = Map<String, dynamic>;

/// A student's account: balance cards, charts, the three-way reconciliation, payment, profile, enrolments,
/// invoices, ledger and history. Learners see their own; staff open any student; instructors see enrolment status only.
class StudentScreen extends StatelessWidget {
  final String id;
  final Me me;
  final bool own;
  const StudentScreen({super.key, required this.id, required this.me, this.own = false});

  Future<J> _load() async {
    final detail = await Api.instance.get('/students/$id') as J;
    J? ledger, events;
    if (me.seesMoney) {
      ledger = await Api.instance.get('/students/$id/ledger') as J;
      events = await Api.instance.get('/students/$id/events') as J;
    }
    return {'detail': detail, 'ledger': ledger, 'events': events};
  }

  @override
  Widget build(BuildContext context) {
    final body = Fetch<J>(load: _load, builder: (c, d, reload) => _Body(data: d, id: id, me: me, own: own, reload: reload));
    if (own) return body;
    return Scaffold(appBar: AppBar(title: const Text('Student')), body: body);
  }
}

class _Body extends StatelessWidget {
  final J data;
  final String id;
  final Me me;
  final bool own;
  final Future<void> Function() reload;
  const _Body({required this.data, required this.id, required this.me, required this.own, required this.reload});

  @override
  Widget build(BuildContext context) {
    final d = data['detail'] as J, s = d['student'] as J, b = d['balance'] as J?;
    final invoices = (d['invoices'] as List?)?.cast<J>() ?? const <J>[];
    final enrollments = (d['enrollments'] as List).cast<J>();
    final ledger = (data['ledger']?['items'] as List?)?.cast<J>() ?? const <J>[];
    final events = (data['events']?['items'] as List?)?.cast<J>() ?? const <J>[];
    final role = me.role;
    final canPay = own || role == 'SUPPORT' || role == 'PLATFORM_ADMIN';
    final canAward = role == 'ACADEMIC_ADMIN' || role == 'PLATFORM_ADMIN';
    final canWithdraw = own || canAward;
    final canEnrol = role == 'ACADEMIC_ADMIN' || role == 'SUPPORT' || role == 'PLATFORM_ADMIN';
    final k = Palette.of(context);
    return ListPage([
      PageTitle(own ? 'My account' : s['full_name'], lead: '${s['full_name']} · ${s['student_id']} · ${s['program_name']} · ${label(s['residency'])} · GPA ${s['gpa']}',
          action: me.seesMoney ? ExportButton(name: 'statement-$id', rows: () async => [
            ['Date', 'Type', 'Source', 'Amount (paise)', 'Running balance (paise)'],
            for (final e in ledger) [e['posted_on'], e['entry_type'], e['source_id'], e['amount_paise'], e['running_balance_paise']],
          ]) : null),
      if (b != null) MetricGrid([
        Metric(kind: Kind.hero, title: b['stated'] > 0 ? 'You owe' : b['stated'] < 0 ? 'Credit held' : 'Settled', value: inr((b['stated'] as num).abs()), note: 'as of ${shortDate(b['as_of'])}'),
        Metric(title: 'Charged', value: inr(b['charged_paise']), note: '${inr(-(b['credits_paise'] as num))} in waivers, awards and adjustments'),
        Metric(kind: Kind.ink, title: 'Paid', value: inr(-(b['paid_paise'] as num)), note: '${inr(b['refunded_paise'])} refunded'),
        Metric(kind: Kind.mint, title: 'Invoices', value: '${invoices.length}', note: '${invoices.where((i) => i['status'] == 'OVERDUE').length} overdue'),
      ]),
      if (b != null) Panel(title: 'Money by kind', child: _kinds(ledger)),
      if (b != null) Panel(title: 'Balance over time', child: _balanceLine(context, ledger)),
      if (b != null) _Three(b: b),
      if (canPay) _PayForm(studentId: id, own: own, done: reload),
      if (!me.instructor) _ProfileForm(key: ValueKey('${s['full_name']}${s['gpa']}${s['income_band']}${s['hostel_resident']}'), student: s, own: own, done: reload),
      if (canAward) _AwardForm(studentId: id, terms: [for (final e in enrollments.where((e) => e['status'] == 'ENROLLED')) (e['term_id'] as String, label(e['term_name']))], done: reload),
      if (canEnrol && !own) _EnrolForm(studentId: id, done: reload),
      Panel(title: 'Enrollments', child: enrollments.isEmpty ? const Empty('No enrollments yet.') : Column(children: [
        for (final e in enrollments) RowLine(
          left: Text('${label(e['term_name'])}  ·  ${e['enrollment_id']}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
          right: statusStamp(context, e['status']),
          below: Row(children: [
            Expanded(child: muted(context, 'Left ${shortDate(e['left_on'])}')),
            if (canWithdraw && e['status'] == 'ENROLLED') _WithdrawButton(id: e['enrollment_id'], own: own, done: reload),
          ]),
        ),
      ])),
      if (me.seesMoney) Panel(title: 'Invoices', child: invoices.isEmpty ? const Empty('No invoices yet.') : Column(children: [
        for (final i in invoices) RowLine(
          onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => InvoiceScreen(id: i['invoice_id']))),
          left: Text(i['invoice_id'], style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13.5)),
          right: Money(i['total_paise'], big: true),
          below: Row(children: [
            statusStamp(context, i['status']), const SizedBox(width: 8),
            Expanded(child: muted(context, 'Issued ${shortDate(i['issue_date'])} · due ${shortDate(i['due_date'])}')),
            IconButton(tooltip: 'Download invoice', visualDensity: VisualDensity.compact, icon: const Icon(Icons.download_rounded, size: 22),
                onPressed: () => downloadInvoice(context, i['invoice_id'])),
          ]),
        ),
      ])),
      if (me.seesMoney) _Ledger(items: ledger),
      if (me.seesMoney && events.isNotEmpty) Panel(title: 'State history', child: Column(children: [
        for (final e in events.reversed.take(25)) RowLine(
          left: Text('${e['entity_id']}', style: TextStyle(color: k.muted, fontSize: 12.5)),
          right: Text(shortDate(e['occurred_on']), style: TextStyle(color: k.muted, fontSize: 12.5)),
          below: Text('${e['from_status'] == null ? '-' : label(e['from_status'])}  →  ${label(e['to_status'])}   ·   ${e['actor']}', style: const TextStyle(fontSize: 13)),
        ),
        if (events.length > 25) Padding(padding: const EdgeInsets.only(top: 8), child: muted(context, 'Latest 25 of ${events.length}. Export the account to get everything.')),
      ])),
    ]);
  }

  Widget _kinds(List<J> ledger) {
    const kinds = [('Charged', ['CHARGE', 'LATE_FEE']), ('Paid', ['PAYMENT']), ('Awards and waivers', ['SCHOLARSHIP', 'WAIVER']), ('Refunded', ['REFUND']), ('Adjustments', ['ADJUSTMENT'])];
    final slices = <Slice>[];
    for (final (name, types) in kinds) {
      final v = ledger.where((e) => types.contains(e['entry_type'])).fold<num>(0, (a, e) => a + (e['amount_paise'] as num)).abs();
      if (v > 0) slices.add(Slice(name, v));
    }
    return Column(children: [
      Donut(slices: slices, centre: '${ledger.length}', sub: 'entries', format: (n) => inrShort(n)),
      const SizedBox(height: 10),
      const Text('Each slice adds up the ledger entries of one kind: fees charged, payments made, awards and waivers that reduced the bill, and refunds paid back.', style: TextStyle(fontSize: 12.5)),
    ]);
  }

  Widget _balanceLine(BuildContext context, List<J> ledger) {
    final k = Palette.of(context);
    if (ledger.length < 2) return const Empty('The chart appears after the first few ledger entries.');
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      muted(context, 'Each dot is one ledger entry. The line climbs when a fee is charged (red dot) and drops when you pay or receive an award (green dot). Above the zero line you owe money; below it you hold credit. Touch the chart to read an entry.'),
      const SizedBox(height: 8),
      LineChart(
        labels: [for (final e in ledger) shortDate(e['posted_on'])],
        series: [LineSeries('Balance you owe', k.orange, [for (final e in ledger) (e['running_balance_paise'] as num).toDouble()])],
        format: (n) => inrShort(n),
        dotColors: [for (final e in ledger) (e['amount_paise'] as num) > 0 ? k.red : k.green],
        tips: [for (final e in ledger) '${shortDate(e['posted_on'])}: ${label(e['entry_type'])} ${inr(e['amount_paise'], sign: true)}, balance ${inr(e['running_balance_paise'])}'],
      ),
    ]);
  }
}

class _Three extends StatelessWidget {
  final J b;
  const _Three({required this.b});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final ok = b['reconciled'] == true;
    Widget line(String t, num v) => RowLine(
          left: Text(t, style: const TextStyle(fontSize: 14)),
          right: Text(inr(v), style: TextStyle(fontFeatures: tabular, fontWeight: FontWeight.w600, color: v == b['stated'] ? k.ink : k.red, decoration: v == b['stated'] ? null : TextDecoration.lineThrough, decorationColor: k.red)),
        );
    return Panel(
      title: 'Three routes to one number',
      trailing: Stamp(ok ? 'Reconciled' : 'Does not reconcile', ok ? k.green : k.red),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        line('Stated balance', b['stated']), line('Sum of ledger entries', b['ledger']), line('Invoices minus payments plus refunds', b['from_documents']),
        const SizedBox(height: 8),
        muted(context, 'When the routes differ, the exception queue raises the case for review.'),
      ]),
    );
  }
}

class _PayForm extends StatefulWidget {
  final String studentId;
  final bool own;
  final Future<void> Function() done;
  const _PayForm({required this.studentId, required this.own, required this.done});
  @override
  State<_PayForm> createState() => _PayFormState();
}

class _PayFormState extends State<_PayForm> {
  final _amount = TextEditingController(), _ref = TextEditingController();
  String _method = 'UPI';
  String? _msg;

  Future<void> _go() async {
    final a = double.tryParse(_amount.text);
    if (a == null || a <= 0) { toast(context, 'Enter an amount in rupees.'); return; }
    if (_ref.text.trim().isEmpty) { toast(context, 'Enter a payment reference.'); return; }
    final ok = await attempt(context, () async {
      final r = await Api.instance.post(widget.own ? '/me/payments' : '/payments',
          {if (!widget.own) 'student_id': widget.studentId, 'amount_paise': (a * 100).round(), 'method': _method, 'reference': _ref.text.trim()}, true) as J;
      _msg = 'Allocated to the oldest due lines; ${inr(r['unapplied_paise'])} left as credit.';
      if (mounted) toast(context, 'Recorded ${(r['payment'] as J)['payment_id']}');
    });
    if (ok) { _amount.clear(); _ref.clear(); await widget.done(); }
  }

  @override
  Widget build(BuildContext context) {
    final methods = widget.own ? const ['UPI', 'CARD', 'NETBANKING'] : const ['UPI', 'CARD', 'NETBANKING', 'BANK_TRANSFER', 'CASH', 'CHEQUE'];
    return Panel(title: widget.own ? 'Pay now' : 'Record a payment', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Field('Amount (rupees)', _amount, number: true),
      Pick<String>('Method', _method, [for (final m in methods) (m, m == 'UPI' ? 'UPI' : label(m))], (v) => setState(() => _method = v)),
      Field('Reference', _ref),
      if (_msg != null) Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(_msg!, style: TextStyle(color: Palette.of(context).green, fontWeight: FontWeight.w600))),
      SizedBox(width: double.infinity, child: SubmitButton(widget.own ? 'Pay' : 'Record and allocate', onPressed: _go)),
    ]));
  }
}

class _ProfileForm extends StatefulWidget {
  final J student;
  final bool own;
  final Future<void> Function() done;
  const _ProfileForm({super.key, required this.student, required this.own, required this.done});
  @override
  State<_ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends State<_ProfileForm> {
  late final _name = TextEditingController(text: widget.student['full_name']);
  late final _gpa = TextEditingController(text: '${widget.student['gpa']}');
  late String _band = widget.student['income_band'], _res = widget.student['residency'];
  late bool _sports = widget.student['sports_quota'] == true, _hostel = widget.student['hostel_resident'] == true;

  Future<void> _go() async {
    final gpa = double.tryParse(_gpa.text);
    if (!widget.own && (gpa == null || gpa < 0 || gpa > 10)) { toast(context, 'GPA must be a number from 0 to 10.'); return; }
    if (_name.text.trim().length < 2) { toast(context, 'Enter a name.'); return; }
    final ok = await attempt(context, () async {
      if (widget.own) {
        await Api.instance.post('/me/profile', {'full_name': _name.text.trim(), 'hostel_resident': _hostel});
      } else {
        await Api.instance.post('/students/${widget.student['student_id']}/profile', {'full_name': _name.text.trim(), 'gpa': gpa, 'income_band': _band, 'residency': _res, 'sports_quota': _sports, 'hostel_resident': _hostel});
      }
    });
    if (ok) { if (mounted) toast(context, 'Profile saved'); await widget.done(); }
  }

  @override
  Widget build(BuildContext context) => Panel(title: widget.own ? 'My details' : 'Edit details', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Field('Full name', _name),
        if (!widget.own) ...[
          Field('GPA', _gpa, number: true),
          Pick<String>('Income band', _band, const [('LOW', 'Low'), ('MID', 'Mid'), ('HIGH', 'High'), ('AFFLUENT', 'Affluent')], (v) => setState(() => _band = v)),
          Pick<String>('Residency', _res, const [('DOMESTIC', 'Domestic'), ('INTERNATIONAL', 'International')], (v) => setState(() => _res = v)),
          Check('Sports quota', _sports, (v) => setState(() => _sports = v)),
        ],
        Check('Hostel resident', _hostel, (v) => setState(() => _hostel = v)),
        if (widget.own) muted(context, 'GPA, income band and residency decide scholarships, so staff maintain them.'),
        const SizedBox(height: 10),
        SizedBox(width: double.infinity, child: SubmitButton('Save details', onPressed: _go, outlined: true)),
      ]));
}

const schemes = [('MERIT_GOLD', 'Merit gold'), ('MERIT_SILVER', 'Merit silver'), ('NEED_BASED', 'Need based'), ('SPORTS', 'Sports'), ('INTL_EXCELLENCE', 'International excellence')];

class _AwardForm extends StatefulWidget {
  final String studentId;
  final List<(String, String)> terms;
  final Future<void> Function() done;
  const _AwardForm({required this.studentId, required this.terms, required this.done});
  @override
  State<_AwardForm> createState() => _AwardFormState();
}

class _AwardFormState extends State<_AwardForm> {
  String? _term;
  String _scheme = 'MERIT_GOLD';

  @override
  Widget build(BuildContext context) {
    if (widget.terms.isEmpty) return const SizedBox();
    _term ??= widget.terms.first.$1;
    return Panel(title: 'Assign a scholarship', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      muted(context, "The scheme's criteria still apply: a student who does not qualify is refused, with the reason."),
      const SizedBox(height: 10),
      Pick<String>('Term', _term!, widget.terms, (v) => setState(() => _term = v)),
      Pick<String>('Scheme', _scheme, schemes, (v) => setState(() => _scheme = v)),
      SizedBox(width: double.infinity, child: SubmitButton('Assign', outlined: true, onPressed: () async {
        final ok = await attempt(context, () async {
          final r = await Api.instance.post('/students/${widget.studentId}/scholarships', {'term_id': _term, 'scheme_code': _scheme}, true) as J;
          if (mounted) toast(context, 'Awarded ${(r['scholarship'] as J)['scholarship_id']}');
        });
        if (ok) await widget.done();
      })),
    ]));
  }
}

class _EnrolForm extends StatefulWidget {
  final String studentId;
  final Future<void> Function() done;
  const _EnrolForm({required this.studentId, required this.done});
  @override
  State<_EnrolForm> createState() => _EnrolFormState();
}

class _EnrolFormState extends State<_EnrolForm> {
  List<(String, String)> _terms = [];
  String? _term;
  @override
  void initState() {
    super.initState();
    Api.instance.get('/terms').then((d) { if (mounted) setState(() { _terms = [for (final t in ((d as J)['items'] as List).cast<J>()) (t['term_id'] as String, '${label(t['term_name'])} ${t['year']}')]; _term = _terms.isEmpty ? null : _terms.last.$1; }); }).catchError((_) {});
  }

  @override
  Widget build(BuildContext context) {
    if (_terms.isEmpty) return const SizedBox();
    return Panel(title: 'Enrol in a term', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      muted(context, 'Bills the program fees for the term. Scholarships are assigned separately.'),
      const SizedBox(height: 10),
      Pick<String>('Term', _term!, _terms, (v) => setState(() => _term = v)),
      SizedBox(width: double.infinity, child: SubmitButton('Enrol and generate invoice', outlined: true, onPressed: () async {
        final ok = await attempt(context, () async { await Api.instance.post('/students/${widget.studentId}/enroll', {'term_id': _term, 'applications': []}, true); });
        if (ok) { if (mounted) toast(context, 'Enrolled. The invoice is ready.'); await widget.done(); }
      })),
    ]));
  }
}

class _WithdrawButton extends StatelessWidget {
  final String id;
  final bool own;
  final Future<void> Function() done;
  const _WithdrawButton({required this.id, required this.own, required this.done});
  @override
  Widget build(BuildContext context) => TextButton(
        style: TextButton.styleFrom(foregroundColor: Palette.of(context).red),
        onPressed: () async {
          final yes = await showDialog<bool>(context: context, builder: (c) => AlertDialog(
            title: Text('Withdraw $id?'), content: const Text('Fees are adjusted and any overpayment is refunded.'),
            actions: [TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Keep')), FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Withdraw'))],
          ));
          if (yes != true || !context.mounted) return;
          final ok = await attempt(context, () async { await Api.instance.post(own ? '/me/enrollments/$id/withdraw' : '/enrollments/$id/withdraw', {}); });
          if (ok) { if (context.mounted) toast(context, 'Withdrawal recorded; fees adjusted'); await done(); }
        },
        child: const Text('Withdraw'),
      );
}

class _Ledger extends StatefulWidget {
  final List<J> items;
  const _Ledger({required this.items});
  @override
  State<_Ledger> createState() => _LedgerState();
}

class _LedgerState extends State<_Ledger> {
  bool _all = false;
  @override
  Widget build(BuildContext context) {
    final rows = _all ? widget.items : widget.items.reversed.take(15).toList();
    return Panel(title: 'Ledger', child: widget.items.isEmpty ? const Empty('No entries yet.') : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      for (final e in rows) RowLine(
        left: Text('${label(e['entry_type'])}  ·  ${shortDate(e['posted_on'])}', style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        right: Money(e['amount_paise'], sign: true, color: (e['amount_paise'] as num) < 0 ? Palette.of(context).green : null),
        below: Row(children: [Expanded(child: muted(context, '${e['source_id']}')), Text('Running ${inr(e['running_balance_paise'])}', style: TextStyle(color: Palette.of(context).muted, fontSize: 12.5, fontFeatures: tabular))]),
      ),
      if (widget.items.length > 15) TextButton(onPressed: () => setState(() => _all = !_all), child: Text(_all ? 'Show latest 15' : 'Show all ${widget.items.length} entries')),
    ]));
  }
}
