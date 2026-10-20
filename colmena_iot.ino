const int PIN_TEMP_INTERNA = A0;  // TMP36 dentro de la colmena
const int PIN_TEMP_EXTERNA = A1;  // TMP36 a la sombra afuera
const int PIN_PESO = A2;          // sensor de fuerza bajo la base
const int PIN_GAS = A3;
const int PIN_LUZ = A4;           // fotorresistor afuera
const int PIN_PIR = 2;            // PIR apuntando a la piquera

const unsigned long INTERVALO_MS = 2000;
const float PESO_MAX_KG = 40.0;  // peso que corresponde a la lectura 1023
const int MUESTRAS_PIR = 20;     // lecturas del PIR dentro de cada intervalo

float leer_tmp36(int pin) {
  float voltaje = analogRead(pin) * 5.0 / 1024.0;  // ADC de 10 bits
  return (voltaje - 0.5) * 100.0;                  // formula del TMP36
}

float leer_peso_kg() {
  return analogRead(PIN_PESO) * PESO_MAX_KG / 1023.0;  // calibrar con un peso conocido
}

int leer_luz_pct() {
  return constrain(map(analogRead(PIN_LUZ), 0, 1023, 0, 100), 0, 100);
}

// Muestrea el PIR durante el intervalo y devuelve el porcentaje con movimiento
int medir_actividad_pct() {
  int detecciones = 0;
  for (int i = 0; i < MUESTRAS_PIR; i++) {
    if (digitalRead(PIN_PIR) == HIGH) detecciones++;
    delay(INTERVALO_MS / MUESTRAS_PIR);  // este ciclo marca el ritmo de envio
  }
  return detecciones * 100 / MUESTRAS_PIR;
}

void setup() {
  Serial.begin(9600);
  pinMode(PIN_PIR, INPUT);
  Serial.println("# colmena-iot listo");  // la PC ignora lineas con #
}

void loop() {
  int actividad = medir_actividad_pct();
  Serial.print("DATA,");
  Serial.print(leer_tmp36(PIN_TEMP_INTERNA), 2);
  Serial.print(',');
  Serial.print(leer_tmp36(PIN_TEMP_EXTERNA), 2);
  Serial.print(',');
  Serial.print(leer_peso_kg(), 2);
  Serial.print(',');
  Serial.print(actividad);
  Serial.print(',');
  Serial.print(analogRead(PIN_GAS));
  Serial.print(',');
  Serial.println(leer_luz_pct());
}