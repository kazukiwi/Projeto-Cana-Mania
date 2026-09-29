
## Pix no PDV

Instale as dependências com `python -m pip install -r requirements.txt`.
No seu `.env`, configure
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

## Gestão comercial e cardápio digital

- **/cardapio**: página pública, com fotos, preços, busca e tema claro/escuro.
  Mostra somente produtos ativos de categorias ativas Abre Alas, Enredo e
  Maníacos por Drink. Os pedidos são feitos no balcão.
- **/relatorios**: filtros por período, loja, operador e pagamento, totais por
  pagamento e por loja/operador, paginação e CSV compatível com Excel.
  Administradores consultam todos; funcionários consultam suas próprias vendas.
- **/caixa**: fundo de abertura, reforços, retiradas e conferências por data,
  loja e operador. Dinheiro esperado = abertura + vendas em dinheiro + reforços
  − retiradas. Cada conferência guarda um retrato dos valores e a diferença
  para o dinheiro contado. Vendas posteriores exigem nova conferência.
  Os lançamentos e conferências são feitos pelo próprio operador.
- **/auditoria**: histórico de preços e estoque, restrito a administradores.
  Registra alterações feitas pela aplicação a partir desta versão, incluindo
  vendas e transferências. Alterações diretas via SQL não passam por esse registro.

### PDV

O carrinho é recuperado ao recarregar a mesma aba, separado por usuário.
Os preços são atualizados a partir do catálogo ao recuperar um rascunho.
Após um envio sem confirmação, os dados ficam preservados para repetir o mesmo
pedido. Uma restrição única no banco impede duplicação e nova baixa de estoque.
Uma venda nova, mesmo com itens iguais, recebe outro identificador.

Atalhos: **F2** buscar, **F4** catálogo, **F8** pagamento, **F9** finalizar.
A recuperação exige que o navegador permita sessionStorage.

### Banco e valores monetários

Execute `python -B -m scripts.migrar_gestao` para criar um backup e testar
a migração em uma cópia do SQLite. Execute com `--aplicar` para atualizar
o banco local depois do ensaio. Os arquivos ficam em `backups/`, fora do Git.
Para outros ambientes, faça backup e execute `alembic upgrade head`.

Os cálculos de preços, vendas e caixa usam Decimal. O SQLite guarda dinheiro
em centavos inteiros; PostgreSQL usa NUMERIC(14,2). A aplicação apresenta os
valores em reais. Consultas SQL diretas ao SQLite precisam considerar os centavos.
Percentuais e quantidades não passam por essa conversão.

Vendas antigas mantêm seus valores, mas aparecem como loja não informada.
Não é possível atribuir retroativamente uma loja sem informação confiável.
Os relatórios usam o horário de Brasília.

### Verificação

`python -B -m unittest discover -s tests -v`

O teste de concorrência usa um banco temporário, sem alterar dados reais.
Verificação opcional de interface com Edge instalado:
`python -m pip install playwright` e `python -B -m scripts.verificar_interface`.
