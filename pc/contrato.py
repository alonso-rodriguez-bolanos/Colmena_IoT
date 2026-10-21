"""Reglas compartidas: sensores, columnas del CSV y alertas de una sola lectura."""

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

ZONA_CR = timezone(timedelta(hours=-6), "America/Costa_Rica")

SENSORES: tuple[str, ...] = (
    "temperatura_interna_c",
    "temperatura_externa_c",
    "peso_kg",
    "actividad_pct",
    "gas_indice",
    "luz_pct",
)

COLUMNAS: tuple[str, ...] = (
    "fecha_hora",
    *SENSORES,
    "periodo_dia",
    "cambio_peso_kg",
    "estado",
    "alerta",
    "origen",
)

TIPOS: dict[str, type] = {
    "temperatura_interna_c": float,
    "temperatura_externa_c": float,
    "peso_kg": float,
    "actividad_pct": int,
    "gas_indice": int,
    "luz_pct": int,
}

CRIA_MIN_C = 32.0  # rango en que la colonia mantiene la cria
CRIA_MAX_C = 37.0
UMBRAL_GAS_ALTO = 600
UMBRAL_LUZ_DIA = 15
INTERVALO_S = 2  # igual a INTERVALO_MS del Arduino

# (minimo, maximo, sensor fisico, unidad): fuera de esto es una falla del sensor, no de la colmena
RANGOS_VALIDOS: dict[str, tuple[float, float, str, str]] = {
    "temperatura_interna_c": (0, 50, "TMP36 interno (A0)", " °C"),
    "temperatura_externa_c": (0, 50, "TMP36 externo (A1)", " °C"),
    "peso_kg": (1, 39.5, "sensor de fuerza (A2)", " kg"),
    "actividad_pct": (0, 100, "PIR (pin 2)", " %"),
    "gas_indice": (0, 1023, "sensor de gas (A3)", ""),
    "luz_pct": (0, 100, "fotorresistor (A4)", " %"),
}


def parsear_linea_serial(linea: str) -> dict[str, float | int] | None:
    """Convierte una línea DATA del Arduino en un diccionario de sensores."""
    partes = linea.strip().split(",")
    if partes[0] != "DATA" or len(partes) not in (len(SENSORES) + 1, len(SENSORES) + 2):
        return None  # el ultimo valor opcional es el numero de lectura, que no se guarda
    try:
        return {
            sensor: TIPOS[sensor](float(valor))
            for sensor, valor in zip(SENSORES, partes[1:])
        }
    except ValueError:
        return None


def numero_de_lectura(linea: str) -> int | None:
    """Número de lectura que el Arduino pone al final de la línea, si lo trae."""
    partes = linea.strip().split(",")
    if len(partes) == len(SENSORES) + 2 and partes[-1].isdigit():
        return int(partes[-1])
    return None


def fuera_de_rango(valores: dict[str, float | int]) -> dict[str, str]:
    """Sensores con un valor imposible, cada uno con el aviso para revisarlo."""
    avisos = {}
    for sensor, (minimo, maximo, nombre, unidad) in RANGOS_VALIDOS.items():
        if not minimo <= valores[sensor] <= maximo:
            avisos[sensor] = f"Revisar {nombre}: marcó {valores[sensor]}{unidad}; lo válido es de {minimo} a {maximo}{unidad}"
    return avisos


def periodo_del_dia(hora: int) -> str:
    """Clasifica una hora de 0 a 23 en un periodo del día."""
    if hora < 6:
        return "madrugada"
    if hora < 12:
        return "manana"
    if hora < 18:
        return "tarde"
    return "noche"


def estado_colmena(valores: dict[str, float | int]) -> str:
    """Indica si las abejas están forrajeando o en reposo."""
    if valores["actividad_pct"] > 0 and valores["luz_pct"] >= UMBRAL_LUZ_DIA:
        return "forrajeo"
    return "reposo"


def calcular_alerta(valores: dict[str, float | int]) -> str:
    """Alerta más importante de una sola lectura."""
    if valores["gas_indice"] >= UMBRAL_GAS_ALTO:
        return "gas_alto"
    if valores["temperatura_interna_c"] > CRIA_MAX_C:
        return "temperatura_alta"
    if valores["temperatura_interna_c"] < CRIA_MIN_C:
        return "temperatura_baja"
    if valores["actividad_pct"] > 0 and valores["luz_pct"] < UMBRAL_LUZ_DIA:
        return "actividad_nocturna"
    return ""


def enriquecer(
    fecha_hora: datetime,
    valores: dict[str, float | int],
    origen: str,
    peso_anterior: float | None = None,
) -> dict[str, str | float | int]:
    """Arma una fila completa del CSV con los datos derivados."""
    cambio = 0.0 if peso_anterior is None else valores["peso_kg"] - peso_anterior
    return {
        "fecha_hora": fecha_hora.isoformat(timespec="seconds"),
        **valores,
        "periodo_dia": periodo_del_dia(fecha_hora.hour),
        "cambio_peso_kg": round(cambio, 3),
        "estado": estado_colmena(valores),
        "alerta": calcular_alerta(valores),
        "origen": origen,
    }


def escribir_csv(ruta: Path, filas: list[dict], agregar: bool = False) -> None:
    """Escribe filas en un CSV con el encabezado del contrato."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    existe = ruta.exists() and ruta.stat().st_size > 0
    with ruta.open("a" if agregar else "w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=COLUMNAS, extrasaction="ignore")
        if not (agregar and existe):
            escritor.writeheader()
        escritor.writerows(filas)


def leer_csv(ruta: Path) -> list[dict]:
    """Lee un CSV del contrato y convierte cada columna a su tipo."""
    filas = []
    with ruta.open(encoding="utf-8") as archivo:
        for fila in csv.DictReader(archivo):
            fila["fecha_hora"] = datetime.fromisoformat(fila["fecha_hora"])
            for sensor, tipo in TIPOS.items():
                fila[sensor] = tipo(float(fila[sensor]))
            fila["cambio_peso_kg"] = float(fila.get("cambio_peso_kg") or 0)
            filas.append(fila)
    return filas
