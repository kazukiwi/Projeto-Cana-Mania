
## Pix no PDV

Instale as dependências com `python -m pip install -r requirements.txt`.
Copie as variáveis de `.env.pix.example` para o seu `.env` e preencha
`PIX_CHAVE`, `PIX_NOME_RECEBEDOR` e `PIX_CIDADE`. Reinicie o servidor.
A chave precisa estar cadastrada na conta que receberá os pagamentos.

No PDV, adicione os itens, selecione Pix e clique em **Gerar QR Code Pix**.
O valor é calculado no servidor pelos preços cadastrados. Alterar o carrinho
ou a loja remove o código exibido; gere outro código para o novo valor.
O QR Code é produzido localmente, sem enviar dados a serviços de imagens.

Confira o crédito na conta antes de finalizar a venda: o QR Code estático
não consulta o banco nem confirma o pagamento automaticamente. Um código já
copiado continua utilizável; não há expiração nem cancelamento bancário.
A geração não reserva estoque e não registra a venda.

Implementação baseada no [Manual de Padrões para Iniciação do Pix do Banco Central](https://www.bcb.gov.br/content/estabilidadefinanceira/pix/Regulamento_Pix/II_ManualdePadroesparaIniciacaodoPix.pdf).
Teste: `python -B -m unittest discover -s tests -v`.
