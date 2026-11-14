import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../api.dart';
import '../format.dart';
import '../theme.dart';

/// Slides a child up into place, staggered by [index] (the site's scroll-into-view reveal). Transform only, never half transparent.
class SlideUp extends StatefulWidget {
  final Widget child;
  final int index;
  const SlideUp({super.key, required this.child, this.index = 0});
  @override
  State<SlideUp> createState() => _SlideUpState();
}

class _SlideUpState extends State<SlideUp> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 700));
  @override
  void initState() {
    super.initState();
    Future.delayed(Duration(milliseconds: math.min(widget.index, 7) * 70), () { if (mounted) _c.forward(); });
  }

  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    if (MediaQuery.of(context).disableAnimations) return widget.child;
    return AnimatedBuilder(
      animation: _c,
      child: widget.child,
      builder: (_, child) => Opacity(opacity: _c.value == 0 ? 0 : 1, child: Transform.translate(offset: Offset(0, (1 - ease.transform(_c.value)) * 36), child: child)),
    );
  }
}

/// Press feedback: the child shrinks a little while a finger is down.
class Press extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  const Press({super.key, required this.child, this.onTap});
  @override
  State<Press> createState() => _PressState();
}

class _PressState extends State<Press> {
  bool _down = false;
  @override
  Widget build(BuildContext context) => GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => setState(() => _down = true),
        onTapCancel: () => setState(() => _down = false),
        onTapUp: (_) => setState(() => _down = false),
        onTap: widget.onTap,
        child: AnimatedScale(scale: _down ? .97 : 1, duration: const Duration(milliseconds: 120), curve: ease, child: widget.child),
      );
}

/// Staggered list of children that each slide up.
List<Widget> reveal(List<Widget> children) => [for (var i = 0; i < children.length; i++) SlideUp(index: i, child: children[i])];

class Money extends StatelessWidget {
  final num? paise;
  final bool sign, big;
  final Color? color;
  const Money(this.paise, {super.key, this.sign = false, this.big = false, this.color});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final c = color ?? k.ink;
    return Text(inr(paise, sign: sign), style: TextStyle(color: c, fontFeatures: tabular, fontWeight: big ? FontWeight.w700 : FontWeight.w500, fontSize: big ? 18 : 15));
  }
}

class Stamp extends StatelessWidget {
  final String text;
  final Color color;
  const Stamp(this.text, this.color, {super.key});
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 2),
        decoration: BoxDecoration(border: Border.all(color: color, width: 1.2), borderRadius: BorderRadius.circular(99)),
        child: Text(text.toUpperCase(), style: TextStyle(color: color, fontSize: 10.5, fontWeight: FontWeight.w800, letterSpacing: .9)),
      );
}

Widget statusStamp(BuildContext context, String status) {
  final k = Palette.of(context);
  final c = [k.green, k.amber, k.red, k.muted][tone(status)];
  return Stamp(label(status), c);
}

class Panel extends StatelessWidget {
  final String? title;
  final Widget child;
  final Widget? trailing;
  final EdgeInsets padding;
  const Panel({super.key, this.title, required this.child, this.trailing, this.padding = const EdgeInsets.fromLTRB(18, 16, 18, 16)});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(color: k.sheet, borderRadius: BorderRadius.circular(26), border: Border.all(color: k.rule)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (title != null) Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Row(children: [Expanded(child: Text(title!, style: const TextStyle(fontFamily: serif, fontSize: 26, height: 1.1))), if (trailing != null) trailing!]),
        ),
        child,
      ]),
    );
  }
}

enum Kind { hero, sand, ink, mint }

/// The site's metric cards: orange hero, sand, ink and mint, with the cut corners.
class Metric extends StatelessWidget {
  final Kind kind;
  final String title, value;
  final String? note;
  final VoidCallback? onTap;
  const Metric({super.key, this.kind = Kind.sand, required this.title, required this.value, this.note, this.onTap});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final dark = Theme.of(context).brightness == Brightness.dark;
    final bg = switch (kind) { Kind.hero => k.orange, Kind.sand => k.sand, Kind.ink => dark ? k.sheet : const Color(0xFF191919), Kind.mint => k.mint };
    final fg = switch (kind) { Kind.hero => const Color(0xFF111111), Kind.ink => const Color(0xFFF4F1E8), _ => dark ? const Color(0xFFF4F1E8) : const Color(0xFF111111) };
    return Press(
      onTap: onTap,
      child: ClipPath(
        clipper: kind == Kind.hero || kind == Kind.mint ? null : _Folder(),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
          decoration: BoxDecoration(color: bg, borderRadius: kind == Kind.hero || kind == Kind.mint ? BorderRadius.circular(26) : null),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title.toUpperCase(), style: TextStyle(color: fg.withValues(alpha: .75), fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 1.2)),
            const SizedBox(height: 8),
            FittedBox(fit: BoxFit.scaleDown, alignment: Alignment.centerLeft, child: Text(value, style: TextStyle(color: fg, fontFamily: serif, fontSize: 36, height: 1.05, fontFeatures: tabular))),
            if (note != null) Padding(padding: const EdgeInsets.only(top: 6), child: Text(note!, style: TextStyle(color: fg.withValues(alpha: .75), fontSize: 12.5))),
          ]),
        ),
      ),
    );
  }
}

/// A card with a folded top-right corner, like the website's folder tabs.
class _Folder extends CustomClipper<Path> {
  @override
  Path getClip(Size s) {
    const r = 26.0, c = 34.0;
    return Path()
      ..moveTo(r, 0)..lineTo(s.width - 70 - c, 0)..lineTo(s.width - 70, c)..lineTo(s.width - r, c)
      ..quadraticBezierTo(s.width, c, s.width, c + r)..lineTo(s.width, s.height - r)
      ..quadraticBezierTo(s.width, s.height, s.width - r, s.height)..lineTo(r, s.height)
      ..quadraticBezierTo(0, s.height, 0, s.height - r)..lineTo(0, r)..quadraticBezierTo(0, 0, r, 0)..close();
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> o) => false;
}

/// Metric cards two per row (one per row on narrow phones), the way the site's card grid wraps.
class MetricGrid extends StatelessWidget {
  final List<Widget> cards;
  const MetricGrid(this.cards, {super.key});
  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 400;
    if (narrow) return Column(children: [for (final c in cards) Padding(padding: const EdgeInsets.only(bottom: 12), child: c)]);
    return Column(children: [
      for (var i = 0; i < cards.length; i += 2)
        Padding(padding: const EdgeInsets.only(bottom: 12), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: cards[i]), const SizedBox(width: 12), Expanded(child: i + 1 < cards.length ? cards[i + 1] : const SizedBox()),
        ])),
    ]);
  }
}

/// Skeleton: shimmering blocks that keep the shape of what replaces them.
class Skeleton extends StatefulWidget {
  final double height;
  const Skeleton({super.key, this.height = 80});
  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300))..repeat();
  @override
  void dispose() { _c.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return AnimatedBuilder(
      animation: _c,
      builder: (_, _) => Container(
        height: widget.height,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: LinearGradient(begin: Alignment(-1.5 + _c.value * 3, 0), end: Alignment(-.5 + _c.value * 3, 0), colors: [k.track, k.rule, k.track]),
        ),
      ),
    );
  }
}

class PageLoading extends StatelessWidget {
  final int cards;
  const PageLoading({super.key, this.cards = 4});
  @override
  Widget build(BuildContext context) => ListView(
        physics: const NeverScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: [for (var i = 0; i < cards; i++) Padding(padding: const EdgeInsets.only(bottom: 12), child: Skeleton(height: i == 0 ? 120 : 90))],
      );
}

class ErrorBox extends StatelessWidget {
  final Object error;
  final VoidCallback? retry;
  const ErrorBox(this.error, {super.key, this.retry});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final e = error is ApiException ? error as ApiException : null;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(border: Border.all(color: k.red), borderRadius: BorderRadius.circular(22), color: k.sheet),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(e?.message ?? 'Something went wrong.', style: TextStyle(color: k.red, fontWeight: FontWeight.w700)),
          if (e?.requestId != null) Padding(padding: const EdgeInsets.only(top: 4), child: Text('Request id ${e!.requestId}', style: TextStyle(color: k.muted, fontSize: 12))),
          if (retry != null) Padding(padding: const EdgeInsets.only(top: 12), child: OutlinedButton(onPressed: retry, child: const Text('Try again'))),
        ]),
      ),
    );
  }
}

class Empty extends StatelessWidget {
  final String text;
  const Empty(this.text, {super.key});
  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(text, style: TextStyle(color: Palette.of(context).muted)));
}

void toast(BuildContext context, String message) {
  ScaffoldMessenger.of(context)..hideCurrentSnackBar()..showSnackBar(SnackBar(content: Text(message)));
}

/// Runs an async action, showing the error as a toast. Returns true when it succeeded.
Future<bool> attempt(BuildContext context, Future<void> Function() f) async {
  try { await f(); return true; } on ApiException catch (e) {
    if (context.mounted) toast(context, e.message);
    return false;
  }
}

class Busy extends StatelessWidget {
  const Busy({super.key});
  @override
  Widget build(BuildContext context) => const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2.4));
}

/// A submit button that shows a spinner while its action runs.
class SubmitButton extends StatefulWidget {
  final String text;
  final Future<void> Function() onPressed;
  final bool outlined, enabled;
  const SubmitButton(this.text, {super.key, required this.onPressed, this.outlined = false, this.enabled = true});
  @override
  State<SubmitButton> createState() => _SubmitButtonState();
}

class _SubmitButtonState extends State<SubmitButton> {
  bool _busy = false;
  Future<void> _go() async {
    setState(() => _busy = true);
    try { await widget.onPressed(); } finally { if (mounted) setState(() => _busy = false); }
  }

  @override
  Widget build(BuildContext context) {
    final child = Row(mainAxisSize: MainAxisSize.min, children: [if (_busy) ...[const Busy(), const SizedBox(width: 10)], Flexible(child: Text(widget.text, textAlign: TextAlign.center))]);
    final cb = _busy || !widget.enabled ? null : _go;
    return widget.outlined ? OutlinedButton(onPressed: cb, child: child) : FilledButton(onPressed: cb, child: child);
  }
}

// ------------------------------------------------------------------ form helpers
class Field extends StatelessWidget {
  final String label;
  final TextEditingController controller;
  final bool obscure, number;
  final String? hint;
  final TextInputType? keyboard;
  final void Function(String)? onChanged;
  const Field(this.label, this.controller, {super.key, this.obscure = false, this.number = false, this.hint, this.keyboard, this.onChanged});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5))),
          TextField(controller: controller, obscureText: obscure, onChanged: onChanged, keyboardType: keyboard ?? (number ? const TextInputType.numberWithOptions(decimal: true) : null),
              autocorrect: !obscure, enableSuggestions: !obscure, decoration: InputDecoration(hintText: hint)),
        ]),
      );
}

class Pick<T> extends StatelessWidget {
  final String label;
  final T value;
  final List<(T, String)> options;
  final void Function(T) onChanged;
  const Pick(this.label, this.value, this.options, this.onChanged, {super.key});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(padding: const EdgeInsets.only(bottom: 6), child: Text(label, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5))),
          DropdownButtonFormField<T>(
            initialValue: value, isExpanded: true, borderRadius: BorderRadius.circular(14),
            items: [for (final o in options) DropdownMenuItem(value: o.$1, child: Text(o.$2, overflow: TextOverflow.ellipsis))],
            onChanged: (v) { if (v != null) onChanged(v); },
          ),
        ]),
      );
}

class Check extends StatelessWidget {
  final String text;
  final bool value;
  final void Function(bool) onChanged;
  const Check(this.text, this.value, this.onChanged, {super.key});
  @override
  Widget build(BuildContext context) => CheckboxListTile(
        value: value, onChanged: (v) => onChanged(v ?? false), contentPadding: EdgeInsets.zero, controlAffinity: ListTileControlAffinity.leading,
        title: Text(text, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)), dense: true,
      );
}

/// A table-like list row: left text, right widget; with the site's thin rules between rows.
class RowLine extends StatelessWidget {
  final Widget left;
  final Widget? right;
  final Widget? below;
  final VoidCallback? onTap;
  const RowLine({super.key, required this.left, this.right, this.below, this.onTap});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    return InkWell(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 11),
        decoration: BoxDecoration(border: Border(bottom: BorderSide(color: k.ruleStrong.withValues(alpha: .6)))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [Expanded(child: left), if (right != null) ...[const SizedBox(width: 10), right!]]),
          if (below != null) Padding(padding: const EdgeInsets.only(top: 4), child: below),
        ]),
      ),
    );
  }
}

Text muted(BuildContext c, String s, {double size = 12.5}) => Text(s, style: TextStyle(color: Palette.of(c).muted, fontSize: size));

// ------------------------------------------------------------------ charts
class Slice {
  final String label;
  final num value;
  const Slice(this.label, this.value);
}

/// Donut that sweeps in slice by slice, with a centre figure and a legend underneath.
class Donut extends StatelessWidget {
  final List<Slice> slices;
  final String centre, sub;
  final String Function(num)? format;
  const Donut({super.key, required this.slices, required this.centre, required this.sub, this.format});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final f = format ?? (n) => n.toString();
    final total = slices.fold<num>(0, (n, s) => n + s.value);
    return Column(children: [
      SizedBox(
        width: 190, height: 190,
        child: TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1), duration: const Duration(milliseconds: 1200), curve: drawCurve,
          builder: (_, t, _) => CustomPaint(
            painter: _DonutPainter(slices.map((s) => s.value.toDouble()).toList(), t, k.track),
            child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
              Text(centre, style: const TextStyle(fontFamily: serif, fontSize: 30, height: 1), maxLines: 1),
              Text(sub.toUpperCase(), style: TextStyle(color: k.muted, fontSize: 10, letterSpacing: 1.4)),
            ])),
          ),
        ),
      ),
      const SizedBox(height: 10),
      Wrap(spacing: 14, runSpacing: 6, alignment: WrapAlignment.center, children: [
        for (var i = 0; i < slices.length; i++)
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 10, height: 10, decoration: BoxDecoration(color: Palette.chart[i % Palette.chart.length], shape: BoxShape.circle)),
            const SizedBox(width: 6),
            Text('${label(slices[i].label)} ', style: TextStyle(color: k.muted, fontSize: 12.5)),
            Text(total == 0 ? '-' : f(slices[i].value), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5)),
          ]),
      ]),
    ]);
  }
}

class _DonutPainter extends CustomPainter {
  final List<double> values;
  final double t;
  final Color track;
  _DonutPainter(this.values, this.t, this.track);
  @override
  void paint(Canvas canvas, Size s) {
    final rect = Rect.fromCircle(center: s.center(Offset.zero), radius: s.width / 2 - 9);
    final p = Paint()..style = PaintingStyle.stroke..strokeWidth = 16..strokeCap = StrokeCap.butt;
    canvas.drawArc(rect, 0, math.pi * 2, false, p..color = track);
    final total = values.fold<double>(0, (a, b) => a + b);
    if (total <= 0) return;
    var start = -math.pi / 2;
    for (var i = 0; i < values.length; i++) {
      final sweep = values[i] / total * math.pi * 2 * t;
      canvas.drawArc(rect, start, math.max(0, sweep - .02), false, p..color = Palette.chart[i % Palette.chart.length]);
      start += values[i] / total * math.pi * 2 * t;
    }
  }

  @override
  bool shouldRepaint(_DonutPainter o) => o.t != t || o.values != values;
}

class LineSeries {
  final String name;
  final Color color;
  final List<double> values;
  const LineSeries(this.name, this.color, this.values);
}

/// Line chart: lines draw themselves in, areas fade in; touch a point to read it.
class LineChart extends StatefulWidget {
  final List<String> labels;
  final List<LineSeries> series;
  final String Function(num) format;
  final double height;
  final bool curve;
  final List<Color>? dotColors;
  final List<String>? tips;
  const LineChart({super.key, required this.labels, required this.series, required this.format, this.height = 220, this.curve = false, this.dotColors, this.tips});
  @override
  State<LineChart> createState() => _LineChartState();
}

class _LineChartState extends State<LineChart> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500))..forward();
  int? _sel;
  @override
  void dispose() { _c.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final n = widget.labels.length;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      LayoutBuilder(builder: (_, box) {
        void pick(double dx) {
          if (n < 2) return;
          setState(() => _sel = ((dx - 8) / (box.maxWidth - 16) * (n - 1)).round().clamp(0, n - 1));
        }
        return GestureDetector(
          onTapDown: (d) => pick(d.localPosition.dx),
          onHorizontalDragUpdate: (d) => pick(d.localPosition.dx),
          child: AnimatedBuilder(
            animation: _c,
            builder: (_, _) => CustomPaint(
              size: Size(box.maxWidth, widget.height),
              painter: _LinePainter(widget, k, drawCurve.transform(_c.value), _sel, Theme.of(context).brightness == Brightness.dark),
            ),
          ),
        );
      }),
      if (_sel != null) Padding(
        padding: const EdgeInsets.only(top: 6),
        child: Text(widget.tips?[_sel!] ?? '${widget.labels[_sel!]}: ${widget.series.map((s) => '${s.name} ${widget.format(s.values[_sel!])}').join(', ')}',
            style: TextStyle(color: k.ink, fontSize: 12.5, fontWeight: FontWeight.w600)),
      ),
      const SizedBox(height: 6),
      Wrap(spacing: 14, children: [for (final s in widget.series) Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 10, height: 10, decoration: BoxDecoration(color: s.color, shape: BoxShape.circle)), const SizedBox(width: 6),
        Text(s.name, style: TextStyle(color: k.muted, fontSize: 12.5)),
      ])]),
    ]);
  }
}

class _LinePainter extends CustomPainter {
  final LineChart w;
  final Palette k;
  final double t;
  final int? sel;
  final bool dark;
  _LinePainter(this.w, this.k, this.t, this.sel, this.dark);

  Path _path(List<Offset> pts) {
    final p = Path()..moveTo(pts.first.dx, pts.first.dy);
    if (!w.curve || pts.length < 3) { for (final o in pts.skip(1)) { p.lineTo(o.dx, o.dy); } return p; }
    // monotone cubic: smooth and never beyond the data
    final n = pts.length;
    final dx = [for (var i = 0; i < n - 1; i++) pts[i + 1].dx - pts[i].dx];
    final m = [for (var i = 0; i < n - 1; i++) (pts[i + 1].dy - pts[i].dy) / dx[i]];
    final tan = [m[0], for (var i = 1; i < n - 1; i++) m[i - 1] * m[i] <= 0 ? 0.0 : (m[i - 1] + m[i]) / 2, m[n - 2]];
    for (var i = 0; i < n - 1; i++) {
      if (m[i] == 0) { tan[i] = 0; tan[i + 1] = 0; continue; }
      final a = tan[i] / m[i], b = tan[i + 1] / m[i], h = math.sqrt(a * a + b * b);
      if (h > 3) { tan[i] = 3 * a * m[i] / h; tan[i + 1] = 3 * b * m[i] / h; }
    }
    for (var i = 0; i < n - 1; i++) {
      p.cubicTo(pts[i].dx + dx[i] / 3, pts[i].dy + tan[i] * dx[i] / 3, pts[i + 1].dx - dx[i] / 3, pts[i + 1].dy - tan[i + 1] * dx[i] / 3, pts[i + 1].dx, pts[i + 1].dy);
    }
    return p;
  }

  @override
  void paint(Canvas canvas, Size s) {
    const l = 8.0, r = 8.0, top = 16.0, bottom = 26.0;
    final all = w.series.expand((e) => e.values);
    final lo = math.min(0.0, all.fold<double>(0, math.min)), hi = math.max(1.0, all.fold<double>(0, math.max));
    final n = w.labels.length;
    double x(int i) => l + (n <= 1 ? (s.width - l - r) / 2 : i * (s.width - l - r) / (n - 1));
    double y(double v) => top + (1 - (v - lo) / (hi - lo)) * (s.height - top - bottom);
    final grid = Paint()..color = k.rule..strokeWidth = 1;
    for (var g = 0; g < 4; g++) { final gy = top + g * (s.height - top - bottom) / 3; canvas.drawLine(Offset(l, gy), Offset(s.width - r, gy), grid); }
    if (lo < 0) canvas.drawLine(Offset(l, y(0)), Offset(s.width - r, y(0)), Paint()..color = k.ruleStrong..strokeWidth = 1.2);
    final tp = TextPainter(textDirection: TextDirection.ltr);
    void text(String t, Offset o, {TextAlign a = TextAlign.left}) {
      tp.text = TextSpan(text: t, style: TextStyle(color: k.muted, fontSize: 10.5));
      tp.layout();
      tp.paint(canvas, Offset(a == TextAlign.right ? o.dx - tp.width : a == TextAlign.center ? o.dx - tp.width / 2 : o.dx, o.dy));
    }
    text(w.format(hi), const Offset(l, 0));
    if (lo < 0) { text('${w.format(0)} settled', Offset(s.width - r, y(0) - 14), a: TextAlign.right); text(w.format(lo), Offset(l, s.height - bottom - 14)); }
    final step = math.max(1, (n / 5).ceil());
    for (var i = 0; i < n; i++) {
      if ((i % step == 0 && (n - 1 - i >= step || i == n - 1) && (i == 0 || w.labels[i] != w.labels[i - 1])) || i == n - 1) {
        text(w.labels[i], Offset(x(i), s.height - 16), a: i == 0 ? TextAlign.left : i == n - 1 ? TextAlign.right : TextAlign.center);
      }
    }
    for (final se in w.series) {
      final pts = [for (var i = 0; i < n; i++) Offset(x(i), y(se.values[i]))];
      if (pts.isEmpty) continue;
      final path = _path(pts);
      final base = y(math.max(lo, 0));
      if (pts.length > 1) {
        final area = Path.from(path)..lineTo(pts.last.dx, base)..lineTo(pts.first.dx, base)..close();
        canvas.drawPath(area, Paint()..shader = LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [se.color.withValues(alpha: .3 * t), se.color.withValues(alpha: 0)]).createShader(Rect.fromLTWH(0, top, s.width, s.height)));
      }
      for (final m in path.computeMetrics()) {
        canvas.drawPath(m.extractPath(0, m.length * t), Paint()..style = PaintingStyle.stroke..strokeWidth = 2.3..strokeCap = StrokeCap.round..strokeJoin = StrokeJoin.round..color = se.color);
      }
      if (n <= 24 && t > .7) {
        for (var i = 0; i < n; i++) {
          final c = w.dotColors != null ? w.dotColors![i] : se.color;
          canvas.drawCircle(pts[i], 3.6, Paint()..color = k.sheet);
          canvas.drawCircle(pts[i], 3.6, Paint()..style = PaintingStyle.stroke..strokeWidth = 2..color = c);
        }
      }
    }
    if (sel != null) {
      canvas.drawLine(Offset(x(sel!), top), Offset(x(sel!), s.height - bottom), Paint()..color = k.ink.withValues(alpha: .25));
      for (final se in w.series) { canvas.drawCircle(Offset(x(sel!), y(se.values[sel!])), 6, Paint()..color = se.color); }
    }
  }

  @override
  bool shouldRepaint(_LinePainter o) => o.t != t || o.sel != sel || o.w != w || o.dark != dark;
}

/// A horizontal bar that grows in; [red] for money owed or problems.
class PillBar extends StatelessWidget {
  final String text;
  final num value, max;
  final String display;
  final bool red;
  const PillBar({super.key, required this.text, required this.value, required this.max, required this.display, this.red = false});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final f = max > 0 ? (value.abs() / max).clamp(0.02, 1.0).toDouble() : 0.0;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [Expanded(child: Text(text, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5))), Text(display, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13, fontFeatures: tabular))]),
        const SizedBox(height: 5),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: Container(height: 9, color: k.track, alignment: Alignment.centerLeft, child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: f), duration: const Duration(milliseconds: 1100), curve: drawCurve,
            builder: (_, v, _) => FractionallySizedBox(widthFactor: v, child: Container(color: red ? k.red : k.orange)),
          )),
        ),
      ]),
    );
  }
}

/// Vertical bars with the value above each (net billed by term).
class TermBars extends StatelessWidget {
  final List<(String, num)> bars;
  final String Function(num) format;
  const TermBars(this.bars, this.format, {super.key});
  @override
  Widget build(BuildContext context) {
    final k = Palette.of(context);
    final mx = bars.fold<num>(1, (a, b) => math.max(a, b.$2));
    return SizedBox(
      height: 190,
      child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
        for (var i = 0; i < bars.length; i++) Expanded(
          child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
            Text(format(bars[i].$2), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12)),
            const SizedBox(height: 4),
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: (bars[i].$2 / mx).toDouble()), duration: Duration(milliseconds: 900 + i * 120), curve: drawCurve,
              builder: (_, v, _) => Container(height: math.max(4, 120 * v), margin: const EdgeInsets.symmetric(horizontal: 14), decoration: BoxDecoration(color: Palette.chart[i % 3 == 0 ? 0 : i % 3], borderRadius: BorderRadius.circular(10))),
            ),
            const SizedBox(height: 6),
            Text(bars[i].$1, style: TextStyle(color: k.muted, fontSize: 12)),
          ]),
        ),
      ]),
    );
  }
}

// ------------------------------------------------------------------ export
/// Saves CSV text to a temporary file and opens the phone's share sheet (save to Drive, email, WhatsApp, ...).
Future<void> shareCsv(BuildContext context, String name, List<List<Object?>> rows) async {
  try {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/$name.csv');
    await file.writeAsString(toCsv(rows));
    await SharePlus.instance.share(ShareParams(files: [XFile(file.path, mimeType: 'text/csv')], subject: name));
  } catch (_) {
    if (context.mounted) toast(context, 'Could not export the file.');
  }
}

/// A "CSV" outline button for page headers.
class ExportButton extends StatefulWidget {
  final Future<List<List<Object?>>> Function() rows;
  final String name;
  const ExportButton({super.key, required this.rows, required this.name});
  @override
  State<ExportButton> createState() => _ExportButtonState();
}

class _ExportButtonState extends State<ExportButton> {
  bool _busy = false;
  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
        style: OutlinedButton.styleFrom(minimumSize: const Size(0, 42), padding: const EdgeInsets.symmetric(horizontal: 16)),
        onPressed: _busy ? null : () async {
          setState(() => _busy = true);
          try {
            final rows = await widget.rows();
            if (mounted) await shareCsv(context, widget.name, rows);
          } on ApiException catch (e) { if (mounted) toast(context, e.message); }
          finally { if (mounted) setState(() => _busy = false); }
        },
        icon: _busy ? const Busy() : const Icon(Icons.ios_share_rounded, size: 18),
        label: const Text('Export CSV'),
      );
}
