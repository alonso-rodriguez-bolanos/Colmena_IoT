"""Corre la etapa 2 completa a partir de la última captura de Tinkercad."""

import subprocess
import sys
from pathlib import Path

CARPETA_PC = Path(__file__).resolve().parent
CARPETA_DATOS = CARPETA_PC.parent / "datos"
USAR_CAPTURAS = "ultima"  # "ultima" o "todas"

CAPTURAS = CARPETA_DATOS / "capturas"
LECTURAS = CARPETA_DATOS / "lecturas_arduino.csv"
AUMENTADAS = CARPETA_DATOS / "lecturas_aumentadas.csv"
BITACORA = CARPETA_DATOS / "bitacora_evidencia.csv"


def correr(titulo: str, argumentos: list[str]) -> bool:
    """Ejecuta un programa de pc/ y muestra el final de lo que imprime."""
    print(f"\n=== {titulo} ===")
    resultado = subprocess.run([sys.executable, *argumentos], cwd=CARPETA_PC, capture_output=True, text=True)
    salida = (resultado.stdout + resultado.stderr).strip().splitlines()
    print("\n".join(salida[-20:]))  # solo el final para no llenar la pantalla
    return resultado.returncode == 0


def juntar_capturas() -> list[Path]:
    """Une las capturas elegidas en datos/lecturas_arduino.csv."""
    archivos = sorted(CAPTURAS.glob("captura_*.csv"))  # el nombre lleva la fecha, asi queda en orden
    elegidas = archivos if USAR_CAPTURAS == "todas" else archivos[-1:]
    encabezado = None
    filas = []
    for archivo in elegidas:
        lineas = archivo.read_text(encoding="utf-8").splitlines()
        encabezado = encabezado or lineas[0]
        filas += lineas[1:]
    if elegidas:
        LECTURAS.write_text("\n".join([encabezado, *filas]) + "\n", encoding="utf-8")
    return elegidas


def main() -> None:
    """Junta las capturas, genera los 7 días, analiza y corre las pruebas."""
    elegidas = juntar_capturas()
    if not elegidas:
        print("No hay capturas todavía. Corré capturar.py primero.")
        return
    print(f"\n=== 1/4 Capturas ({USAR_CAPTURAS}) ===")
    for archivo in elegidas:
        print(f"  {archivo.name}")

    pasos = [
        ("2/4 Aumento a 7 días", ["aumento_datos.py"]),
        ("3/4 Eventos e indicadores", ["analisis.py", "--entrada", str(AUMENTADAS)]),
        ("4/4 Pruebas", ["-m", "unittest", "discover", "-s", "tests"]),
    ]
    for titulo, argumentos in pasos:
        if not correr(titulo, argumentos):
            print(f"\nSe detuvo en: {titulo}.")
            return

    print("\n=== Listo ===")
    print(f"Archivos para B:\n  {AUMENTADAS}\n  {BITACORA}")


if __name__ == "__main__":
    main()
