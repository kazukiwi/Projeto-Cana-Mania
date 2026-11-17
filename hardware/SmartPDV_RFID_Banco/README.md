# Cana Mania RFID: saldo no banco de dados

Este sketch identifica tags e recebe respostas pela Serial USB. Ele **não grava saldo no cartão**. Saldos e lançamentos ficam no banco SQLAlchemy do Cana Mania. Trata-se de saldo fictício para demonstração, não de pagamento bancário.

## IDE Arduino

1. Abra `smartpdv_rfid_banco.ino` desta pasta. Não abra o sketch legado em `SmartPDV_I2C` para este fluxo.
2. Instale as bibliotecas **MFRC522** e **LiquidCrystal_I2C**.
3. Selecione **Arduino Uno** e a porta USB do leitor (por exemplo, COM5), feche o Monitor Serial e carregue o sketch.
4. Configure `ARDUINO_PORT` no ambiente do servidor Cana Mania. O servidor precisa ter acesso local à mesma porta USB.
5. Reinicie o Cana Mania. A tela administrativa **Cartões RFID** permite ler, cadastrar, consultar e recarregar. O PDV permite uma compra simulada.

## Protocolo serial (9600 baud, linhas terminadas em LF)

| Servidor → Arduino | Arduino → servidor |
| --- | --- |
| `PING` | `PONG` |
| `IDENTIFICAR` | `AGUARDANDO|IDENTIFICAR`, depois `TAG|UID` |
| `PAGAR|centavos` | `AGUARDANDO|PAGAR`, depois `TAG|UID` |
| `CADASTRO_OK|saldo_total` | `RESULT|CADASTRO_OK` |
| `RECARGA_OK|saldo_total` | `RESULT|RECARGA_OK` |
| `SALDO|saldo_total` | `RESULT|SALDO` |
| `APROVADO|saldo_restante` | `RESULT|APROVADO` |
| `NEGADO|SALDO_INSUFICIENTE|saldo_atual` | `RESULT|NEGADO|SALDO_INSUFICIENTE` |
| `NEGADO|NAO_CADASTRADO` | `RESULT|NEGADO|NAO_CADASTRADO` |
| `CANCELAR` | `RESULT|CANCELADO` |

A espera pela tag é de até 120 segundos. Depois da leitura, o Arduino aguarda até 180 segundos para cadastro/recarga e 15 segundos para o resultado da compra. `READY`, `EXPIRADO` e `ERRO|...` são mensagens de estado/erro.

## Ligações

LCD I2C: SDA em A4, SCL em A5, VCC em 5 V e GND comum. RC522: SS D10, RST D9, SCK D13, MOSI D11, MISO D12, VCC 3,3 V e GND comum. Faça conversão de nível de 5 V para 3,3 V nas linhas do Uno que entram no RC522. Nunca ligue o RC522 em 5 V.

O UID serve apenas como identificador do registro. Não é autenticação segura; não use este mecanismo para valores reais.
