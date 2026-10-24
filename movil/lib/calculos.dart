// Cálculos de las consultas. Mismas reglas que web/calculos.js (CONTRATO_DATOS.md):
//  - Se agrupa en hora de Costa Rica (UTC-6, sin horario de verano).
//  - Horas o días sin lecturas se omiten (null), no cuentan como 0.
//  - Lecturas sin valor para el sensor se ignoran.
//  - En un empate de máximo o mínimo gana la lectura más antigua.

class Sensor {
  final String clave, nombre, unidad;
  final int dec;
  const Sensor(this.clave, this.nombre, this.unidad, this.dec);
}

const sensores = <Sensor>[
  Sensor('temp_int', 'Temperatura interna', '°C', 1),
  Sensor('temp_ext', 'Temperatura externa', '°C', 1),
  Sensor('peso', 'Peso', 'kg', 2),
  Sensor('actividad', 'Actividad', '%', 0),
  Sensor('gas', 'Gas (aire)', 'ADC', 0),
  Sensor('luz', 'Luz', '%', 0),
];

Sensor sensorPorClave(String c) => sensores.firstWhere((s) => s.clave == c);

class Lectura {
  final DateTime ts; // UTC
  final Map<String, double> valores;
  Lectura(this.ts, this.valores);
}

class Extremo {
  final double valor;
  final DateTime ts;
  Extremo(this.valor, this.ts);
}

class PromedioDia {
  final String dia; // "2026-10-15"
  final double promedio;
  PromedioDia(this.dia, this.promedio);
}

const _desfase = Duration(hours: 6);

/// DateTime UTC cuyos getters muestran la hora de reloj de Costa Rica.
DateTime relojCR(DateTime ts) => ts.toUtc().subtract(_desfase);

/// "2026-10-15" -> medianoche de ese día en Costa Rica (06:00 UTC).
DateTime inicioDiaCR(String iso) {
  final p = iso.split('-').map(int.parse).toList();
  return DateTime.utc(p[0], p[1], p[2]).add(_desfase);
}

/// Inicio del día siguiente (fin exclusivo del rango).
DateTime finDiaCR(String iso) => inicioDiaCR(iso).add(const Duration(days: 1));

String _dos(int n) => n.toString().padLeft(2, '0');

String fechaISOCR(DateTime ts) {
  final c = relojCR(ts);
  return '${c.year.toString().padLeft(4, '0')}-${_dos(c.month)}-${_dos(c.day)}';
}

String textoFecha(String iso) {
  final p = iso.split('-');
  return '${p[2]}/${p[1]}/${p[0]}';
}

String textoFechaHoraCR(DateTime ts) {
  final c = relojCR(ts);
  return '${_dos(c.day)}/${_dos(c.month)}/${c.year} ${_dos(c.hour)}:${_dos(c.minute)}';
}

String formatear(Sensor s, double v) => '${v.toStringAsFixed(s.dec)} ${s.unidad}';

/// 24 posiciones (hora 0-23 de CR); null si no hubo datos.
List<double?> promedioPorHora(List<Lectura> lecturas, String sensor) {
  final suma = List<double>.filled(24, 0);
  final n = List<int>.filled(24, 0);
  for (final l in lecturas) {
    final v = l.valores[sensor];
    if (v == null) continue;
    final h = relojCR(l.ts).hour;
    suma[h] += v;
    n[h]++;
  }
  return List.generate(24, (h) => n[h] > 0 ? suma[h] / n[h] : null);
}

/// Ordenado por fecha; solo días con datos. Media de todas las lecturas del día.
List<PromedioDia> promedioPorDia(List<Lectura> lecturas, String sensor) {
  final acc = <String, List<double>>{}; // dia -> [suma, n]
  for (final l in lecturas) {
    final v = l.valores[sensor];
    if (v == null) continue;
    final a = acc.putIfAbsent(fechaISOCR(l.ts), () => [0, 0]);
    a[0] += v;
    a[1] += 1;
  }
  final dias = acc.keys.toList()..sort();
  return [for (final d in dias) PromedioDia(d, acc[d]![0] / acc[d]![1])];
}

Extremo? _extremo(List<Lectura> lecturas, String sensor, bool Function(double, double) mejor) {
  Extremo? res;
  for (final l in lecturas) {
    final v = l.valores[sensor];
    if (v == null) continue;
    if (res == null || mejor(v, res.valor) || (v == res.valor && l.ts.isBefore(res.ts))) {
      res = Extremo(v, l.ts);
    }
  }
  return res;
}

Extremo? maximo(List<Lectura> l, String s) => _extremo(l, s, (a, b) => a > b);
Extremo? minimo(List<Lectura> l, String s) => _extremo(l, s, (a, b) => a < b);
