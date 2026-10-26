# Colmena IoT

Proyecto IoT del curso IC3101 Arquitectura de Computadoras (TEC).
Monitoreo de una colmena con 6 sensores en Arduino (simulado en Tinkercad), datos en la PC, almacenamiento en Firebase y consulta desde una aplicación web y una móvil.

**Circuito en Tinkercad:** https://www.tinkercad.com/things/iMggERHdqN8-colmena-iot/editel?returnTo=https%3A%2F%2Fwww.tinkercad.com%2Fdashboard&sharecode=PPATr75AcHlVmoDYXWMt-I5OVBtnh7Z1MdflyBYK5p8
**Página web publicada:** https://colmena-iot-tec.web.app

## Arquitectura

| Etapa | Qué hace | Carpeta | Tecnología |
|---|---|---|---|
| 1. Obtención de datos | 6 sensores envían una línea `DATA,...` cada 2 s por el puerto serie | `arduino/` | Arduino UNO (Tinkercad) |
| 2. Datos en la PC | Lee el puerto, guarda el CSV con fecha y hora, genera 7 días aumentados y detecta eventos | `pc/` | Python |
| 3. Datos en la nube | Sube el CSV a la colección `lecturas` | `nube/` | Cloud Firestore |
| 4. Consulta | 4 consultas con gráficos | `web/`, `movil/` | HTML + JavaScript + Chart.js · Flutter (Dart) |

El formato de los datos y las reglas de cálculo que comparten la web y la app están en [`CONTRATO_DATOS.md`](CONTRATO_DATOS.md).

### Sensores

| Sensor | Pin | Ubicación | Campo |
|---|---|---|---|
| TMP36 | A0 | Dentro de la colmena | `temp_int` (°C) |
| TMP36 | A1 | Afuera, a la sombra | `temp_ext` (°C) |
| Sensor de fuerza | A2 | Bajo la base | `peso` (kg) |
| Sensor de gas | A3 | Dentro de la colmena | `gas` (0–1023) |
| Fotorresistor | A4 | Afuera | `luz` (%) |
| PIR | D2 | Frente a la entrada | `actividad` (% del tiempo con movimiento) |

## Las 4 consultas (web y móvil)

1. **Promedio por hora** de un sensor en un día (por defecto, actividad).
2. **Promedio por día** de un sensor en un rango de fechas (por defecto, peso).
3. **Máximo y mínimo** de un sensor dentro de un rango, con fecha y hora.
4. **Máximo y mínimo histórico** de un sensor.

Todas las horas se muestran en hora de Costa Rica (UTC−6).

## Cómo correr cada parte

### Etapas 1 y 2

1. Pegar `arduino/colmena_iot.ino` en Tinkercad (Code → Text) e iniciar la simulación.
2. Instalar una sola vez: `pip install playwright` (se necesita Google Chrome).
3. Capturar y procesar:

```bash
cd pc
python capturar.py    # abre Tinkercad en Chrome, junta 300 lecturas (10 min) y procesa todo
python procesar.py    # solo volver a procesar la última captura, sin capturar
```

Tinkercad simula el Arduino en el navegador y no crea un puerto COM, así que `puente_tinkercad.py` lee el Serial Monitor desde Chrome cada segundo y entrega cada línea nueva como si llegara por el puerto. `monitor_serial.py` le pone fecha y hora, descarta valores imposibles y avisa qué sensor revisar.

`procesar.py` genera, en `datos/`:

| Archivo | Para qué |
|---|---|
| `lecturas_aumentadas.csv` | Captura real + 7 días aumentados. Es el que se sube con `nube/subir_firestore.py` |
| `bitacora_evidencia.csv` | Eventos detectados: firma de intoxicación (gas + caída de actividad + caída de peso) y enjambrazón |

Estos archivos no se suben a git. Pruebas de la etapa 2: `cd pc && python -m unittest discover -s tests -v`. Detalle en [`pc/README.md`](pc/README.md).

### Etapa 3: subir a Firestore

```bash
pip install firebase-admin
# Descargar la clave: Consola de Firebase > Configuración del proyecto > Cuentas de servicio
#   > Generar nueva clave privada  ->  guardarla como nube/clave_servicio.json (NO se sube a git)
python nube/subir_firestore.py datos/muestra.csv --seco   # revisar primero, no escribe nada
python nube/subir_firestore.py datos/muestra.csv          # subir
```

Los datos aumentados se reducen a una lectura cada 5 minutos (≈ 2 016 documentos por semana) para no pasar la cuota gratuita de Firestore (20 000 escrituras y 50 000 lecturas por día).

### Etapa 4: web

```bash
cd web
python -m http.server 8000     # abrir http://localhost:8000
```

Sin configurar Firebase, la página usa datos de demostración. Para conectarla, completar `web/config.js` con la configuración de la app web de Firebase.
No funciona abriendo `index.html` con doble clic: los módulos de JavaScript necesitan un servidor.

Pruebas de los cálculos: `node --test web/test/calculos.test.mjs`

Publicar en Firebase Hosting:

```bash
npm install -g firebase-tools
firebase login
firebase deploy --only hosting,firestore:rules
```

El proyecto (`colmena-iot-tec`) ya está fijado en `.firebaserc`, así que no hace falta `firebase use --add`.
En Windows, si `python` no funciona, usar `py`.

### Etapa 4: app móvil
Ver [`movil/README.md`](movil/README.md).

## Integrantes

| Integrante | Rol |
|---|---|
| _(nombre)_ | A · Hardware y datos en la PC |
| _(nombre)_ | B · Nube y web |
| _(nombre)_ | C · App móvil |
