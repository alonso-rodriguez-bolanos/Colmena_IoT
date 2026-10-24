import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import 'calculos.dart';
import 'datos.dart' as datos;

void main() => runApp(const ColmenaApp());

class ColmenaApp extends StatelessWidget {
  const ColmenaApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'Colmena IoT',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.amber),
          useMaterial3: true,
        ),
        home: const Pantalla(),
      );
}

const _consultas = [
  'Promedio por hora (un día)',
  'Promedio por día (rango)',
  'Máximo y mínimo (rango)',
  'Máximo y mínimo histórico',
];
const _maxDias = 31;

String _iso(DateTime d) =>
    '${d.year.toString().padLeft(4, '0')}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

class Pantalla extends StatefulWidget {
  const Pantalla({super.key});
  @override
  State<Pantalla> createState() => _PantallaState();
}

class _PantallaState extends State<Pantalla> {
  int consulta = 0;
  String sensor = 'actividad';
  late DateTime desde, hasta;
  bool cargando = false;
  String? error;
  String? aviso;
  Widget? resultado;

  @override
  void initState() {
    super.initState();
    // Los datos van del 15 al 19/10/2026: se abre ya sobre ese rango.
    desde = DateTime(2026, 10, 15);
    hasta = DateTime(2026, 10, 19);
  }

  void _cambiarConsulta(int i) => setState(() {
        consulta = i;
        resultado = null;
        error = null;
        aviso = null;
        if (i == 0) sensor = 'actividad';
        if (i == 1) sensor = 'peso';
        if (i == 0 || i == 1) {
          desde = DateTime(2026, 10, 15);
          if (hasta.isBefore(desde)) hasta = DateTime(2026, 10, 19);
        }
      });

  Future<void> _elegirFecha(bool esDesde) async {
    final r = await showDatePicker(
      context: context,
      initialDate: esDesde ? desde : hasta,
      firstDate: DateTime(2026, 1, 1),
      lastDate: DateTime(2027, 12, 31),
    );
    if (r == null) return;
    setState(() {
      if (esDesde || consulta == 0) {
        desde = r;
        if (consulta == 0 || hasta.isBefore(desde)) hasta = r;
      } else {
        hasta = r;
        if (hasta.isBefore(desde)) desde = r;
      }
    });
  }

  Future<void> _consultar() async {
    setState(() {
      cargando = true;
      error = null;
      aviso = null;
      resultado = null;
    });
    try {
      final s = sensorPorClave(sensor);
      final d0 = _iso(desde), d1 = consulta == 0 ? d0 : _iso(hasta);
      if (consulta != 3 && hasta.difference(desde).inDays + 1 > _maxDias && consulta != 0) {
        throw datos.ErrorDatos('El rango máximo es de $_maxDias días.');
      }
      Widget w;
      if (consulta == 3) {
        final mx = await datos.extremoHistorico(sensor, true);
        final mn = await datos.extremoHistorico(sensor, false);
        if (mx == null || mn == null) {
          aviso = 'La colección está vacía (aún no se han subido datos).';
          w = const SizedBox();
        } else {
          w = _tarjetasExtremos(s, mx, mn);
        }
      } else {
        final l = await datos.entre(inicioDiaCR(d0), finDiaCR(d1));
        if (l.isEmpty) {
          aviso = 'No hay lecturas en ese periodo.';
          w = const SizedBox();
        } else if (consulta == 0) {
          w = _graficoHoras(s, promedioPorHora(l, sensor), l.length);
        } else if (consulta == 1) {
          w = _graficoDias(s, promedioPorDia(l, sensor), l.length);
        } else {
          final mx = maximo(l, sensor), mn = minimo(l, sensor);
          w = (mx == null || mn == null)
              ? const Text('Sin valores para este sensor.')
              : _tarjetasExtremos(s, mx, mn);
        }
      }
      if (mounted) setState(() => resultado = w);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => cargando = false);
    }
  }

  // ---------- Widgets de resultado ----------

  Widget _tarjetasExtremos(Sensor s, Extremo mx, Extremo mn) => Column(children: [
        _tarjeta('Máximo', formatear(s, mx.valor), textoFechaHoraCR(mx.ts), Colors.red.shade700),
        _tarjeta('Mínimo', formatear(s, mn.valor), textoFechaHoraCR(mn.ts), Colors.blue.shade700),
      ]);

  Widget _tarjeta(String t, String v, String f, Color c) => Card(
        child: ListTile(
          leading: Icon(t == 'Máximo' ? Icons.arrow_upward : Icons.arrow_downward, color: c),
          title: Text('$t: $v', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          subtitle: Text(f),
        ),
      );

  Widget _graficoHoras(Sensor s, List<double?> prom, int n) {
    final valores = prom.whereType<double>();
    final maxY = valores.reduce((a, b) => a > b ? a : b);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('${s.nombre} (${s.unidad}) · promedio por hora · $n lecturas',
          style: const TextStyle(fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      SizedBox(
        height: 260,
        child: BarChart(BarChartData(
          maxY: maxY <= 0 ? 1 : maxY * 1.15,
          barGroups: [
            for (var h = 0; h < 24; h++)
              BarChartGroupData(x: h, barRods: [
                BarChartRodData(
                    toY: prom[h] ?? 0,
                    width: 8,
                    color: prom[h] == null ? Colors.transparent : Colors.amber.shade700)
              ])
          ],
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 40)),
            bottomTitles: AxisTitles(
                sideTitles: SideTitles(
              showTitles: true,
              interval: 1,
              getTitlesWidget: (v, m) => v.toInt() % 3 == 0
                  ? Text('${v.toInt()}', style: const TextStyle(fontSize: 11))
                  : const SizedBox(),
            )),
          ),
          barTouchData: BarTouchData(
            touchTooltipData: BarTouchTooltipData(
              getTooltipItem: (g, gi, r, ri) => prom[g.x] == null
                  ? null
                  : BarTooltipItem('${g.x}h\n${formatear(s, prom[g.x]!)}',
                      const TextStyle(color: Colors.white)),
            ),
          ),
        )),
      ),
      const SizedBox(height: 8),
      Wrap(spacing: 12, runSpacing: 4, children: [
        for (var h = 0; h < 24; h++)
          if (prom[h] != null) Text('${h.toString().padLeft(2, '0')}h: ${formatear(s, prom[h]!)}',
              style: const TextStyle(fontSize: 12)),
      ]),
    ]);
  }

  Widget _graficoDias(Sensor s, List<PromedioDia> dias, int n) {
    final ys = dias.map((d) => d.promedio);
    var minY = ys.reduce((a, b) => a < b ? a : b);
    var maxY = ys.reduce((a, b) => a > b ? a : b);
    final pad = (maxY - minY) == 0 ? 1.0 : (maxY - minY) * 0.15;
    minY -= pad;
    maxY += pad;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('${s.nombre} (${s.unidad}) · promedio por día · $n lecturas',
          style: const TextStyle(fontWeight: FontWeight.bold)),
      const SizedBox(height: 12),
      SizedBox(
        height: 260,
        child: LineChart(LineChartData(
          minY: minY,
          maxY: maxY,
          lineBarsData: [
            LineChartBarData(
              spots: [for (var i = 0; i < dias.length; i++) FlSpot(i.toDouble(), dias[i].promedio)],
              color: Colors.amber.shade800,
              barWidth: 3,
              isCurved: false,
              dotData: const FlDotData(show: true),
            )
          ],
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            leftTitles: AxisTitles(
                sideTitles: SideTitles(
              showTitles: true,
              reservedSize: 44,
              getTitlesWidget: (v, m) =>
                  Text(v.toStringAsFixed(s.dec), style: const TextStyle(fontSize: 10)),
            )),
            bottomTitles: AxisTitles(
                sideTitles: SideTitles(
              showTitles: true,
              interval: 1,
              getTitlesWidget: (v, m) {
                final i = v.toInt();
                if (v != i.toDouble() || i < 0 || i >= dias.length) return const SizedBox();
                if (dias.length > 8 && i % 2 != 0) return const SizedBox();
                final p = dias[i].dia.split('-');
                return Text('${p[2]}/${p[1]}', style: const TextStyle(fontSize: 10));
              },
            )),
          ),
          lineTouchData: LineTouchData(
            touchTooltipData: LineTouchTooltipData(
              getTooltipItems: (spots) => [
                for (final t in spots)
                  LineTooltipItem(
                      '${textoFecha(dias[t.x.toInt()].dia)}\n${formatear(s, t.y)}',
                      const TextStyle(color: Colors.white))
              ],
            ),
          ),
        )),
      ),
      const SizedBox(height: 8),
      for (final d in dias) Text('${textoFecha(d.dia)}: ${formatear(s, d.promedio)}'),
    ]);
  }

  // ---------- Interfaz ----------

  @override
  Widget build(BuildContext context) {
    final soloUnDia = consulta == 0;
    final sinFechas = consulta == 3;
    return Scaffold(
      appBar: AppBar(title: const Text('Colmena IoT'), backgroundColor: Colors.amber),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        DropdownButtonFormField<int>(
          initialValue: consulta,
          decoration: const InputDecoration(labelText: 'Consulta', border: OutlineInputBorder()),
          items: [for (var i = 0; i < _consultas.length; i++) DropdownMenuItem(value: i, child: Text(_consultas[i]))],
          onChanged: (v) => _cambiarConsulta(v!),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          initialValue: sensor,
          decoration: const InputDecoration(labelText: 'Sensor', border: OutlineInputBorder()),
          items: [for (final s in sensores) DropdownMenuItem(value: s.clave, child: Text(s.nombre))],
          onChanged: (v) => setState(() {
            sensor = v!;
            resultado = null;
          }),
        ),
        if (!sinFechas) ...[
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
                child: OutlinedButton.icon(
              icon: const Icon(Icons.calendar_today),
              label: Text(soloUnDia ? 'Día: ${textoFecha(_iso(desde))}' : 'Desde: ${textoFecha(_iso(desde))}'),
              onPressed: () => _elegirFecha(true),
            )),
            if (!soloUnDia) ...[
              const SizedBox(width: 8),
              Expanded(
                  child: OutlinedButton.icon(
                icon: const Icon(Icons.calendar_today),
                label: Text('Hasta: ${textoFecha(_iso(hasta))}'),
                onPressed: () => _elegirFecha(false),
              )),
            ],
          ]),
        ],
        const SizedBox(height: 12),
        FilledButton(onPressed: cargando ? null : _consultar, child: const Text('Consultar')),
        const SizedBox(height: 16),
        if (cargando) const Center(child: CircularProgressIndicator()),
        if (error != null) Text(error!, style: TextStyle(color: Colors.red.shade800)),
        if (aviso != null) Text(aviso!),
        if (resultado != null) resultado!,
      ]),
    );
  }
}
