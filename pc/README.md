# Etapa 2 · Datos en la PC

Programas en Python que reciben las lecturas del Arduino de Tinkercad, les agregan fecha, hora y datos derivados, generan 7 días de datos y detectan eventos.

## Uso rápido (con F5 en IDLE)

1. **`capturar.py`** · abre Tinkercad en un Chrome aparte y lee el Serial Monitor en vivo hasta juntar `LECTURAS` lecturas (300 = 10 minutos) y avisa al terminar. Cada captura queda en su propio archivo en `datos/capturas/` y ninguna se borra.
2. **`procesar.py`** · se corre solo al terminar una captura completa; también se puede correr aparte para volver a procesar sin capturar. Usa la última captura (o todas, con `USAR_CAPTURAS = "todas"`), genera los 7 días, detecta eventos, calcula indicadores y corre las pruebas.

## Archivos

| Archivo | Qué hace |
|---|---|
| `contrato.py` | Formato de la línea `DATA`, columnas del CSV y alertas de una lectura |
| `puente_tinkercad.py` | Lee el Serial Monitor de Tinkercad desde el navegador, como si fuera un puerto serie |
| `monitor_serial.py` | Recibe las líneas de Tinkercad, les pone fecha y hora y las guarda |
| `capturar.py` | Atajo para capturar desde Tinkercad |
| `aumento_datos.py` | Genera 7 días a partir de la captura real, con una enjambrazón y una fumigación simuladas |
| `analisis.py` | Firma de intoxicación, enjambrazón, índice de termorregulación, balance de néctar y bitácora |
| `procesar.py` | Corre todo en orden |
| `tests/` | Pruebas automáticas |

## Instalación (una sola vez)

    pip3 install playwright

Se necesita Google Chrome instalado.

## Desde la Terminal

    cd pc
    python3 capturar.py     # 300 lecturas en vivo y después procesa todo
    python3 procesar.py     # solo procesar otra vez, sin capturar
