"""Pruebas de la etapa 2 (rol A). Ejecutar desde pc/ con: python -m unittest discover -s tests -v"""

import contextlib
import io
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analisis import analizar  # noqa: E402
from aumento_datos import generar  # noqa: E402
from contrato import ZONA_CR, calcular_alerta, enriquecer, fuera_de_rango, parsear_linea_serial  # noqa: E402
from monitor_serial import monitorear  # noqa: E402
from puente_tinkercad import extraer_lineas, lineas_nuevas  # noqa: E402

INICIO = datetime(2026, 10, 10, tzinfo=ZONA_CR)


def fila(minutos: int, temperatura: float, peso: float = 24.0) -> dict:
    momento = datetime(2026, 10, 20, 10, 0, tzinfo=ZONA_CR) + timedelta(minutes=minutos)
    valores = {"temperatura_interna_c": temperatura, "temperatura_externa_c": 27.0, "peso_kg": peso,
               "actividad_pct": 40, "gas_indice": 200, "luz_pct": 70}
    return enriquecer(momento, valores, "arduino") | {"fecha_hora": momento}


def semana(fumigacion: set[int], enjambrazon: set[int]) -> list[dict]:
    reales = [fila(i * 2, 34.8 + i % 3 * 0.1) for i in range(30)]
    filas = generar(reales, INICIO, INICIO + timedelta(days=7), 5, 2026, fumigacion, enjambrazon)
    for f in filas:
        f["fecha_hora"] = datetime.fromisoformat(f["fecha_hora"])
    return filas


class PruebasContrato(unittest.TestCase):
    def test_linea_valida(self):
        valores = parsear_linea_serial("DATA,34.6,27.1,24.85,100,210,72\r\n")
        self.assertEqual(valores["actividad_pct"], 100)
        self.assertAlmostEqual(valores["peso_kg"], 24.85)

    def test_lineas_invalidas(self):
        for linea in ("# listo", "DATA,1,2", "DATA,a,b,c,d,e,f", ""):
            self.assertIsNone(parsear_linea_serial(linea))

    def test_alertas_de_una_lectura(self):
        base = {"temperatura_interna_c": 34.8, "temperatura_externa_c": 27, "peso_kg": 24,
                "actividad_pct": 0, "gas_indice": 200, "luz_pct": 70}
        self.assertEqual(calcular_alerta(base), "")
        self.assertEqual(calcular_alerta(base | {"temperatura_interna_c": 30}), "temperatura_baja")
        self.assertEqual(calcular_alerta(base | {"actividad_pct": 20, "luz_pct": 2}), "actividad_nocturna")
        self.assertEqual(calcular_alerta(base | {"gas_indice": 700, "temperatura_interna_c": 30}), "gas_alto")

    def test_cambio_de_peso(self):
        momento = datetime(2026, 10, 20, 10, tzinfo=ZONA_CR)
        valores = {"temperatura_interna_c": 34.8, "temperatura_externa_c": 27, "peso_kg": 24.3,
                   "actividad_pct": 50, "gas_indice": 200, "luz_pct": 70}
        resultado = enriquecer(momento, valores, "arduino", peso_anterior=24.0)
        self.assertAlmostEqual(resultado["cambio_peso_kg"], 0.3)
        self.assertEqual(resultado["estado"], "forrajeo")


class PruebasMonitor(unittest.TestCase):
    def test_guarda_solo_lineas_data(self):
        import tempfile
        lineas = ["# colmena-iot listo", "DATA,34.8,27,24.2,0,180,64", "basura", "DATA,34.9,27,24.3,50,181,65"]
        with tempfile.TemporaryDirectory() as carpeta:
            salida = Path(carpeta) / "salida.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                guardadas = monitorear(iter(lineas), salida, None)
            filas = salida.read_text().splitlines()
        self.assertEqual(guardadas, 2)
        self.assertEqual(len(filas), 3)  # encabezado + 2 lecturas
        self.assertIn(",0.1,", filas[2])  # cambio de peso 24.2 -> 24.3


    def test_hora_por_numero_descarta_y_avisa(self):
        import tempfile
        lineas = ["DATA,34.8,27,24.2,0,180,64,10", "DATA,34.9,27,24.3,50,181,65,11",
                  "DATA,124.8,27,24.3,50,181,65,12", "DATA,34.9,27,24.4,50,181,65,14"]
        with tempfile.TemporaryDirectory() as carpeta:
            salida = Path(carpeta) / "salida.csv"
            pantalla = io.StringIO()
            with contextlib.redirect_stdout(pantalla):
                guardadas = monitorear(iter(lineas), salida, None)
            horas = [datetime.fromisoformat(f.split(",")[0]) for f in salida.read_text().splitlines()[1:]]
        self.assertEqual(guardadas, 3)  # la de 124.8 °C se descarta
        self.assertEqual([(h - horas[0]).seconds for h in horas], [0, 2, 8])  # 2 s por numero de lectura
        texto = pantalla.getvalue()
        self.assertIn("Revisar TMP36 interno (A0)", texto)
        self.assertIn("Se perdió la lectura 13", texto)

    def test_rangos_validos(self):
        normal = {"temperatura_interna_c": 34.8, "temperatura_externa_c": 27, "peso_kg": 26,
                  "actividad_pct": 40, "gas_indice": 300, "luz_pct": 60}
        self.assertEqual(fuera_de_rango(normal), {})
        self.assertEqual(set(fuera_de_rango(normal | {"peso_kg": 0, "temperatura_externa_c": -40.2})),
                         {"peso_kg", "temperatura_externa_c"})


class PruebasPuenteTinkercad(unittest.TestCase):
    def test_extrae_solo_lineas_completas(self):
        texto = "Serial Monitor\nDATA,1,2\nDATA,34.8,27.1,24.2,45,210,72,7\nDATA,35,27,24,0,200,60,8"
        self.assertEqual(extraer_lineas(texto), [(7, "DATA,34.8,27.1,24.2,45,210,72,7"), (8, "DATA,35,27,24,0,200,60,8")])

    def test_lineas_iguales_no_se_pierden(self):
        # el caso que congelaba la captura: lecturas identicas con el monitor borrando las viejas
        def pantalla(desde, hasta):
            return [(n, f"DATA,35.94,29.10,23.23,0,306,91,{n}") for n in range(desde, hasta + 1)]
        nuevas, ultimo = lineas_nuevas(0, pantalla(1, 30))
        self.assertEqual((len(nuevas), ultimo), (30, 30))
        nuevas, ultimo = lineas_nuevas(ultimo, pantalla(2, 31))
        self.assertEqual((nuevas, ultimo), (["DATA,35.94,29.10,23.23,0,306,91,31"], 31))
        self.assertEqual(lineas_nuevas(ultimo, pantalla(2, 31)), ([], 31))

    def test_linea_repetida_en_la_pagina(self):
        ahora = [(5, "DATA,35,27,24,0,200,60,5"), (6, "DATA,35,27,24,0,200,60,6"), (5, "DATA,35,27,24,0,200,60,5")]
        self.assertEqual(lineas_nuevas(4, ahora), (["DATA,35,27,24,0,200,60,5", "DATA,35,27,24,0,200,60,6"], 6))

    def test_reinicio_de_la_simulacion(self):
        nuevas, ultimo = lineas_nuevas(120, [(1, "DATA,35,27,24,0,200,60,1"), (2, "DATA,35,27,24,0,200,60,2")])
        self.assertEqual((len(nuevas), ultimo), (2, 2))

    def test_linea_con_numero_de_lectura(self):
        self.assertEqual(parsear_linea_serial("DATA,34.6,27.1,24.85,100,210,72,15")["luz_pct"], 72)


class PruebasAumentoYAnalisis(unittest.TestCase):
    def test_aumento_reproducible_y_en_rango(self):
        primera, segunda = semana({4}, {1}), semana({4}, {1})
        self.assertEqual(len(primera), 7 * 24 * 12)
        self.assertEqual(primera, segunda)
        self.assertTrue(all(f["origen"] == "aumentado" for f in primera))
        self.assertTrue(all(0 <= f["actividad_pct"] <= 100 for f in primera))

    def test_detecta_los_eventos_simulados(self):
        eventos, _ = analizar(semana({4}, {1}))
        tipos = {(e["tipo"], e["dia"]) for e in eventos}
        self.assertIn(("posible_intoxicacion", "2026-10-14"), tipos)
        self.assertIn(("posible_enjambrazon", "2026-10-11"), tipos)

    def test_sin_eventos_no_hay_alertas(self):
        eventos, _ = analizar(semana(set(), set()))
        self.assertEqual(eventos, [])

    def test_termorregulacion_baja_tras_fumigacion(self):
        _, indicadores = analizar(semana({4}, set()))
        antes = indicadores["2026-10-13"]["indice_termorregulacion"]
        despues = indicadores["2026-10-15"]["indice_termorregulacion"]
        self.assertGreater(antes, despues)

    def test_balance_neto_es_ganancia_menos_perdida(self):
        _, indicadores = analizar(semana(set(), set()))
        dia = indicadores["2026-10-12"]
        self.assertAlmostEqual(dia["balance_neto_kg"], dia["ganancia_diurna_kg"] - dia["perdida_nocturna_kg"], places=2)


if __name__ == "__main__":
    unittest.main()
