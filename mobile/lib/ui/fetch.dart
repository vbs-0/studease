import 'package:flutter/material.dart';

import '../api.dart';

import 'kit.dart';

/// Loads data, shows skeleton cards while waiting, an error box with retry on failure, and supports pull-to-refresh.
/// [builder] gets the data and a [reload] callback to call after a write.
class Fetch<T> extends StatefulWidget {
  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data, Future<void> Function() reload) builder;
  final int skeletons;
  final Object? refreshKey;
  const Fetch({super.key, required this.load, required this.builder, this.skeletons = 4, this.refreshKey});
  @override
  State<Fetch<T>> createState() => _FetchState<T>();
}

class _FetchState<T> extends State<Fetch<T>> {
  T? _data;
  Object? _error;
  bool _loading = true;

  @override
  void initState() { super.initState(); _run(); Api.instance.epoch.addListener(_run); }

  @override
  void dispose() { Api.instance.epoch.removeListener(_run); super.dispose(); }

  @override
  void didUpdateWidget(Fetch<T> old) {
    super.didUpdateWidget(old);
    if (old.refreshKey != widget.refreshKey) { _data = null; _loading = true; _run(); }
  }

  Future<void> _run() async {
    try {
      final d = await widget.load();
      if (mounted) setState(() { _data = d; _error = null; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = e; _loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading && _data == null) return PageLoading(cards: widget.skeletons);
    if (_error != null && _data == null) return ListView(children: [ErrorBox(_error!, retry: () { setState(() { _loading = true; _error = null; }); _run(); })]);
    return RefreshIndicator(onRefresh: _run, child: widget.builder(context, _data as T, _run));
  }
}

/// A scrollable page body that always allows pull-to-refresh, with consistent padding.
class ListPage extends StatelessWidget {
  final List<Widget> children;
  const ListPage(this.children, {super.key});
  @override
  Widget build(BuildContext context) => ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 28),
        children: [for (final w in reveal(children)) Padding(padding: const EdgeInsets.only(bottom: 14), child: w)],
      );
}

/// Big serif page title with an optional lead line, like the website's page header.
class PageTitle extends StatelessWidget {
  final String text;
  final String? lead;
  final Widget? action;
  const PageTitle(this.text, {super.key, this.lead, this.action});
  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(text.toUpperCase(), style: const TextStyle(fontFamily: serifName, fontSize: 44, height: .95, letterSpacing: -.5)),
        if (lead != null) Padding(padding: const EdgeInsets.only(top: 8), child: muted(context, lead!, size: 14)),
        if (action != null) Padding(padding: const EdgeInsets.only(top: 12), child: action),
      ]);
}

const serifName = 'InstrumentSerif';
