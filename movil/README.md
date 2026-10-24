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

## Correrla
Requiere Flutter 3.47 y un emulador o teléfono Android (la primera compilación pide el NDK 28.2.13676358).

    flutter pub get
    flutter run

APK de release:

    flutter build apk

queda en `build/app/outputs/flutter-apk/app-release.apk`.
