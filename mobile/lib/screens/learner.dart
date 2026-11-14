import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../theme.dart';
import '../ui/fetch.dart';
import '../ui/kit.dart';
import 'invoice.dart';

typedef J = Map<String, dynamic>;

/// Enrol in a term: the fees you will be billed, which scholarships you meet (and why not), then apply.
class EnrollScreen extends StatefulWidget {
  const EnrollScreen({super.key});
  @override
  State<EnrollScreen> createState() => _EnrollState();
}

class _EnrollState extends State<EnrollScreen> {
  final Map<String, Set<String>> _pick = {};
  int _v = 0;

  @override
  Widget build(BuildContext context) => Fetch<J>(
        refreshKey: _v,
        load: () async => await Api.instance.get('/me/enrollable') as J,
        builder: (c, d, reload) {
          final items = (d['items'] as List).cast<J>();
          final k = Palette.of(c);
          if (items.isEmpty) return ListPage([const PageTitle('Enrol', lead: 'Choose a term. You are billed the fees for your program.'), const Panel(child: Empty('There is no open term to enrol in: you are already enrolled in every term that is still running.'))]);
          return ListPage([
            const PageTitle('Enrol', lead: 'Choose a term. You are billed the fees for your program, and each scheme you apply for is judged against its published criteria.'),
            for (final o in items) ...[
              MetricGrid([
                Metric(kind: Kind.hero, title: 'Term', value: label((o['term'] as J)['term_name']), note: '${shortDate((o['term'] as J)['start_date'])} to ${shortDate((o['term'] as J)['end_date'])}'),
                Metric(title: 'Fees', value: inr(o['total_paise']), note: '${(o['lines'] as List).length} lines, due ${shortDate((o['term'] as J)['due_date'])}'),
                Metric(kind: Kind.ink, title: 'Scholarship-eligible fees', value: inr(o['eligible_fees_paise']), note: 'The base awards are calculated on'),
              ]),
              Panel(title: 'What you will be billed', child: Column(children: [
                for (final l in (o['lines'] as List).cast<J>()) RowLine(left: Text(l['description']), right: Money(l['amount_paise'], sign: (l['amount_paise'] as num) < 0)),
                RowLine(left: const Text('Total', style: TextStyle(fontWeight: FontWeight.w800)), right: Money(o['total_paise'], big: true)),
              ])),
              Panel(title: 'Apply for scholarships', child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                muted(c, 'Only the single largest award you qualify for is granted. Schemes you do not meet are shown with the reason.'),
                const SizedBox(height: 8),
                for (final s in (o['schemes'] as List).cast<J>()) Opacity(
                  opacity: s['meets_criteria'] == true ? 1 : .6,
                  child: Container(
                    margin: const EdgeInsets.only(top: 8),
                    decoration: BoxDecoration(border: Border.all(color: k.rule), borderRadius: BorderRadius.circular(16)),
                    child: CheckboxListTile(
                      value: (_pick[(o['term'] as J)['term_id']] ?? {}).contains(s['scheme_code']),
                      onChanged: s['meets_criteria'] == true ? (v) => setState(() {
                            final set = _pick.putIfAbsent((o['term'] as J)['term_id'], () => {});
                            v == true ? set.add(s['scheme_code']) : set.remove(s['scheme_code']);
                          }) : null,
                      controlAffinity: ListTileControlAffinity.leading,
                      title: Text(s['name'], style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
                      subtitle: Padding(padding: const EdgeInsets.only(top: 4), child: Wrap(spacing: 8, crossAxisAlignment: WrapCrossAlignment.center, children: s['meets_criteria'] == true
                          ? [Stamp('Meets criteria', k.green), Text('worth up to ${inr(s['would_award_paise'])}', style: TextStyle(color: k.muted, fontSize: 12.5))]
                          : [Stamp('Not eligible', k.muted), Text(label(s['reason']), style: TextStyle(color: k.muted, fontSize: 12.5))])),
                    ),
                  ),
                ),
              ])),
              SizedBox(width: double.infinity, child: SubmitButton('Enrol in ${label((o['term'] as J)['term_name'])} and generate my invoice', onPressed: () async {
                final tid = (o['term'] as J)['term_id'] as String;
                final ok = await attempt(c, () async {
                  final r = await Api.instance.post('/me/enroll', {'term_id': tid, 'applications': (_pick[tid] ?? {}).toList()}, true) as J;
                  if (c.mounted) toast(c, r['scholarship'] != null ? 'Enrolled. ${label((r['scholarship'] as J)['scheme_code'])} awarded: ${inr((r['scholarship'] as J)['amount_paise'])}' : 'Enrolled. Your invoice is ready.');
                });
                if (ok) setState(() => _v++);
              })),
            ],
          ]);
        },
      );
}

class MyAwardsScreen extends StatelessWidget {
  const MyAwardsScreen({super.key});
  @override
  Widget build(BuildContext context) => Fetch<J>(
        load: () async => await Api.instance.get('/me/scholarships') as J,
        builder: (c, d, reload) {
          final awards = (d['awards'] as List).cast<J>(), decisions = (d['decisions'] as List).cast<J>();
          final total = awards.fold<num>(0, (a, e) => a + (e['amount_paise'] as num));
          return ListPage([
            PageTitle('My scholarships', lead: 'Awards are capped at the scholarship-eligible fees. Each decision records the GPA and income band it was based on.',
                action: ExportButton(name: 'my-scholarship-decisions', rows: () async => [['Decided on', 'Scheme', 'Decision', 'Reason', 'GPA at decision'], for (final x in decisions) [x['decided_on'], x['scheme_name'], x['decision'], x['reason_code'], x['gpa_at_decision']]])),
            MetricGrid([
              Metric(kind: Kind.hero, title: 'Awards', value: '${awards.length}', note: 'Currently held or applied'),
              Metric(title: 'Total awarded', value: inr(total)),
              Metric(kind: Kind.ink, title: 'Decisions', value: '${decisions.length}', note: '${decisions.where((x) => x['decision'] == 'ELIGIBLE').length} eligible'),
            ]),
            Panel(title: 'Awards', child: awards.isEmpty ? const Empty('No awards yet. Enrol and apply to be considered.') : Column(children: [
              for (final a in awards) RowLine(
                onTap: a['invoice_id'] == null ? null : () => Navigator.push(c, MaterialPageRoute(builder: (_) => InvoiceScreen(id: a['invoice_id']))),
                left: Text(a['scheme_name'], style: const TextStyle(fontWeight: FontWeight.w700)),
                right: Money(a['amount_paise'], big: true),
                below: Row(children: [statusStamp(c, a['status']), const SizedBox(width: 8), Expanded(child: muted(c, '${a['scholarship_id']} · eligible fees ${inr(a['eligible_fees_paise'])}'))]),
              ),
            ])),
            Panel(title: 'Every decision', child: decisions.isEmpty ? const Empty('No applications yet.') : Column(children: [
              for (final x in decisions) RowLine(
                left: Text(x['scheme_name'], style: const TextStyle(fontWeight: FontWeight.w600)),
                right: statusStamp(c, x['decision']),
                below: muted(c, '${shortDate(x['decided_on'])} · ${label(x['reason_code'])} · GPA ${x['gpa_at_decision']}'),
              ),
            ])),
          ]);
        },
      );
}

class MyFeesScreen extends StatelessWidget {
  const MyFeesScreen({super.key});
  @override
  Widget build(BuildContext context) => Fetch<J>(
        load: () async => await Api.instance.get('/me/fees') as J,
        builder: (c, d, reload) {
          final items = (d['items'] as List).cast<J>();
          final terms = {for (final f in items) f['term_name'] as String};
          return ListPage([
            PageTitle('Fee schedule', lead: 'Fees for ${d['program_id']}. Only the version in force on the invoice date is billed.',
                action: ExportButton(name: 'my-fee-schedule', rows: () async => [['Term', 'Fee', 'Applies to', 'Amount (paise)', 'Version', 'Effective from'], for (final f in items) [f['term_id'], f['fee_type'], f['applies_to'], f['amount_paise'], f['version'], f['effective_from']]])),
            for (final t in terms) Panel(title: label(t), child: Column(children: [
              for (final f in items.where((f) => f['term_name'] == t)) RowLine(
                left: Text('${label(f['fee_type'])}${f['applies_to'] == 'ALL' ? '' : ' (${label(f['applies_to'])})'}', style: const TextStyle(fontWeight: FontWeight.w600)),
                right: Money(f['amount_paise']),
                below: muted(c, 'v${f['version']} · from ${shortDate(f['effective_from'])}${f['effective_to'] == null ? '' : ' to ${shortDate(f['effective_to'])}'} · ${f['scholarship_eligible'] == true ? 'scholarship eligible' : 'no scholarship'}'),
              ),
            ])),
          ]);
        },
      );
}
