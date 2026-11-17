# SmartPDV RFID — saldo local no cartão de teste

Este fluxo grava saldo de teste no próprio cartão e pode debitar o total de uma venda do PDV. Ele não processa pagamentos bancários. Use apenas cartões de teste: MIFARE Classic com chave A padrão `FFFFFFFFFFFF`; o firmware grava um registro no bloco de dados 4. O RC522 detecta outras famílias, mas elas são recusadas por este formato.

## Preparação

1. Instale as dependências do site com `python -m pip install -r requirements.txt`.
2. No Arduino IDE, carregue `smartpdv_i2c.ino` em um Arduino Uno na porta configurada em `ARDUINO_PORT` (COM5 no computador configurado). Bibliotecas: MFRC522 e LiquidCrystal_I2C.
3. Feche o Monitor Serial e reinicie o site para liberar a porta serial.
4. Administrador: no PDV, informe um valor em **Carregar saldo no cartão de teste**, clique no botão e aproxime o cartão. O saldo fica no bloco 4 do cartão.
5. No PDV, monte o carrinho e clique **Pagar com cartão RFID**. Aproxime o cartão. Se o saldo cobrir o total, o firmware debita e o site finaliza a venda, baixa o estoque e abre o recibo.

## Fiação

LCD I2C: SDA no A4, SCL no A5, VCC 5 V e GND comum. RC522: SS D10, RST D9, SCK D13, MOSI D11, MISO D12, VCC 3,3 V e GND comum. Converta os sinais D10, D13, D11 e D9 de 5 V para 3,3 V antes do RC522. Nunca alimente o RC522 com 5 V. O LCD usa endereço I2C 0x27 por padrão; alguns módulos usam 0x3F.