/*
 * Diagnostico seguro: identifica o tipo e o UID do cartao via RC522.
 * Nao grava nem altera dados do cartao.
 * RC522: SS D10, RST D9, SCK D13, MOSI D11, MISO D12, VCC 3.3V.
 * Converta os sinais 5V do Uno (D10, D11, D13 e D9) para 3.3V.
 */
#include <SPI.h>
#include <MFRC522.h>

const byte RFID_SS = 10;
const byte RFID_RST = 9;
MFRC522 leitor(RFID_SS, RFID_RST);

void setup() {
  Serial.begin(9600);
  SPI.begin();
  leitor.PCD_Init();
  delay(100);
  Serial.println("RFID_READER_READY");
  Serial.println("Aproxime um cartao; este teste so identifica UID e tipo.");
}

void loop() {
  if (!leitor.PICC_IsNewCardPresent() || !leitor.PICC_ReadCardSerial()) {
    delay(30);
    return;
  }

  Serial.print("UID=");
  for (byte i = 0; i < leitor.uid.size; i++) {
    if (leitor.uid.uidByte[i] < 0x10) Serial.print('0');
    Serial.print(leitor.uid.uidByte[i], HEX);
  }
  Serial.print(" TYPE=");
  Serial.println(leitor.PICC_GetTypeName(leitor.PICC_GetType(leitor.uid.sak)));

  leitor.PICC_HaltA();
  leitor.PCD_StopCrypto1();
  delay(800);
}