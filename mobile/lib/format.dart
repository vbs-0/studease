// Money is integer paise everywhere; it is only formatted here, at the edge.

/// Indian digit grouping: 12345678 -> "1,23,456.78".
String inr(num? paise, {bool sign = false}) {
  if (paise == null) return '-';
  final p = paise.round();
  final abs = p.abs();
  final rupees = (abs ~/ 100).toString();
  final frac = (abs % 100).toString().padLeft(2, '0');
  final head = rupees.length > 3 ? rupees.substring(0, rupees.length - 3) : '';
  final grouped = (head.isEmpty ? '' : '${head.replaceAllMapped(RegExp(r'\B(?=(\d{2})+(?!\d))'), (_) => ',')},') + rupees.substring(rupees.length > 3 ? rupees.length - 3 : 0);
  final s = p < 0 ? '-' : (sign && p > 0 ? '+' : '');
  return '$s₹$grouped.$frac';
}

/// Whole rupees, for chart labels: 12,34,567
String inrShort(num? paise) => inr(paise).replaceFirst(RegExp(r'\.00$'), '');

/// Crores for big axis labels: 12.5 Cr
String crore(num paise) => '${(paise / 1e9).toStringAsFixed(1)} Cr';

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// "2026-09-05" -> "05 Sep 2026", built by hand so it never depends on locale data.
String shortDate(String? iso) {
  if (iso == null || iso.length < 10) return '-';
  final p = iso.substring(0, 10).split('-');
  return '${p[2]} ${_months[int.parse(p[1]) - 1]} ${p[0]}';
}

String label(String? code) {
  if (code == null || code.isEmpty) return '-';
  final s = code.toLowerCase().replaceAll('_', ' ');
  return s[0].toUpperCase() + s.substring(1);
}

/// Status -> tone: 0 ok, 1 warn, 2 bad, 3 muted.
int tone(String status) {
  if (const ['PAID', 'ALLOCATED', 'RESOLVED', 'ELIGIBLE', 'APPLIED', 'COMPLETED', 'ENROLLED'].contains(status)) return 0;
  if (const ['OVERDUE', 'OPEN', 'REVOKED', 'INELIGIBLE'].contains(status)) return 2;
  if (const ['PARTIALLY_PAID', 'PARTIALLY_ALLOCATED', 'APPROVED', 'RECEIVED', 'AWARDED', 'ISSUED'].contains(status)) return 1;
  return 3;
}

/// A spreadsheet-safe CSV cell: a leading = + - @ would be run as a formula, so it is prefixed to stay text.
String csvCell(Object? v) {
  var s = v == null ? '' : v.toString();
  if (RegExp(r'^[=+\-@\t\r]').hasMatch(s) && double.tryParse(s) == null) s = "'$s";
  return RegExp(r'[",\n\r]').hasMatch(s) ? '"${s.replaceAll('"', '""')}"' : s;
}

String toCsv(List<List<Object?>> rows) => '﻿${rows.map((r) => r.map(csvCell).join(',')).join('\r\n')}\r\n';
