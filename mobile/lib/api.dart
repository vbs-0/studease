import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Server address. Override at build time: flutter build apk --dart-define=API_BASE=https://host/api/v1
const apiBase = String.fromEnvironment('API_BASE', defaultValue: 'https://studease.is-cool.dev/api/v1');

class ApiException implements Exception {
  final int status;
  final String message;
  final String? requestId;
  ApiException(this.status, this.message, [this.requestId]);
  @override
  String toString() => message;
}

class Me {
  final String id, email, role;
  final String? studentId, programId;
  Me(this.id, this.email, this.role, this.studentId, this.programId);
  factory Me.fromJson(Map<String, dynamic> j) => Me(j['app_user_id'], j['email'], j['role'], j['student_id'], j['program_id']);
  bool get learner => role == 'LEARNER';
  bool get instructor => role == 'INSTRUCTOR';
  bool get staff => !learner;
  bool get seesMoney => !instructor;
}

const staffRoles = ['ACADEMIC_ADMIN', 'SUPPORT', 'PLATFORM_ADMIN'];

/// One small client: bearer token in the Keystore-backed secure storage, the backend's error envelope as a typed error,
/// a 401 on a stored token signs the user out, and every successful read is kept on the phone so screens still open offline.
class Api {
  static final Api instance = Api._();
  Api._();
  final _store = const FlutterSecureStorage();
  final _client = http.Client();
  String? _token;
  void Function()? onSignedOut;

  /// True while the last read was answered from the on-device copy because the server could not be reached.
  final offline = ValueNotifier<bool>(false);

  /// Bumped after every successful write, so every open screen quietly reloads and shows the new books.
  final epoch = ValueNotifier<int>(0);

  Future<bool> restore() async {
    try { _token = await _store.read(key: 'token'); } catch (_) { _token = null; }
    return _token != null;
  }

  Future<Me> login(String email, String password) async {
    final r = await _send('POST', '/auth/login', body: {'email': email, 'password': password}, auth: false);
    return _adopt(r);
  }

  Future<Me> signup(Map<String, dynamic> body) async => _adopt(await _send('POST', '/auth/signup', body: body, auth: false));

  Future<Me> _adopt(dynamic r) async {
    _token = r['token'] as String;
    try { await _store.write(key: 'token', value: _token); } catch (_) {/* keep in memory */}
    return me();
  }

  Future<Me> me() async => Me.fromJson(await get('/auth/me') as Map<String, dynamic>);

  Future<void> signOut() async {
    _token = null;
    try { await _store.delete(key: 'token'); } catch (_) {}
    final p = await SharedPreferences.getInstance();
    for (final k in p.getKeys().where((k) => k.startsWith(_prefix))) { await p.remove(k); }
  }

  static const _prefix = 'c1:';
  String _key(String path, Map<String, String?> q) {
    final parts = (q.entries.where((e) => e.value != null && e.value!.isNotEmpty).toList()..sort((a, b) => a.key.compareTo(b.key))).map((e) => '${e.key}=${e.value}');
    return '$_prefix$path?${parts.join('&')}';
  }

  /// Reads go to the server and are remembered; with no signal the remembered copy answers.
  Future<dynamic> get(String path, [Map<String, String?> q = const {}]) async {
    final key = _key(path, q);
    try {
      final data = await _send('GET', path, query: q);
      if (offline.value) offline.value = false;
      _remember(key, data);
      return data;
    } on ApiException catch (e) {
      if (e.status != 0) rethrow;
      final saved = await _recall(key);
      if (saved == null) rethrow;
      offline.value = true;
      return saved;
    }
  }

  Future<dynamic> post(String path, [Map<String, dynamic>? body, bool idempotent = false]) async {
    final r = await _send('POST', path, body: body ?? {}, headers: idempotent ? {'Idempotency-Key': newKey()} : null);
    epoch.value++;
    return r;
  }

  static String newKey() {
    final r = Random.secure();
    return List.generate(24, (_) => 'abcdefghijklmnopqrstuvwxyz0123456789'[r.nextInt(36)]).join();
  }

  Future<void> _remember(String key, dynamic data) async {
    try {
      final p = await SharedPreferences.getInstance();
      final keys = p.getKeys().where((k) => k.startsWith(_prefix)).toList();
      if (keys.length > 80 && !keys.contains(key)) { await p.remove(keys.first); }
      await p.setString(key, jsonEncode(data));
    } catch (_) {}
  }

  Future<dynamic> _recall(String key) async {
    try {
      final s = (await SharedPreferences.getInstance()).getString(key);
      return s == null ? null : jsonDecode(s);
    } catch (_) { return null; }
  }

  Future<dynamic> _send(String method, String path, {Map<String, String?> query = const {}, Map<String, dynamic>? body, Map<String, String>? headers, bool auth = true}) async {
    final q = {for (final e in query.entries) if (e.value != null && e.value!.isNotEmpty) e.key: e.value!};
    final uri = Uri.parse(apiBase + path).replace(queryParameters: q.isEmpty ? null : q);
    final h = {if (body != null) 'Content-Type': 'application/json', if (auth && _token != null) 'Authorization': 'Bearer $_token', ...?headers};
    http.Response res;
    try {
      final f = method == 'GET' ? _client.get(uri, headers: h) : _client.post(uri, headers: h, body: jsonEncode(body ?? {}));
      res = await f.timeout(const Duration(seconds: 25));
    } catch (_) {
      throw ApiException(0, 'Cannot reach the server. Check your connection and try again.');
    }
    dynamic data;
    try { data = res.body.isEmpty ? null : jsonDecode(utf8.decode(res.bodyBytes)); } catch (_) { data = null; }
    if (res.statusCode >= 400) {
      final e = data is Map ? data['error'] : null;
      if (res.statusCode == 401 && auth && _token != null && path != '/auth/login') { onSignedOut?.call(); }
      throw ApiException(res.statusCode, (e is Map ? e['message'] : null) ?? 'Request failed (${res.statusCode})', e is Map ? e['request_id'] : null);
    }
    return data;
  }

  /// Follow the keyset cursor until the list ends, so an export is the whole list and not one page.
  Future<List<Map<String, dynamic>>> all(String path, [Map<String, String?> q = const {}, int cap = 20000]) async {
    final out = <Map<String, dynamic>>[];
    String? after;
    do {
      final page = await get(path, {...q, 'limit': '200', 'after': after}) as Map;
      out.addAll((page['items'] as List).cast<Map<String, dynamic>>());
      after = page['next'] as String?;
    } while (after != null && out.length < cap);
    return out;
  }
}
