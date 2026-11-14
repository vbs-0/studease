import 'package:flutter/material.dart';

import '../api.dart';
import '../format.dart';
import '../ui/fetch.dart';
import '../ui/kit.dart';

typedef J = Map<String, dynamic>;

/// One invoice as a CSV file: a header block (who, when, status) then the lines and the total, shared through the phone's share sheet.
Future<void> downloadInvoice(BuildContext context, String id) async {
  try {
    final r = await Api.instance.get('/invoices/$id') as J;
    final inv = r['invoice'] as J;
    final lines = (r['lines'] as List).cast<J>();
    await shareCsv(context, id, [
      ['Invoice', inv['invoice_id']], ['Student', inv['student_id']], ['Issued', inv['issue_date']], ['Due', inv['due_date']], ['Status', inv['status']], [],
      ['Line', 'Type', 'Description', 'Amount (rupees)'],
      for (final l in lines) [l['line_no'], l['line_type'], l['description'], ((l['amount_paise'] as num) / 100).toStringAsFixed(2)],
      ['', '', 'Total', ((inv['total_paise'] as num) / 100).toStringAsFixed(2)],
    ]);
  } on ApiException catch (e) {
    if (context.mounted) toast(context, e.message);
  }
}

class InvoiceScreen extends StatelessWidget {
  final String id;
  const InvoiceScreen({super.key, required this.id});
  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Invoice')),
        body: Fetch<J>(
          load: () async => await Api.instance.get('/invoices/$id') as J,
          builder: (c, d, reload) {
            final inv = d['invoice'] as J;
            final lines = (d['lines'] as List).cast<J>();
            final history = (d['history'] as List).cast<J>();
            return ListPage([
              PageTitle('Invoice', lead: '${inv['invoice_id']}\nStudent ${inv['student_id']} · issued ${shortDate(inv['issue_date'])} · due ${shortDate(inv['due_date'])}',
                  action: Row(children: [statusStamp(c, inv['status']), const SizedBox(width: 12), OutlinedButton.icon(onPressed: () => downloadInvoice(c, id), icon: const Icon(Icons.download_rounded, size: 18), label: const Text('Download'))])),
              Panel(title: 'Lines', child: Column(children: [
                for (final l in lines) RowLine(
                  left: Text('${l['line_no']}. ${l['description']}', style: const TextStyle(fontSize: 14)),
                  right: Money(l['amount_paise'], sign: (l['amount_paise'] as num) < 0),
                  below: l['outstanding_paise'] == null ? muted(c, label(l['line_type'])) : Text('${label(l['line_type'])} · paid ${inr(l['allocated_paise'])} · outstanding ${inr(l['outstanding_paise'])}', style: TextStyle(fontSize: 12.5, color: Theme.of(c).colorScheme.outline)),
                ),
                RowLine(left: const Text('Total', style: TextStyle(fontWeight: FontWeight.w800)), right: Money(inv['total_paise'], big: true)),
              ])),
              Panel(title: 'Status history', child: Column(children: [
                for (final h in history) RowLine(left: Text('${h['from_status'] == null ? '-' : label(h['from_status'])}  →  ${label(h['to_status'])}'), right: muted(c, shortDate(h['occurred_on']))),
              ])),
            ]);
          },
        ),
      );
}
