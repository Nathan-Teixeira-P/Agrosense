#include <Wire.h>
#include <Adafruit_BME280.h>  // instalar: Adafruit BME280 Library (Adafruit Unified Sensor junto)

#define INTERVALO_MS 2000

const float TEMP_OFFSET = 0;  // calibre se o termometro de referencia discordar

Adafruit_BME280 bme;  // I2C no Uno: SDA=A4, SCL=A5, VIN=5V, GND=GND

void setup() {
  Serial.begin(9600);
  if (!bme.begin(0x76) && !bme.begin(0x77)) Serial.println("ERRO: BME280 nao encontrado");
  delay(2000);
}

void loop() {
  float temp = bme.readTemperature() + TEMP_OFFSET;
  float umi = bme.readHumidity();
  float pres = bme.readPressure() / 100.0;  // Pa -> hPa
  // BMP280 vendido como BME280 nao tem umidade (NaN): nao envia a linha
  if (!isnan(temp) && !isnan(umi) && !isnan(pres)) {
    Serial.print(temp, 1); Serial.print(',');
    Serial.print(umi, 1); Serial.print(',');
    Serial.println(pres, 1);
  }
  delay(INTERVALO_MS);
}
