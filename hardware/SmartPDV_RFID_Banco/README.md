# Cana Mania RFID: saldo no banco de dados

Este sketch identifica tags e recebe respostas pela Serial USB. Ele **não grava saldo no cartão**. Saldos e lançamentos ficam no banco SQLAlchemy do Cana Mania. Trata-se de saldo fictício para demonstração, não de pagamento bancário.

## IDE Arduino

1. Abra `smartpdv_rfid_banco.ino` desta pasta. Não abra o sketch legado em `SmartPDV_I2C` para este fluxo.
2. Instale as bibliotecas **MFRC522** e **LiquidCrystal_I2C**.
3. Selecione **Arduino Uno** e a porta USB do leitor (por exemplo, COM5), feche o Monitor Serial e carregue o sketch.
4. Configure `ARDUINO_PORT` no ambiente do servidor Cana Mania. O servidor precisa ter acesso local à mesma porta USB.
5. Instale as dependências (`pip install -r requirements.txt`), aplique as migrações (`alembic upgrade head`) e reinicie o Cana Mania. A tela administrativa **Cartões RFID** permite ler, cadastrar, consultar e recarregar. A venda aguarda a confirmação e o comprovante será exibido em seguida.

No PDV, selecione débito, crédito, Pix ou cortesia. A confirmação por cartão usa o saldo fictício cadastrado; Pix e cortesia também podem ser confirmados pelo QR Code do sistema, sem cobrança bancária. Na cortesia, o cartão não é debitado e a mensagem de brinde aparece no comprovante e, conforme a opção escolhida, no celular ou no visor da maquininha. O pagamento dividido não está disponível neste fluxo.

Para usar o QR Code no celular, o computador e o celular precisam estar na mesma rede, o servidor deve aceitar conexões nessa rede e o PDV deve ser acessado pelo endereço IP do computador, não por `localhost`. O código usa o mesmo endereço pelo qual o PDV foi aberto e expira após dois minutos. Reiniciar o servidor invalida confirmações pendentes.

## Pedidos pelo celular e fila

1. Na conta da equipe, abra **QR para clientes** no menu. Clientes podem criar sua própria conta, entrar em uma conta existente ou continuar como visitantes sem cadastro. O administrador também pode criar contas em **Usuários → Novo usuário**, com perfil **Cliente**.
2. No computador conectado ao Arduino, inicie o sistema com `uvicorn app.main:app --host 0.0.0.0 --port 8000`. Use um único processo, pois a porta USB e a fila pertencem a esse processo.
3. Com os aparelhos na mesma rede, leia o QR Code ou consulte o IPv4 do computador com `ipconfig` e acesse `http://IP-DO-COMPUTADOR:8000/acesso/` pelo celular. O firewall precisa permitir essa conexão na rede local. Cada cliente vê o catálogo e os próprios comprovantes. O comprovante do visitante fica disponível somente durante a sessão; uma conta cadastrada permite consultá-lo novamente depois do login.
4. Para débito ou crédito simulados, os pedidos aguardam em fila. O cliente acompanha a posição e recebe um código quando chega sua vez. O visor alterna entre a instrução para aproximar o cartão e o código do pedido: confira os códigos antes de encostar o cartão. É necessário carregar novamente este sketch no Arduino para exibir o código.

O código no visor ajuda a identificar o pedido, mas o leitor não verifica se o cartão pertence à conta do cliente. A equipe deve conferir o código antes de cada leitura. Os pagamentos são fictícios. A fila fica na memória: uma reinicialização interrompe os pedidos ainda pendentes, que devem ser feitos novamente. Use essa configuração de rede apenas para testes controlados; para disponibilizar o sistema ao público, configure HTTPS, uma chave `SECRET_KEY` forte e persistente e uma implantação apropriada.

O QR Code usa o endereço pelo qual a página foi aberta, ou tenta descobrir o IPv4 local quando acessada por `localhost`. Se houver mais de uma rede ou proxy, defina `ACESSO_PUBLICO_URL` com o endereço base correto, por exemplo `http://192.168.1.10:8000`, e reinicie o servidor.

## Protocolo serial (9600 baud, linhas terminadas em LF)

| Servidor → Arduino | Arduino → servidor |
| --- | --- |
| `PING` | `PONG` |
| `IDENTIFICAR` | `AGUARDANDO|IDENTIFICAR`, depois `TAG|UID` |
| `PAGAR|centavos|codigo` (0 para cortesia) | `AGUARDANDO|PAGAR`, depois `TAG|UID` |
| `CADASTRO_OK|saldo_total` | `RESULT|CADASTRO_OK` |
| `RECARGA_OK|saldo_total` | `RESULT|RECARGA_OK` |
| `SALDO|saldo_total` | `RESULT|SALDO` |
| `APROVADO|saldo_restante` | `RESULT|APROVADO` |
| `BRINDE|saldo_restante` | `RESULT|BRINDE` |
| `NEGADO|SALDO_INSUFICIENTE|saldo_atual` | `RESULT|NEGADO|SALDO_INSUFICIENTE` |
| `NEGADO|NAO_CADASTRADO` | `RESULT|NEGADO|NAO_CADASTRADO` |
| `CANCELAR` | `RESULT|CANCELADO` |

A espera pela tag é de até 120 segundos. Depois da leitura, o Arduino aguarda até 180 segundos para cadastro/recarga e 15 segundos para o resultado da compra. `READY`, `EXPIRADO` e `ERRO|...` são mensagens de estado/erro.

Ao receber `PAGAR`, o visor mostra o valor em reais na primeira linha e `Aproxime cartao` na segunda. Após alterar o sketch, envie-o novamente ao Arduino pela IDE; feche o Monitor Serial antes de usar o sistema.

## Ligações

LCD I2C: SDA em A4, SCL em A5, VCC em 5 V e GND comum. RC522: SS D10, RST D9, SCK D13, MOSI D11, MISO D12, VCC 3,3 V e GND comum. Faça conversão de nível de 5 V para 3,3 V nas linhas do Uno que entram no RC522. Nunca ligue o RC522 em 5 V.

O UID serve apenas como identificador do registro. Não é autenticação segura; não use este mecanismo para valores reais.
