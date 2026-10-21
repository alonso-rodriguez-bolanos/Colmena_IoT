"""Genera 7 días de datos de colmena a partir de la captura real de Tinkercad."""

import argparse
import math
import random
import statistics
from datetime import datetime, timedelta
from pathlib import Path

from contrato import SENSORES, enriquecer, escribir_csv, leer_csv

CARPETA_DATOS = Path(__file__).resolve().parent.parent / "datos"

TEMP_CRIA_C = 34.8
HORA_PICO_FORRAJEO = 11.0
HORA_FUMIGACION = 10.0
HORA_ENJAMBRAZON = 11.5


def medianas_reales(filas: list[dict]) -> dict[str, float]:
    """Mediana de cada sensor en la captura real; unos pocos valores raros no la mueven."""
    return {sensor: statistics.median(fila[sensor] for fila in filas) for sensor in SENSORES}


def en_ventana(hora: float, inicio: float, minutos: float) -> float:
    """Avance de 0 a 1 dentro de una ventana que empieza a cierta hora."""
    avance = (hora - inicio) * 60 / minutos
    return avance if 0 <= avance < 1 else -1


def generar(
    reales: list[dict],
    desde: datetime,
    hasta: datetime,
    intervalo_min: int,
    semilla: int,
    dias_fumigacion: set[int] = frozenset(),
    dias_enjambrazon: set[int] = frozenset(),
) -> list[dict]:
    """Genera lecturas aumentadas entre dos instantes."""
    azar = random.Random(semilla)
    base = medianas_reales(reales)
    total = int((hasta - desde).total_seconds() // 60) // intervalo_min
    peso = base["peso_kg"]
    salud = 1.0  # 1 colonia fuerte y 0 colonia muy debil
    peso_anterior = None
    filas = []

    for i in range(total):
        momento = desde + timedelta(minutes=i * intervalo_min)
        hora = momento.hour + momento.minute / 60
        dia = (momento.date() - desde.date()).days
        real = reales[i % len(reales)]  # la captura real aporta variacion

        if momento.hour == 0 and momento.minute < intervalo_min:
            nubosidad = azar.uniform(0.5, 1.0)  # cada dia es distinto
            floracion = azar.uniform(0.6, 1.2)
            salud = min(1.0, salud + 0.1)  # la colonia se recupera poco a poco
        elif i == 0:
            nubosidad, floracion = azar.uniform(0.5, 1.0), azar.uniform(0.6, 1.2)

        externa = base["temperatura_externa_c"] + 5 * math.sin(2 * math.pi * (hora - 9) / 24)
        externa += (real["temperatura_externa_c"] - base["temperatura_externa_c"]) * 0.3 + azar.gauss(0, 0.4)

        sol = max(0.0, math.sin(math.pi * (hora - 6) / 12))
        luz = 100 * sol * nubosidad + azar.gauss(0, 2)

        actividad = 85 * math.exp(-((hora - HORA_PICO_FORRAJEO) ** 2) / (2 * 2.2**2))
        actividad *= (0.5 + 0.5 * nubosidad) * salud if luz > 15 else 0
        if 21 <= hora < 22 and azar.random() < 0.05:
            actividad = 10  # actividad nocturna ocasional
        if actividad > 0:
            actividad = max(0, actividad + azar.gauss(0, 5))  # ruido solo cuando hay vuelo

        gas = base["gas_indice"] + (real["gas_indice"] - base["gas_indice"]) * 0.5 + azar.gauss(0, 12)
        if luz < 15:
            gas += 30  # de noche la colonia esta adentro y sube el CO2

        if dia in dias_fumigacion:
            avance = en_ventana(hora, HORA_FUMIGACION, 45)
            if avance >= 0:
                gas += 450 * math.sin(math.pi * avance)  # nube de la fumigacion
            if en_ventana(hora, HORA_FUMIGACION + 0.25, 45) >= 0:
                peso -= 0.35 * intervalo_min / 45  # pecoreadoras que mueren y no regresan
            if hora >= HORA_FUMIGACION + 0.25:
                salud = min(salud, 0.2)

        if dia in dias_enjambrazon:
            avance = en_ventana(hora, HORA_ENJAMBRAZON, 20)
            if avance >= 0:
                actividad = 100  # salida del enjambre
                peso -= 1.8 * intervalo_min / 20
                salud = min(salud, 0.85)

        if actividad > 0:
            peso += actividad / 100 * floracion * 0.025 * intervalo_min / 5  # entra nectar
        if luz < 15:
            peso -= 0.004 * intervalo_min / 5  # consumo y evaporacion de noche
        peso += azar.gauss(0, 0.005)

        acople = 0.08 + 0.3 * (1 - salud)  # colonia debil sigue mas a la temperatura externa
        interna = TEMP_CRIA_C + (externa - TEMP_CRIA_C) * acople + azar.gauss(0, 0.15)

        valores = {
            "temperatura_interna_c": round(interna, 2),
            "temperatura_externa_c": round(externa, 2),
            "peso_kg": round(peso, 3),
            "actividad_pct": int(min(100, round(actividad / 5) * 5)),  # el PIR mide en pasos de 5 %
            "gas_indice": int(min(1023, max(0, round(gas)))),
            "luz_pct": int(min(100, max(0, round(luz)))),
        }
        filas.append(enriquecer(momento, valores, "aumentado", peso_anterior))
        peso_anterior = valores["peso_kg"]
    return filas


def lista_de_dias(texto: str) -> set[int]:
    """Convierte ``"2,4"`` en ``{2, 4}``."""
    return {int(parte) for parte in texto.split(",") if parte.strip()}


def main() -> None:
    """Punto de entrada de la línea de comandos."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entrada", type=Path, default=CARPETA_DATOS / "lecturas_arduino.csv")
    parser.add_argument("--salida", type=Path, default=CARPETA_DATOS / "lecturas_aumentadas.csv")
    parser.add_argument("--dias", type=int, default=7, help="días completos antes de la captura")
    parser.add_argument("--intervalo", type=int, default=5, help="minutos entre lecturas")
    parser.add_argument("--semilla", type=int, default=2026)
    parser.add_argument("--fumigacion", type=lista_de_dias, default={4}, help="días con fumigación, ej. 4 o 2,5")
    parser.add_argument("--enjambrazon", type=lista_de_dias, default={1}, help="días con enjambrazón")
    args = parser.parse_args()

    reales = leer_csv(args.entrada)
    if not reales:
        raise SystemExit("La entrada no tiene lecturas")

    inicio_real = min(fila["fecha_hora"] for fila in reales)
    desde = inicio_real.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=args.dias)
    aumentadas = generar(reales, desde, inicio_real, args.intervalo, args.semilla, args.fumigacion, args.enjambrazon)
    primera_real = min(reales, key=lambda fila: fila["fecha_hora"])
    ajuste = primera_real["peso_kg"] - aumentadas[-1]["peso_kg"]  # que el peso empalme con la captura real
    for fila in aumentadas:
        fila["peso_kg"] = round(fila["peso_kg"] + ajuste, 3)

    for fila in reales:
        fila["fecha_hora"] = fila["fecha_hora"].isoformat(timespec="seconds")
    todas = sorted(aumentadas + reales, key=lambda fila: fila["fecha_hora"])
    escribir_csv(args.salida, todas)
    print(f"{len(reales)} reales + {len(aumentadas)} aumentadas -> {args.salida}")


if __name__ == "__main__":
    main()
