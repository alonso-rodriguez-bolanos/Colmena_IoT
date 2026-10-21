"""Lee en vivo el Serial Monitor de Tinkercad desde Chrome, como si fuera un puerto serie."""

import json
import re
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Iterator

PATRON_DATA = re.compile(r"DATA(?:,-?[\d.]+){6},(\d+)")  # 6 sensores y el numero de lectura
AVISO_SIN_DATOS_S = 10
PERFIL = Path.home() / ".colmena-iot" / "chrome"  # guarda la sesion de Tinkercad
URL_TINKERCAD = "https://www.tinkercad.com/dashboard"
PUERTO_DEPURACION = 9222
RUTAS_CHROME = [  # Mac y Windows
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

LEER_TEXTO_JS = """() => {
  const partes = [document.body ? document.body.innerText : ''];
  document.querySelectorAll('textarea, pre').forEach(e => partes.push(e.value || e.textContent || ''));
  return partes.join('\\n');
}"""


def extraer_lineas(texto: str) -> list[tuple[int, str]]:
    """Saca del texto de la página las líneas DATA en orden, con su número de lectura."""
    return [(int(m.group(1)), m.group(0)) for m in PATRON_DATA.finditer(texto)]


def lineas_nuevas(ultimo: int, ahora: list[tuple[int, str]]) -> tuple[list[str], int]:
    """Devuelve las líneas con número mayor al último entregado y el nuevo último."""
    unicas = dict(sorted(ahora))  # una misma linea puede verse dos veces en la pagina
    if unicas and max(unicas) < ultimo:
        ultimo = 0  # se reinicio la simulacion y el Arduino volvio a contar desde 1
    nuevas = [linea for numero, linea in unicas.items() if numero > ultimo]
    return nuevas, max([ultimo, *unicas])


def texto_de_pagina(pagina) -> str:
    """Junta el texto de la página y de todos sus marcos (iframes)."""
    partes = []
    for marco in pagina.frames:
        try:
            partes.append(marco.evaluate(LEER_TEXTO_JS))
        except Exception:
            pass  # un marco que se esta recargando se lee en la siguiente vuelta
    return "\n".join(partes)


def chrome_escuchando(puerto: int) -> bool:
    """Indica si ya hay un Chrome con el puerto de depuración abierto."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{puerto}/json/version", timeout=1) as respuesta:
            return "Browser" in json.load(respuesta)
    except OSError:
        return False


def abrir_chrome(url: str, puerto: int) -> None:
    """Abre Chrome como programa normal con el puerto de depuración."""
    if chrome_escuchando(puerto):
        return  # ya estaba abierto de una corrida anterior
    ruta = next((r for r in RUTAS_CHROME if r and Path(r).exists()), None)
    if ruta is None:
        raise SystemExit("No encontré Google Chrome. Instalalo y probá de nuevo.")
    PERFIL.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [ruta, f"--remote-debugging-port={puerto}", f"--user-data-dir={PERFIL}", "--no-first-run", url],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):  # espera hasta 15 s a que Chrome arranque
        if chrome_escuchando(puerto):
            return
        time.sleep(0.5)
    raise SystemExit("Chrome no abrió el puerto de depuración. Cerrá esa ventana de Chrome y probá de nuevo.")


def texto_de_navegador(navegador) -> str:
    """Junta el texto de todas las pestañas abiertas."""
    return "\n".join(texto_de_pagina(pagina) for contexto in navegador.contexts for pagina in contexto.pages)


def lineas_de_tinkercad(url: str = URL_TINKERCAD, cada_s: float = 1.0, puerto: int = PUERTO_DEPURACION) -> Iterator[str]:
    """Abre Chrome en Tinkercad y entrega cada línea nueva del Serial Monitor."""
    from playwright.sync_api import sync_playwright

    abrir_chrome(url, puerto)
    print("En la ventana de Chrome: iniciá sesión si te lo pide, abrí tu diseño,")
    print("Start Simulation y abrí el Serial Monitor. Esperando líneas DATA...")
    with sync_playwright() as p:
        navegador = p.chromium.connect_over_cdp(f"http://127.0.0.1:{puerto}")  # solo lee, no controla
        visibles = extraer_lineas(texto_de_navegador(navegador))
        ultimo = visibles[-1][0] if visibles else 0  # lo que ya estaba en pantalla no es de esta captura
        ultima_llegada = time.monotonic()
        avisado = False
        while True:
            nuevas, ultimo = lineas_nuevas(ultimo, extraer_lineas(texto_de_navegador(navegador)))
            if nuevas:
                ultima_llegada, avisado = time.monotonic(), False
            elif not avisado and time.monotonic() - ultima_llegada > AVISO_SIN_DATOS_S:
                print(f"Hace {AVISO_SIN_DATOS_S} s que no llegan lecturas: revisá que la simulación esté corriendo,")
                print("el Serial Monitor abierto y el código nuevo del Arduino (las líneas terminan en un número).")
                avisado = True
            yield from nuevas
            time.sleep(cada_s)
