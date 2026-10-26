# App móvil · Colmena IoT (Flutter)

Consulta la colección `lecturas` de Cloud Firestore (proyecto `colmena-iot-tec`) y muestra las 4 consultas del enunciado, con los mismos números que la web:

1. Promedio por hora de un sensor en un día (por defecto, actividad).
2. Promedio por día de un sensor en un rango de fechas (por defecto, peso).
3. Máximo y mínimo de un sensor en un rango, con fecha y hora.
4. Máximo y mínimo histórico de un sensor.

Las reglas de cálculo son las de `CONTRATO_DATOS.md` (hora de Costa Rica UTC-6, horas o días sin datos se omiten, en empate gana la lectura más antigua). La lógica está en `lib/calculos.dart` y replica `web/calculos.js`.

## Cómo está hecha
- `lib/calculos.dart`: sensores, conversión a hora CR, promedios, máximo y mínimo.
- `lib/datos.dart`: lee Firestore por REST (`runQuery`) con el paquete `http`. No usa plugins de Firebase ni `google-services.json`. La apiKey es pública (la misma de `web/config.js`); la seguridad la dan las reglas de Firestore (solo lectura).
- `lib/main.dart`: interfaz y gráficos con `fl_chart`.
- `android/app/src/main/AndroidManifest.xml`: Impeller desactivado, porque en emuladores con gráficos por software la app se quedaba en el logo de Flutter.

## Requisitos
- Flutter 3.47 (la primera compilación descarga el NDK 28.2.13676358).
- Android Studio con un emulador **API 34 (Android 14), x86_64, Google APIs** o un teléfono Android con depuración USB.

Emulador probado en una Mac Intel: Pixel 6a, API 34, Graphics *Software*, RAM 2–4 GB. La imagen de API 37 se cerraba sola.

## Correrla en el emulador (desde la terminal)

```bash
# 1. Ver el nombre del emulador
~/Library/Android/sdk/emulator/emulator -list-avds

# 2. Encenderlo desde cero (cold boot), en segundo plano
~/Library/Android/sdk/emulator/emulator -avd Pixel_6a -no-snapshot-load &

# 3. Esperar a que Android termine de arrancar
~/Library/Android/sdk/platform-tools/adb wait-for-device
until [ "$(~/Library/Android/sdk/platform-tools/adb shell getprop sys.boot_completed 2>/dev/null)" = "1" ]; do sleep 2; done; echo "Emulador listo"

# 4. Compilar e instalar la app
cd movil
flutter pub get
flutter run --release -d emulator-5554
```

`--release` hace que la app vaya fluida en el emulador; en modo debug se traba. Con `q` se cierra la conexión y la app queda instalada en el emulador.

En Windows las rutas son `%LOCALAPPDATA%\Android\Sdk\emulator\emulator` y `...\platform-tools\adb`. También se puede encender el emulador con ▶ en *Device Manager* de Android Studio.

Si el emulador no responde («Process timed out», «Broken pipe»): cerrarlo, correr `adb kill-server` y `adb start-server`, y volver a encenderlo con *Cold Boot*.

## APK de release

```bash
flutter build apk
```

Queda en `build/app/outputs/flutter-apk/app-release.apk`. Para instalarlo en el emulador basta con arrastrarlo a su ventana.
