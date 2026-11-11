#include <Wire.h>
#include <Adafruit_BME280.h>

#define INTERVALO_MS 2000

const float TEMP_OFFSET = 0;

Adafruit_BME280 bme;

void setup() {
  Serial.begin(9600);
  if (!bme.begin(0x76) && !bme.begin(0x77)) Serial.println("ERRO: BME280 nao encontrado");
  delay(2000);
}

void loop() {
  float temp = bme.readTemperature() + TEMP_OFFSET;
  float umi = bme.readHumidity();
  float pres = bme.readPressure() / 100.0;
  if (!isnan(temp) && !isnan(umi) && !isnan(pres)) {
    Serial.print(temp, 1); Serial.print(',');
    Serial.print(umi, 1); Serial.print(',');
    Serial.println(pres, 1);
  } else {
    Serial.println("ERRO: leitura invalida do BME280 (fiacao ou modulo BMP280 sem umidade?)");
  }
  delay(INTERVALO_MS);
}
