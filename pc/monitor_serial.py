"""Recibe las líneas DATA, les pone fecha y hora y las guarda en un CSV."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from contrato import (INTERVALO_S, RANGOS_VALIDOS, ZONA_CR, enriquecer, escribir_csv, fuera_de_rango,
                      numero_de_lectura, parsear_linea_serial)


def monitorear(origen_lineas: Iterator[str], ruta: Path, cantidad: int | None) -> int:
    """Guarda cada lectura válida en el CSV hasta juntar la cantidad pedida y devuelve cuántas guardó."""
    guardadas = descartadas = perdidas = 0
    peso_anterior = None
    inicio = None  # hora y numero de la primera lectura: el reloj de toda la captura
    numero_anterior = None
    con_falla: set[str] = set()
    try:
        for linea in origen_lineas:
            valores = parsear_linea_serial(linea)
            if valores is None:
                continue  # comentarios o basura del Serial Monitor
            momento = datetime.now(ZONA_CR)
            numero = numero_de_lectura(linea)
            if numero is not None:
                if numero_anterior is not None and numero > numero_anterior + 1:
                    faltan = numero - numero_anterior - 1
                    perdidas += faltan
                    if faltan == 1:
                        print(f"⚠ Se perdió la lectura {numero - 1}")
                    else:
                        print(f"⚠ Se perdieron {faltan} lecturas: de la {numero_anterior + 1} a la {numero - 1}")
                if inicio is None or numero < numero_anterior:
                    inicio = (momento, numero)  # primera lectura o simulacion reiniciada
                numero_anterior = numero
                momento = inicio[0] + timedelta(seconds=(numero - inicio[1]) * INTERVALO_S)

            fallas = fuera_de_rango(valores)
            for sensor in fallas.keys() - con_falla:
                print(f"⚠ {fallas[sensor]}")
            for sensor in con_falla - fallas.keys():
                print(f"✓ {RANGOS_VALIDOS[sensor][2]} volvió a valores normales")
            con_falla = set(fallas)
            if fallas:
                descartadas += 1
                print(f"  (descartada) {linea}")
                continue

            fila = enriquecer(momento, valores, "arduino", peso_anterior)
            peso_anterior = valores["peso_kg"]
            escribir_csv(ruta, [fila], agregar=True)  # se guarda al instante por si se cae
            guardadas += 1
            print(f"[{guardadas}/{cantidad or '∞'}] {fila['fecha_hora']} {linea} {fila['estado']} {fila['alerta']}")
            if cantidad and guardadas >= cantidad:
                break
    except KeyboardInterrupt:
        print("\nCaptura detenida con Ctrl+C.")
    if descartadas or perdidas:
        print(f"\nResumen: {descartadas} lecturas descartadas por sensores fuera de rango y {perdidas} perdidas.")
    return guardadas
