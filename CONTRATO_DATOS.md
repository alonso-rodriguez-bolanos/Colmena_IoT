# Contrato de datos · Colmena IoT

Acuerdo entre la **web (B)** y la **app móvil (C)** para que las dos den los mismos números.
Si algo de aquí cambia, se avisa a ambos antes de subir datos.

## Firestore

Colección: `lecturas` · un documento por lectura · id automático.

| Campo       | Tipo Firestore | Unidad / rango        | Ejemplo        | Columna en el CSV de A |
|-------------|----------------|-----------------------|----------------|------------------------|
| `ts`        | **Timestamp**  | instante de captura   | 2026-10-15 15:35 UTC | `fecha_hora` |
| `temp_int`  | number         | °C                    | 34.62          | `temperatura_interna_c` |
| `temp_ext`  | number         | °C                    | 27.10          | `temperatura_externa_c` |
| `peso`      | number         | kg                    | 24.85          | `peso_kg` |
| `gas`       | number         | 0–1023 (ADC)          | 210            | `gas_indice` |
| `luz`       | number         | 0–100 %               | 72             | `luz_pct` |
| `actividad` | number         | 0–100 %               | 45             | `actividad_pct` |
| `origen`    | string         | `"real"` o `"aumentado"` | "aumentado" | `origen` (`arduino` se sube como `real`) |

- `ts` debe ser **Timestamp**, no texto. En Python con `firebase_admin`, basta con pasar un `datetime` con zona horaria (por ejemplo `datetime(..., tzinfo=timezone.utc)` o la hora de CR con su zona); un `datetime` sin zona se interpreta mal.
- Datos aumentados: **una lectura cada 5 minutos** (288 por día, ~2 016 por semana). Los ~20 min reales pueden ir completos.
- Los demás campos calculados del CSV (periodo, cambio de peso, estado, alerta) pueden subirse; la app móvil los ignora.

## CSV que A entrega a B

Lo genera `pc/procesar.py` en `datos/lecturas_aumentadas.csv`. Los nombres de columna son los de la etapa 2 (`pc/contrato.py`); `nube/subir_firestore.py` los traduce a los campos de Firestore de la tabla de arriba.

```
fecha_hora,temperatura_interna_c,temperatura_externa_c,peso_kg,actividad_pct,gas_indice,luz_pct,periodo_dia,cambio_peso_kg,estado,alerta,origen
2026-10-15T09:35:00-06:00,34.62,27.10,24.85,45,210,72,manana,0.012,forrajeo,,aumentado
```

- `fecha_hora`: ISO 8601 con `-06:00`. Si viene sin zona, `subir_firestore.py` la toma como hora de Costa Rica.
- `origen`: `arduino` (captura real de Tinkercad) o `aumentado`. En Firestore `arduino` queda como `real`.
- Las columnas calculadas (`periodo_dia`, `cambio_peso_kg`, `estado`, `alerta`) se suben tal cual; la app móvil las ignora.
- `datos/muestra.csv` es un ejemplo válido de este formato (lo genera `nube/generar_muestra.py`).

## Del Arduino al CSV (posición → campo)

El sketch `arduino/colmena_iot.ino` envía `DATA,a,b,c,d,e,f,n`. El orden **no** es el de los pines:

| Posición | Campo en Firestore | Columna del CSV (A) | Origen en el sketch |
|----------|---------------------|--------------------|---------------------|
| 1        | `temp_int`  | `temperatura_interna_c` | A0, TMP36           |
| 2        | `temp_ext`  | `temperatura_externa_c` | A1, TMP36           |
| 3        | `peso`      | `peso_kg` | A2, sensor de fuerza |
| 4        | `actividad` | `actividad_pct` | D2, PIR (%)         |
| 5        | `gas`       | `gas_indice` | A3                  |
| 6        | `luz`       | `luz_pct` | A4 (%)              |
| 7        | — | —           | número de lectura (1, 2, 3…). La PC lo usa para no repetir ni perder líneas y calcular la hora; no se sube |

## Reglas de cálculo (iguales en web y móvil)

1. **Zona horaria:** todo se agrupa en hora de Costa Rica, UTC−6 (sin horario de verano). "El día 15" va de 15/10 06:00 UTC a 16/10 06:00 UTC.
2. **Promedio por hora:** media aritmética de las lecturas de esa hora de reloj (09:00–09:59 → hora 9).
3. **Promedio por día:** media de **todas las lecturas** del día, no la media de los promedios por hora.
4. **Horas o días sin datos:** se omiten. No cuentan como 0.
5. **Máximo / mínimo de una consulta:** sobre las lecturas del rango elegido, desde el inicio del primer día hasta el final del último día (inclusive).
6. **Empates:** se informa la lectura más antigua.
7. **Histórico:** sobre toda la colección.

## Cómo comprobar que coinciden

Antes del 22, elegir 3 consultas fijas (por ejemplo: actividad por hora del día 15; peso por día del 13 al 19; máx/mín histórico de temp_ext) y comparar los números de la web y la móvil uno a uno.
