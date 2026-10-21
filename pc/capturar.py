"""Captura en vivo desde Tinkercad y guarda un archivo nuevo en datos/capturas/."""

from datetime import datetime
from pathlib import Path

import procesar
from contrato import ZONA_CR
from monitor_serial import monitorear
from puente_tinkercad import lineas_de_tinkercad

LECTURAS = 300  # una cada 2 s: 10 minutos de simulacion
URL_DISENO = "https://www.tinkercad.com/dashboard"  # pegar aqui el enlace de tu diseño
CAPTURAS = Path(__file__).resolve().parent.parent / "datos" / "capturas"


def main() -> None:
    """Captura LECTURAS lecturas en un archivo con la fecha y hora en el nombre."""
    salida = CAPTURAS / f"captura_{datetime.now(ZONA_CR):%Y-%m-%d_%H%M%S}.csv"
    print(f"Capturando {LECTURAS} lecturas en {salida}")
    total = monitorear(lineas_de_tinkercad(URL_DISENO), salida, LECTURAS)
    print("\n" + "=" * 60)
    print(f"CAPTURA TERMINADA: {total} lecturas guardadas en {salida.name}")
    print("=" * 60)
    if total < LECTURAS:
        print("Captura incompleta: no se procesa. Volvé a correr capturar.py.")
        return
    print("Ya podés detener la simulación. Procesando...")
    procesar.main()  # 7 dias, eventos, indicadores y pruebas


if __name__ == "__main__":
    main()
