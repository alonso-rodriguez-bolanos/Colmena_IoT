// Lectura de Cloud Firestore por REST (runQuery), sin plugins de Firebase.
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'calculos.dart';

const _proyecto = 'colmena-iot-tec';
const _apiKey = 'AIzaSyAvL5XUArLR9TtDpc7uSRqsxXu4vF7klDs'; // pública (web/config.js)
const _coleccion = 'lecturas';

final _url = Uri.parse(
    'https://firestore.googleapis.com/v1/projects/$_proyecto/databases/(default)/documents:runQuery?key=$_apiKey');

class ErrorDatos implements Exception {
  final String mensaje;
  ErrorDatos(this.mensaje);
  @override
  String toString() => mensaje;
}

Future<List<dynamic>> _run(Map<String, dynamic> query) async {
  final http.Response r;
  try {
    r = await http
        .post(_url,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'structuredQuery': query}))
        .timeout(const Duration(seconds: 30));
  } catch (e) {
    throw ErrorDatos('Sin conexión con Firestore: $e');
  }
  if (r.statusCode == 403) {
    throw ErrorDatos('Error 403: revisar reglas de Firestore o restricciones de la apiKey.');
  }
  if (r.statusCode != 200) {
    throw ErrorDatos('Error ${r.statusCode}: ${r.body}');
  }
  return jsonDecode(r.body) as List<dynamic>;
}

Lectura _aLectura(Map<String, dynamic> doc) {
  final f = (doc['fields'] as Map<String, dynamic>);
  final ts = DateTime.parse(f['ts']['timestampValue'] as String).toUtc();
  final valores = <String, double>{};
  for (final s in sensores) {
    final c = f[s.clave];
    if (c == null) continue;
    if (c['doubleValue'] != null) {
      valores[s.clave] = (c['doubleValue'] as num).toDouble();
    } else if (c['integerValue'] != null) {
      valores[s.clave] = double.parse(c['integerValue'].toString());
    }
  }
  return Lectura(ts, valores);
}

List<Lectura> _lecturas(List<dynamic> resp) => [
      for (final e in resp)
        if (e is Map && e['document'] != null) _aLectura(e['document'] as Map<String, dynamic>)
    ];

Map<String, dynamic> _ts(String op, DateTime d) => {
      'fieldFilter': {
        'field': {'fieldPath': 'ts'},
        'op': op,
        'value': {'timestampValue': d.toUtc().toIso8601String()}
      }
    };

/// Lecturas con desde <= ts < hasta, ordenadas por ts.
Future<List<Lectura>> entre(DateTime desde, DateTime hasta) async {
  final resp = await _run({
    'from': [
      {'collectionId': _coleccion}
    ],
    'where': {
      'compositeFilter': {
        'op': 'AND',
        'filters': [_ts('GREATER_THAN_OR_EQUAL', desde), _ts('LESS_THAN', hasta)]
      }
    },
    'orderBy': [
      {'field': {'fieldPath': 'ts'}, 'direction': 'ASCENDING'}
    ],
  });
  return _lecturas(resp);
}

/// Máximo o mínimo de toda la colección (1 lectura). En empate, la más antigua.
Future<Extremo?> extremoHistorico(String sensor, bool esMaximo) async {
  final resp = await _run({
    'from': [
      {'collectionId': _coleccion}
    ],
    'orderBy': [
      {'field': {'fieldPath': sensor}, 'direction': esMaximo ? 'DESCENDING' : 'ASCENDING'},
    ],
    'limit': 1,
  });
  final l = _lecturas(resp);
  if (l.isEmpty || l.first.valores[sensor] == null) return null;
  final v = l.first.valores[sensor]!;
  // Empates: todas las lecturas con ese valor (sin índice compuesto); gana la más antigua.
  final iguales = await _run({
    'from': [
      {'collectionId': _coleccion}
    ],
    'where': {
      'fieldFilter': {
        'field': {'fieldPath': sensor},
        'op': 'EQUAL',
        'value': {'doubleValue': v}
      }
    },
  });
  final ties = _lecturas(iguales);
  var ts = l.first.ts;
  for (final t in ties) {
    if (t.ts.isBefore(ts)) ts = t.ts;
  }
  return Extremo(v, ts);
}
