# Contrato de datos · Colmena IoT

Acuerdo entre la **web (B)** y la **app móvil (C)** para que las dos den los mismos números.
Si algo de aquí cambia, se avisa a ambos antes de subir datos.

## Firestore

Colección: `lecturas` · un documento por lectura · id automático.

| Campo       | Tipo Firestore | Unidad / rango        | Ejemplo        |
|-------------|----------------|-----------------------|----------------|
| `ts`        | **Timestamp**  | instante de captura   | 2026-10-15 15:35 UTC |
| `temp_int`  | number         | °C                    | 34.62          |
| `temp_ext`  | number         | °C                    | 27.10          |
| `peso`      | number         | kg                    | 24.85          |
| `gas`       | number         | 0–1023 (ADC)          | 210            |
| `luz`       | number         | 0–100 %               | 72             |
| `actividad` | number         | 0–100 %               | 45             |
| `origen`    | string         | `"real"` o `"aumentado"` | "aumentado" |

- `ts` debe ser **Timestamp**, no texto. En Python con `firebase_admin`, basta con pasar un `datetime` con zona horaria (por ejemplo `datetime(..., tzinfo=timezone.utc)` o la hora de CR con su zona); un `datetime` sin zona se interpreta mal.
- Datos aumentados: **una lectura cada 5 minutos** (288 por día, ~2 016 por semana). Los ~20 min reales pueden ir completos.
- Los demás campos calculados del CSV (periodo, cambio de peso, estado, alerta) pueden subirse; la app móvil los ignora.

## CSV que A entrega a B

Encabezado mínimo (en este orden o en otro, lo que importa es el nombre):

```
fecha_hora,temp_int,temp_ext,peso,actividad,gas,luz,origen
2026-10-15T09:35:00-06:00,34.62,27.10,24.85,45,210,72,aumentado
```

- `fecha_hora`: ISO 8601. De preferencia con `-06:00` al final. Si viene sin zona, `subir_firestore.py` la toma como hora de Costa Rica.
- Columnas extra (periodo, cambio de peso, estado, alerta) se pueden agregar; se suben tal cual.
- `datos/muestra.csv` es un ejemplo válido de este formato.

## Del Arduino al CSV (posición → campo)

El sketch `colmena_iot.ino` envía `DATA,a,b,c,d,e,f`. El orden **no** es el de los pines:

| Posición | Campo       | Origen en el sketch |
|----------|-------------|---------------------|
| 1        | `temp_int`  | A0, TMP36           |
| 2        | `temp_ext`  | A1, TMP36           |
| 3        | `peso`      | A2, sensor de fuerza |
| 4        | `actividad` | D2, PIR (%)         |
| 5        | `gas`       | A3                  |
| 6        | `luz`       | A4 (%)              |

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
