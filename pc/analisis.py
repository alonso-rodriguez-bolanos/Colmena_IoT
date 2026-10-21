"""Añadidos: firma de intoxicación, enjambrazón, termorregulación y balance de néctar."""

import argparse
import csv
import statistics
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

VENTANA = timedelta(minutes=60)
HORARIO_FORRAJEO = (8, 15)
SUBIDA_GAS = 250          # sobre la mediana del dia
CAIDA_ACTIVIDAD = 0.4     # 40 % menos de lo esperado para esa hora
CAIDA_PESO_KG = -0.15
CAIDA_ENJAMBRE_KG = -1.0
VENTANA_ENJAMBRE = timedelta(minutes=30)
HORA_AMANECER = 6
HORA_ATARDECER = 18
COBERTURA_MINIMA_H = 20   # un dia con menos datos no da indicadores


def _fecha(fila: dict) -> datetime:
    valor = fila["fecha_hora"]
    return valor if isinstance(valor, datetime) else datetime.fromisoformat(valor)


def _por_dia(filas: list[dict]) -> dict[str, list[dict]]:
    grupos: dict[str, list[dict]] = defaultdict(list)
    for fila in filas:
        grupos[_fecha(fila).date().isoformat()].append(fila)
    return dict(sorted(grupos.items()))


def perfil_actividad(filas: list[dict]) -> dict[int, float]:
    """Actividad esperada para cada hora del día."""
    por_dia_hora: dict[tuple[str, int], list[int]] = defaultdict(list)
    for fila in filas:
        momento = _fecha(fila)
        por_dia_hora[(momento.date().isoformat(), momento.hour)].append(fila["actividad_pct"])
    por_hora: dict[int, list[float]] = defaultdict(list)
    for (_, hora), valores in por_dia_hora.items():
        por_hora[hora].append(statistics.fmean(valores))
    return {hora: statistics.median(valores) for hora, valores in por_hora.items()}


def _tramo(filas: list[dict], tiempos: list[datetime], inicio: datetime, duracion: timedelta) -> list[dict]:
    desde = bisect_left(tiempos, inicio)
    hasta = bisect_left(tiempos, inicio + duracion)
    return filas[desde:hasta]


def detectar_intoxicaciones(filas: list[dict]) -> list[dict]:
    """Busca la firma de intoxicación en la serie de lecturas."""
    tiempos = [_fecha(fila) for fila in filas]
    perfil = perfil_actividad(filas)
    medianas = {dia: statistics.median(f["gas_indice"] for f in grupo) for dia, grupo in _por_dia(filas).items()}
    eventos = []
    fin_ultimo = None

    for i, fila in enumerate(filas):
        momento = tiempos[i]
        if fin_ultimo and momento < fin_ultimo:
            continue  # ya cubierto por un evento
        if not HORARIO_FORRAJEO[0] <= momento.hour < HORARIO_FORRAJEO[1]:
            continue
        if fila["gas_indice"] < medianas[momento.date().isoformat()] + SUBIDA_GAS:
            continue

        despues = _tramo(filas, tiempos, momento, VENTANA)
        esperado = statistics.fmean(perfil.get(_fecha(f).hour, 0) for f in despues)
        real = statistics.fmean(f["actividad_pct"] for f in despues)
        caida = 1 - real / esperado if esperado else 0
        cambio_peso = despues[-1]["peso_kg"] - despues[0]["peso_kg"]

        if caida >= CAIDA_ACTIVIDAD and cambio_peso <= CAIDA_PESO_KG:
            fin_ultimo = momento + VENTANA
            eventos.append({
                "tipo": "posible_intoxicacion",
                "inicio": momento.isoformat(timespec="seconds"),
                "fin": fin_ultimo.isoformat(timespec="seconds"),
                "dia": momento.date().isoformat(),
                "detalle": {
                    "gas_maximo": max(f["gas_indice"] for f in despues),
                    "gas_mediana_dia": medianas[momento.date().isoformat()],
                    "caida_actividad_pct": round(caida * 100),
                    "cambio_peso_kg": round(cambio_peso, 3),
                },
            })
    return eventos


def detectar_enjambrazon(filas: list[dict]) -> list[dict]:
    """Busca caídas grandes de peso con actividad máxima en la piquera."""
    tiempos = [_fecha(fila) for fila in filas]
    eventos = []
    fin_ultimo = None
    for i, fila in enumerate(filas):
        momento = tiempos[i]
        if (fin_ultimo and momento < fin_ultimo) or fila["actividad_pct"] < 90:
            continue
        tramo = _tramo(filas, tiempos, momento, VENTANA_ENJAMBRE)
        cambio = tramo[-1]["peso_kg"] - tramo[0]["peso_kg"]
        if cambio <= CAIDA_ENJAMBRE_KG:
            fin_ultimo = momento + VENTANA_ENJAMBRE
            eventos.append({
                "tipo": "posible_enjambrazon",
                "inicio": momento.isoformat(timespec="seconds"),
                "fin": fin_ultimo.isoformat(timespec="seconds"),
                "dia": momento.date().isoformat(),
                "detalle": {"cambio_peso_kg": round(cambio, 3)},
            })
    return eventos


def marcar_eventos(filas: list[dict], eventos: list[dict]) -> None:
    """Escribe el tipo de evento en la columna alerta de las filas afectadas."""
    for evento in eventos:
        inicio = datetime.fromisoformat(evento["inicio"])
        fin = datetime.fromisoformat(evento["fin"])
        for fila in filas:
            if inicio <= _fecha(fila) < fin:
                fila["alerta"] = evento["tipo"]


def indicadores_diarios(filas: list[dict]) -> dict[str, dict]:
    """Índice de termorregulación y balance de néctar de cada día."""
    resultado = {}
    atardecer_anterior = None
    for dia, grupo in _por_dia(filas).items():
        horas = [_fecha(f) for f in grupo]
        completo = (max(horas) - min(horas)) >= timedelta(hours=COBERTURA_MINIMA_H)
        indicadores = {"completo": completo, "indice_termorregulacion": None,
                       "ganancia_diurna_kg": None, "perdida_nocturna_kg": None, "balance_neto_kg": None}
        if completo:
            interna = statistics.pstdev(f["temperatura_interna_c"] for f in grupo)
            externa = statistics.pstdev(f["temperatura_externa_c"] for f in grupo)
            if externa > 0:
                indicadores["indice_termorregulacion"] = round(min(1, max(0, 1 - interna / externa)), 3)

            de_dia = [f for f, h in zip(grupo, horas) if HORA_AMANECER <= h.hour < HORA_ATARDECER]
            amanecer, atardecer = de_dia[0]["peso_kg"], de_dia[-1]["peso_kg"]
            indicadores["ganancia_diurna_kg"] = round(atardecer - amanecer, 3)
            if atardecer_anterior is not None:
                perdida = atardecer_anterior - amanecer
                indicadores["perdida_nocturna_kg"] = round(perdida, 3)
                indicadores["balance_neto_kg"] = round(atardecer - atardecer_anterior, 3)
            atardecer_anterior = atardecer
        else:
            atardecer_anterior = None
        resultado[dia] = indicadores
    return resultado


def analizar(filas: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Corre todos los añadidos y marca las alertas en las filas."""
    eventos = detectar_intoxicaciones(filas) + detectar_enjambrazon(filas)
    eventos.sort(key=lambda e: e["inicio"])
    marcar_eventos(filas, eventos)
    return eventos, indicadores_diarios(filas)


def guardar_bitacora(ruta: Path, eventos: list[dict]) -> None:
    """Exporta los eventos a un CSV que se puede adjuntar a una denuncia."""
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["tipo", "inicio", "fin", "evidencia"])
        for evento in eventos:
            evidencia = "; ".join(f"{clave}={valor}" for clave, valor in evento["detalle"].items())
            escritor.writerow([evento["tipo"], evento["inicio"], evento["fin"], evidencia])


def main() -> None:
    """Analiza un CSV del contrato, muestra eventos e indicadores y guarda la bitácora."""
    from contrato import leer_csv

    carpeta_datos = Path(__file__).resolve().parent.parent / "datos"
    parser = argparse.ArgumentParser(description="Detecta eventos y calcula indicadores diarios.")
    parser.add_argument("--entrada", type=Path, default=carpeta_datos / "lecturas_aumentadas.csv")
    parser.add_argument("--bitacora", type=Path, default=carpeta_datos / "bitacora_evidencia.csv")
    args = parser.parse_args()

    filas = sorted(leer_csv(args.entrada), key=lambda f: f["fecha_hora"])
    eventos, indicadores = analizar(filas)
    guardar_bitacora(args.bitacora, eventos)

    print(f"{len(filas)} lecturas · {len(indicadores)} días · {len(eventos)} eventos -> {args.bitacora.name}")
    for evento in eventos:
        print(f"  {evento['tipo']:22} {evento['inicio']}  {evento['detalle']}")
    print("\n  día         termorregulación  balance néctar (kg)")
    for dia, valores in indicadores.items():
        indice = valores["indice_termorregulacion"]
        balance = valores["balance_neto_kg"]
        print(f"  {dia}  {'-' if indice is None else f'{indice:.2f}':>16}  {'-' if balance is None else f'{balance:+.2f}':>19}")


if __name__ == "__main__":
    main()
