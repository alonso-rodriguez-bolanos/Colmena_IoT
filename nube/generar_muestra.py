"""Genera datos de MUESTRA para probar Firebase, la web y la app móvil
antes de tener los datos finales de A.

7 días que terminan ayer, una lectura cada 5 minutos, con las columnas de
CONTRATO_DATOS.md. Usa una semilla fija: siempre genera lo mismo.

Uso:
    python generar_muestra.py                 -> datos/muestra.csv
    python generar_muestra.py --dias 7 --salida datos/muestra.csv

No reemplaza a aumento_datos.py de A; solo sirve para no esperar.
"""
import argparse
import csv
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

CR = timezone(timedelta(hours=-6))  # Costa Rica, sin horario de verano
CAMPOS = ["fecha_hora", "temp_int", "temp_ext", "peso", "actividad", "gas", "luz", "origen"]


def generar(dias: int, fin: datetime):
    rnd = random.Random(42)
    ruido = lambda a: (rnd.random() - 0.5) * 2 * a
    inicio = fin - timedelta(days=dias)
    peso = 24.0
    t = inicio
    nubosidad = 1.0
    dia_actual = None
    while t < fin:
        h = t.hour + t.minute / 60
        if t.date() != dia_actual:
            dia_actual = t.date()
            nubosidad = 0.6 + rnd.random() * 0.4
        es_dia = 6 <= h < 18
        luz = 100 * math.sin(math.pi * (h - 6) / 12) * nubosidad + ruido(3) if es_dia else 2 + ruido(2)
        actividad = (85 * nubosidad * math.exp(-((h - 11) ** 2) / (2 * 2.5 ** 2)) + ruido(4)
                     if es_dia else abs(ruido(1)))
        peso += 0.0025 * nubosidad if 9 <= h < 16 else -0.0008
        yield {
            "fecha_hora": t.isoformat(timespec="seconds"),
            "temp_int": round(34.5 + 0.3 * math.sin(2 * math.pi * (h - 9) / 24) + ruido(0.15), 2),
            "temp_ext": round(26 + 4 * math.sin(2 * math.pi * (h - 9) / 24) + ruido(0.4), 2),
            "peso": round(peso + ruido(0.01), 2),
            "actividad": int(round(min(100, max(0, actividad)))),
            "gas": int(round(200 + ruido(15))),
            "luz": int(round(min(100, max(0, luz)))),
            "origen": "aumentado",
        }
        t += timedelta(minutes=5)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dias", type=int, default=7)
    p.add_argument("--salida", default=str(Path(__file__).resolve().parent.parent / "datos" / "muestra.csv"))
    a = p.parse_args()

    hoy = datetime.now(CR).replace(hour=0, minute=0, second=0, microsecond=0)
    filas = list(generar(a.dias, hoy))
    Path(a.salida).parent.mkdir(parents=True, exist_ok=True)
    with open(a.salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)
    print(f"{len(filas)} filas -> {a.salida}  ({filas[0]['fecha_hora']} a {filas[-1]['fecha_hora']})")


if __name__ == "__main__":
    main()
