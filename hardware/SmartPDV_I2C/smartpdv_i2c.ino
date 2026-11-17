/*
 * SmartPDV RFID - saldo pre-pago de TESTE gravado em cartao MIFARE Classic.
 * Nao representa pagamento bancario. A leitura pode ser clonada; use somente teste.
 * LCD I2C: GND/GND, VCC/5V, SDA/A4, SCL/A5.
 * RC522: SS/D10, SCK/D13, MOSI/D11, MISO/D12, RST/D9, VCC/3.3V, GND comum.
 * Converta os sinais D10, D13, D11 e D9 de 5V para 3.3V antes do RC522.
 */
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <stdlib.h>
#include <string.h>

const byte RFID_SS = 10;
const byte RFID_RST = 9;
const byte BLOCO_SALDO = 4; // bloco de dados do setor 1 em MIFARE Classic
const unsigned long SALDO_MAXIMO = 99999999UL; // R$ 999.999,99
MFRC522 rfid(RFID_SS, RFID_RST);
LiquidCrystal_I2C lcd(0x27, 16, 2);
MFRC522::MIFARE_Key chaveA;

bool aguardandoTag = false;
unsigned long inicioOperacao = 0;
char operacao[12] = "";
unsigned long valorOperacao = 0;
char comando[40];
byte indice = 0;

void mostrarValor(const char *titulo, unsigned long centavos) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(titulo);
  lcd.print(" R$ ");
  lcd.print(centavos / 100);
  lcd.print(',');
  if (centavos % 100 < 10) lcd.print('0');
  lcd.print(centavos % 100);
  lcd.setCursor(0, 1);
  lcd.print("Aproxime cartao");
}

void mostrarSaldo(const char *titulo, unsigned long centavos) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(titulo);
  lcd.setCursor(0, 1);
  lcd.print("R$ ");
  lcd.print(centavos / 100);
  lcd.print(',');
  if (centavos % 100 < 10) lcd.print('0');
  lcd.print(centavos % 100);
}

void imprimirUID(char *uidTexto) {
  byte posicao = 0;
  for (byte i = 0; i < rfid.uid.size && posicao < 20; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uidTexto[posicao++] = '0';
    byte valor = rfid.uid.uidByte[i];
    const char hex[] = "0123456789ABCDEF";
    uidTexto[posicao++] = hex[(valor >> 4) & 0x0F];
    uidTexto[posicao++] = hex[valor & 0x0F];
  }
  uidTexto[posicao] = '\0';
}

bool tipoCompativel() {
  MFRC522::PICC_Type tipo = rfid.PICC_GetType(rfid.uid.sak);
  return tipo == MFRC522::PICC_TYPE_MIFARE_MINI ||
         tipo == MFRC522::PICC_TYPE_MIFARE_1K ||
         tipo == MFRC522::PICC_TYPE_MIFARE_4K;
}

bool autenticarBloco() {
  return rfid.PICC_Authenticate(MFRC522::PICC_CMD_MF_AUTH_KEY_A, BLOCO_SALDO, &chaveA, &(rfid.uid)) == MFRC522::STATUS_OK;
}

bool lerSaldo(unsigned long &saldo, bool &cartaoVirgem) {
  byte dados[18];
  byte tamanho = sizeof(dados);
  if (rfid.MIFARE_Read(BLOCO_SALDO, dados, &tamanho) != MFRC522::STATUS_OK) return false;
  bool todosFF = true;
  bool todosZero = true;
  for (byte i = 0; i < 16; i++) {
    if (dados[i] != 0xFF) todosFF = false;
    if (dados[i] != 0x00) todosZero = false;
  }
  cartaoVirgem = todosFF || todosZero;
  if (cartaoVirgem) { saldo = 0; return true; }
  if (dados[0] != 'C' || dados[1] != 'M' || dados[2] != 'N' || dados[3] != '1') return false;
  uint32_t valor = ((uint32_t)dados[4] << 24) | ((uint32_t)dados[5] << 16) | ((uint32_t)dados[6] << 8) | dados[7];
  for (byte i = 0; i < 4; i++) if (dados[8 + i] != (byte)~dados[4 + i]) return false;
  if (dados[12] != 0xA5 || dados[13] != 0x5A || dados[14] != 0xC3 || dados[15] != 0x3C || valor > SALDO_MAXIMO) return false;
  saldo = valor;
  return true;
}

bool gravarSaldo(unsigned long saldo) {
  byte dados[16] = {'C', 'M', 'N', '1'};
  dados[4] = (byte)(saldo >> 24); dados[5] = (byte)(saldo >> 16);
  dados[6] = (byte)(saldo >> 8);  dados[7] = (byte)saldo;
  for (byte i = 0; i < 4; i++) dados[8 + i] = (byte)~dados[4 + i];
  dados[12] = 0xA5; dados[13] = 0x5A; dados[14] = 0xC3; dados[15] = 0x3C;
  return rfid.MIFARE_Write(BLOCO_SALDO, dados, 16) == MFRC522::STATUS_OK;
}

void resultado(const char *codigo, const char *uid, unsigned long saldo) {
  Serial.print(codigo); Serial.print('|'); Serial.print(uid); Serial.print('|'); Serial.println(saldo);
}

void finalizarCartao() {
  char uid[21];
  imprimirUID(uid);
  if (!tipoCompativel()) {
    Serial.print("ERRO_CARTAO|"); Serial.print(uid); Serial.println("|TIPO_NAO_COMPATIVEL");
    lcd.clear(); lcd.print("Cartao incompativel"); lcd.setCursor(0, 1); lcd.print("Use MIFARE Classic");
    return;
  }
  if (!autenticarBloco()) {
    Serial.print("ERRO_CARTAO|"); Serial.print(uid); Serial.println("|CHAVE");
    lcd.clear(); lcd.print("Falha ao acessar"); lcd.setCursor(0, 1); lcd.print("setor do cartao");
    return;
  }
  unsigned long saldo = 0;
  bool virgem = false;
  if (!lerSaldo(saldo, virgem)) {
    Serial.print("ERRO_CARTAO|"); Serial.print(uid); Serial.println("|DADOS_INVALIDOS");
    lcd.clear(); lcd.print("Dados invalidos"); lcd.setCursor(0, 1); lcd.print("Cartao nao alterado");
    return;
  }
  if (strcmp(operacao, "CARREGAR") == 0) {
    if (valorOperacao > SALDO_MAXIMO - saldo) {
      resultado("ERRO_CARTAO", uid, saldo);
      lcd.clear(); lcd.print("Limite excedido"); lcd.setCursor(0, 1); lcd.print("Carga cancelada");
      return;
    }
    unsigned long novoSaldo = saldo + valorOperacao;
    if (!gravarSaldo(novoSaldo)) {
      resultado("ERRO_CARTAO", uid, saldo);
      lcd.clear(); lcd.print("Falha ao gravar"); lcd.setCursor(0, 1); lcd.print("Tente novamente");
      return;
    }
    resultado("SALDO_CARREGADO", uid, novoSaldo);
    mostrarSaldo("Saldo carregado", novoSaldo);
  } else {
    if (virgem || saldo < valorOperacao) {
      resultado("SALDO_INSUFICIENTE", uid, saldo);
      mostrarSaldo("Saldo insuficiente", saldo);
      return;
    }
    unsigned long novoSaldo = saldo - valorOperacao;
    if (!gravarSaldo(novoSaldo)) {
      resultado("ERRO_CARTAO", uid, saldo);
      lcd.clear(); lcd.print("Falha ao debitar"); lcd.setCursor(0, 1); lcd.print("Tente novamente");
      return;
    }
    resultado("APROVADO", uid, novoSaldo);
    mostrarSaldo("Compra aprovada", novoSaldo);
  }
}

void processarComando(char *linha) {
  char *separador = strchr(linha, '|');
  if (!separador) return;
  *separador = '\0';
  char *fim;
  unsigned long centavos = strtoul(separador + 1, &fim, 10);
  if (*fim != '\0' || centavos < 1 || centavos > 999999) {
    Serial.println("ERRO|VALOR"); return;
  }
  if (strcmp(linha, "PAGAR") != 0 && strcmp(linha, "CARREGAR") != 0) return;
  strncpy(operacao, linha, sizeof(operacao) - 1);
  operacao[sizeof(operacao) - 1] = '\0';
  valorOperacao = centavos;
  aguardandoTag = true;
  inicioOperacao = millis();
  mostrarValor(strcmp(operacao, "CARREGAR") == 0 ? "Carga" : "Pagar", centavos);

  Serial.println("AGUARDANDO");
}

void setup() {
  Serial.begin(9600);
  Wire.begin();
  lcd.init(); lcd.backlight();
  lcd.clear(); lcd.print("SmartPDV RFID"); lcd.setCursor(0, 1); lcd.print("Aguardando PDV");
  SPI.begin(); rfid.PCD_Init();
  for (byte i = 0; i < 6; i++) chaveA.keyByte[i] = 0xFF;
  delay(80);
  Serial.println("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') { comando[indice] = '\0'; processarComando(comando); indice = 0; }
    else if (indice < sizeof(comando) - 1) comando[indice++] = c;
    else indice = 0;
  }
  if (aguardandoTag && millis() - inicioOperacao > 120000UL) {
    aguardandoTag = false; lcd.clear(); lcd.print("Tempo esgotado");
    Serial.println("EXPIRADO");
  }
  if (aguardandoTag && rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    aguardandoTag = false;
    finalizarCartao();
    rfid.PICC_HaltA();
    rfid.PCD_StopCrypto1();
  }
}