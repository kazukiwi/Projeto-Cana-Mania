/*
 * Cana Mania - RFID de saldo ficticio controlado pelo banco do sistema.
 * O UID identifica o cartao; nenhum saldo/dado e gravado no chip.
 * LCD I2C: GND/GND, VCC/5V, SDA/A4, SCL/A5.
 * RC522: SS/D10, SCK/D13, MOSI/D11, MISO/D12, RST/D9, VCC/3.3V, GND comum.
 * Use conversao de nivel 5V->3.3V nos sinais do Uno para o RC522.
 */
#include <Wire.h>
#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>
#include <stdlib.h>
#include <string.h>

const byte RFID_SS = 10;
const byte RFID_RST = 9;
const unsigned long TIMEOUT_TAG = 120000UL;
const unsigned long TIMEOUT_CADASTRO = 180000UL;
const unsigned long TIMEOUT_PAGAMENTO = 15000UL;
const unsigned long TEMPO_RESULTADO = 5000UL;
const unsigned long VELOCIDADE_BOAS_VINDAS = 280UL;
MFRC522 rfid(RFID_SS, RFID_RST);
LiquidCrystal_I2C lcd(0x27, 16, 2);

enum Estado { OCIOSO, EXIBINDO_RESULTADO, ESPERANDO_TAG_IDENTIFICAR, ESPERANDO_TAG_PAGAR, ESPERANDO_CONFIRMACAO, ESPERANDO_RESPOSTA_PAGAMENTO };
Estado estado = OCIOSO;
unsigned long iniciadoEm = 0;
char linhaSerial[64];
byte indiceSerial = 0;
unsigned long valorPendente = 0;
char codigoPedido[7] = "";
bool exibindoCodigo = false;
unsigned long ultimaTroca = 0;
unsigned long resultadoIniciadoEm = 0;
unsigned long ultimoPassoBoasVindas = 0;
int posicaoBoasVindas = -16;
const char mensagemBoasVindas[] = "Seja bem-vindo ao Cana Mania";
char comandoPendente[64] = "";

void mostrar(const char *linha1, const char *linha2) {
  lcd.clear(); lcd.setCursor(0, 0); lcd.print(linha1); lcd.setCursor(0, 1); lcd.print(linha2);
}

void iniciarBoasVindas() {
  estado = OCIOSO;
  posicaoBoasVindas = -16;
  ultimoPassoBoasVindas = millis() - VELOCIDADE_BOAS_VINDAS;
  lcd.clear();
}

void animarBoasVindas() {
  if (millis() - ultimoPassoBoasVindas < VELOCIDADE_BOAS_VINDAS) return;
  ultimoPassoBoasVindas = millis();
  char linha[17];
  const int tamanho = strlen(mensagemBoasVindas);
  for (byte i = 0; i < 16; i++) {
    int indice = posicaoBoasVindas + i;
    linha[i] = (indice >= 0 && indice < tamanho) ? mensagemBoasVindas[indice] : ' ';
  }
  linha[16] = '\0';
  lcd.setCursor(0, 0);
  lcd.print(linha);
  posicaoBoasVindas++;
  if (posicaoBoasVindas > tamanho) posicaoBoasVindas = -16;
}

void exibirResultado() {
  estado = EXIBINDO_RESULTADO;
  resultadoIniciadoEm = millis();
}

void telaAguardarTag(bool pagamento) {
  if (pagamento) mostrar("Compra teste", "Aproxime cartao");
  else mostrar("Cadastro / saldo", "Aproxime a tag");
}

void telaPagamento(unsigned long centavos) {
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("R$ ");
  lcd.print(centavos / 100);
  lcd.print(',');
  if (centavos % 100 < 10) lcd.print('0');
  lcd.print(centavos % 100);
  lcd.setCursor(0, 1);
  if (exibindoCodigo && codigoPedido[0]) {
    lcd.print("Pedido: "); lcd.print(codigoPedido);
  } else lcd.print("Aproxime cartao");
}

bool obterCentavos(const char *texto, unsigned long &valor) {
  if (!texto || !*texto) return false;
  for (const char *p = texto; *p; ++p) if (*p < '0' || *p > '9') return false;
  char *fim = NULL;
  valor = strtoul(texto, &fim, 10);
  return fim && *fim == '\0' && valor <= 2147483647UL;
}

void mostrarSaldo(const char *titulo, unsigned long centavos) {
  lcd.clear(); lcd.setCursor(0, 0); lcd.print(titulo);
  lcd.setCursor(0, 1); lcd.print("R$ "); lcd.print(centavos / 100); lcd.print(',');
  if (centavos % 100 < 10) lcd.print('0');
  lcd.print(centavos % 100);
}

void mostrarUID() {
  Serial.print("TAG|");
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) Serial.print('0');
    Serial.print(rfid.uid.uidByte[i], HEX);
  }
  Serial.println();
}

void cancelar(const char *mensagem) {
  comandoPendente[0] = '\0';
  mostrar(mensagem, "Tente novamente");
  exibirResultado();
  Serial.println("RESULT|CANCELADO");
}

void processar(const char *linha) {
  if (strcmp(linha, "PING") == 0) { Serial.println("PONG"); return; }
  if (strcmp(linha, "CANCELAR") == 0) {
    if (estado == EXIBINDO_RESULTADO && comandoPendente[0]) {
      comandoPendente[0] = '\0'; Serial.println("RESULT|CANCELADO"); return;
    }
    cancelar("Leitura cancelada"); return;
  }

  // A próxima venda pode chegar imediatamente da fila; não interromper a mensagem atual.
  if (estado == EXIBINDO_RESULTADO && (strcmp(linha, "IDENTIFICAR") == 0 || strncmp(linha, "PAGAR|", 6) == 0)) {
    strncpy(comandoPendente, linha, sizeof(comandoPendente) - 1);
    comandoPendente[sizeof(comandoPendente) - 1] = '\0';
    return;
  }

  if (strcmp(linha, "IDENTIFICAR") == 0) {
    estado = ESPERANDO_TAG_IDENTIFICAR; iniciadoEm = millis();
    telaAguardarTag(false); Serial.println("AGUARDANDO|IDENTIFICAR"); return;
  }
  if (strncmp(linha, "PAGAR|", 6) == 0) {
    unsigned long cents;
    char valorTexto[16];
    const char *separador = strchr(linha + 6, '|');
    size_t tamanho = separador ? (size_t)(separador - (linha + 6)) : strlen(linha + 6);
    if (tamanho == 0 || tamanho >= sizeof(valorTexto)) { Serial.println("ERRO|VALOR"); return; }
    memcpy(valorTexto, linha + 6, tamanho); valorTexto[tamanho] = '\0';
    if (!obterCentavos(valorTexto, cents)) { Serial.println("ERRO|VALOR"); return; }
    codigoPedido[0] = '\0';
    if (separador) { strncpy(codigoPedido, separador + 1, 6); codigoPedido[6] = '\0'; }
    valorPendente = cents; exibindoCodigo = false; ultimaTroca = millis();
    estado = ESPERANDO_TAG_PAGAR; iniciadoEm = millis();
    telaPagamento(cents); Serial.println("AGUARDANDO|PAGAR"); return;
  }

  unsigned long saldo;
  if (strncmp(linha, "CADASTRO_OK|", 12) == 0 && obterCentavos(linha + 12, saldo)) {
    mostrarSaldo("Cartao cadastrado", saldo); exibirResultado(); Serial.println("RESULT|CADASTRO_OK"); return;
  }
  if (strncmp(linha, "RECARGA_OK|", 11) == 0 && obterCentavos(linha + 11, saldo)) {
    mostrarSaldo("Recarga confirmada", saldo); exibirResultado(); Serial.println("RESULT|RECARGA_OK"); return;
  }
  if (strncmp(linha, "SALDO|", 6) == 0 && obterCentavos(linha + 6, saldo)) {
    mostrarSaldo("Saldo disponivel", saldo); exibirResultado(); Serial.println("RESULT|SALDO"); return;
  }
  if (strncmp(linha, "APROVADO|", 9) == 0 && obterCentavos(linha + 9, saldo)) {
    mostrar("Compra aprovada", ""); exibirResultado(); Serial.println("RESULT|APROVADO"); return;
  }
  if (strncmp(linha, "BRINDE|", 7) == 0 && obterCentavos(linha + 7, saldo)) {
    mostrar("Compra aprovada", ""); exibirResultado(); Serial.println("RESULT|BRINDE"); return;
  }
  if (strncmp(linha, "NEGADO|SALDO_INSUFICIENTE|", 26) == 0 && obterCentavos(linha + 26, saldo)) {
    mostrarSaldo("Saldo insuficiente", saldo); exibirResultado(); Serial.println("RESULT|NEGADO|SALDO_INSUFICIENTE"); return;
  }
  if (strcmp(linha, "NEGADO|NAO_CADASTRADO") == 0) {
    mostrar("Cartao nao", "cadastrado"); exibirResultado(); Serial.println("RESULT|NEGADO|NAO_CADASTRADO"); return;
  }
  if (strncmp(linha, "NEGADO|", 7) == 0) {
    mostrar("Compra negada", "Sem alteracao"); exibirResultado(); Serial.println("RESULT|NEGADO"); return;
  }
  Serial.println("ERRO|COMANDO");
}

void setup() {
  Serial.begin(9600); Wire.begin(); lcd.init(); lcd.backlight();
  SPI.begin(); rfid.PCD_Init();
  iniciarBoasVindas();
  delay(80); Serial.println("READY");
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') { linhaSerial[indiceSerial] = '\0'; processar(linhaSerial); indiceSerial = 0; }
    else if (indiceSerial < sizeof(linhaSerial) - 1) linhaSerial[indiceSerial++] = c;
    else { indiceSerial = 0; Serial.println("ERRO|LINHA_LONGA"); }
  }

  if (estado == OCIOSO) { animarBoasVindas(); return; }
  if (estado == EXIBINDO_RESULTADO) {
    if (millis() - resultadoIniciadoEm >= TEMPO_RESULTADO) {
      iniciarBoasVindas();
      if (comandoPendente[0]) {
        char proximoComando[sizeof(comandoPendente)];
        strcpy(proximoComando, comandoPendente);
        comandoPendente[0] = '\0';
        processar(proximoComando);
      }
    }
    return;
  }
  if (estado == ESPERANDO_TAG_PAGAR && codigoPedido[0] && millis() - ultimaTroca >= 2500UL) {
    exibindoCodigo = !exibindoCodigo; ultimaTroca = millis(); telaPagamento(valorPendente);
  }
  unsigned long limite = (estado == ESPERANDO_TAG_IDENTIFICAR || estado == ESPERANDO_TAG_PAGAR) ? TIMEOUT_TAG :
                         (estado == ESPERANDO_CONFIRMACAO ? TIMEOUT_CADASTRO : TIMEOUT_PAGAMENTO);
  if (millis() - iniciadoEm >= limite) {
    mostrar("Tempo esgotado", "Inicie novamente"); exibirResultado(); Serial.println("EXPIRADO"); return;
  }

  if ((estado == ESPERANDO_TAG_IDENTIFICAR || estado == ESPERANDO_TAG_PAGAR) &&
      rfid.PICC_IsNewCardPresent() && rfid.PICC_ReadCardSerial()) {
    bool pagar = estado == ESPERANDO_TAG_PAGAR;
    mostrarUID(); rfid.PICC_HaltA(); rfid.PCD_StopCrypto1();
    iniciadoEm = millis();
    estado = pagar ? ESPERANDO_RESPOSTA_PAGAMENTO : ESPERANDO_CONFIRMACAO;
    mostrar("Cartao lido", "Aguarde sistema");
  }
}
