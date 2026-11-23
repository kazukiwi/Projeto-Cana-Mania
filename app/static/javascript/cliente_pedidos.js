(() => {
    const form = document.getElementById('pedido');
    const enviar = document.getElementById('enviar');
    const status = document.getElementById('status');
    const titulo = document.getElementById('titulo');
    const acompanhamento = document.getElementById('acompanhamento');
    const codigoEl = document.getElementById('codigo-pedido');
    const statusPagamento = document.getElementById('status-pagamento');
    const qrImagem = document.getElementById('qr-pagamento');
    const qrLink = document.getElementById('qr-pagamento-link');
    const comprovante = document.getElementById('comprovante-pedido');
    const total = document.getElementById('total');
    const itensResumo = document.getElementById('pedido-itens');
    const quantidades = [...document.querySelectorAll('[data-produto]')];
    async function lerResposta(response) {
        const corpo = await response.text();
        try { return JSON.parse(corpo); }
        catch (_) {
            if (response.redirected || /<!doctype html|<html/i.test(corpo)) {
                throw new Error('O servidor retornou uma pagina HTML em vez do resultado do pedido. Atualize a tela e entre novamente se a sessao expirou.');
            }
            throw new Error(`Resposta invalida do servidor (HTTP ${response.status}).`);
        }
    }
    const moeda = value => (value / 100).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    const valor = () => quantidades.reduce((sum, input) => sum + Math.round(Number(input.dataset.preco) * 100) * Number(input.value || 0), 0);
    function atualizarResumo() {
        total.textContent = moeda(valor());
        const selecionados = quantidades.filter(input => Number(input.value) > 0);
        if (!selecionados.length) {
            const linha = document.createElement('tr'); const celula = document.createElement('td');
            celula.colSpan = 3; celula.className = 'cliente-pdv-vazio'; celula.textContent = 'Adicione produtos ao carrinho.';
            linha.append(celula); itensResumo.replaceChildren(linha); return;
        }
        itensResumo.replaceChildren(...selecionados.map(input => {
            const qtd = Number(input.value); const linha = document.createElement('tr');
            const nome = document.createElement('td'); nome.textContent = input.dataset.nome;
            const quantidade = document.createElement('td'); quantidade.textContent = String(qtd);
            const subtotal = document.createElement('td'); subtotal.textContent = moeda(Math.round(Number(input.dataset.preco) * 100) * qtd);
            linha.append(nome, quantidade, subtotal); return linha;
        }));
    }
    quantidades.forEach(input => input.addEventListener('input', atualizarResumo)); atualizarResumo();

    function mostrarPagamentoEmAndamento(pagamento, pedido) {
        statusPagamento.hidden = false;
        qrImagem.hidden = !pedido.qr_url || pagamento.status !== 'aguardando_qr';
        qrLink.hidden = !pedido.qr_url;
        if (pedido.qr_url) { qrImagem.src = `/cliente/pedidos/${encodeURIComponent(pedido.codigo)}/qr`; qrLink.href = pedido.qr_url; }
        if (pagamento.status === 'aprovado' && pagamento.venda_id) {
            titulo.textContent = 'Pagamento aprovado!';
            statusPagamento.textContent = 'Seu pagamento foi confirmado.';
            comprovante.href = `/pdv/venda/${pagamento.venda_id}`; comprovante.hidden = false;
            sessionStorage.removeItem('pedido_cliente_pendente');
            sessionStorage.removeItem('operacao_cliente_pendente'); return;
        }
        if (['negado_saldo_insuficiente', 'expirado', 'erro_comunicacao', 'cancelado'].includes(pagamento.status)) {
            titulo.textContent = 'Pagamento nao concluido';
            titulo.textContent = 'Pagamento precisa de ajuda';
            statusPagamento.textContent = 'Avise a equipe no balcao para tentar novamente.';
            setTimeout(() => acompanhar(pedido.codigo), 4000); return;
        }
        titulo.textContent = 'Pagamento em andamento';
        statusPagamento.textContent = pagamento.status === 'na_fila' ? 'Aguarde sua vez na maquininha.' :
            (pagamento.status === 'aguardando_qr' ? 'Leia o QR Code Pix para confirmar.' : 'Aproxime seu cartao na maquininha.');
        if (pedido.qr_url) { qrLink.href = pedido.qr_url; qrLink.hidden = false; }
        setTimeout(() => acompanhar(pedido.codigo), 1500);
    }

    async function acompanhar(codigo) {
        acompanhamento.hidden = false; enviar.disabled = true; codigoEl.textContent = codigo;
        try {
            const response = await fetch(`/cliente/pedidos/${encodeURIComponent(codigo)}`, {cache: 'no-store'});
            const pedido = await lerResposta(response);
            if (!response.ok) throw new Error(pedido.detail || 'Nao foi possivel consultar o pedido.');
            if (pedido.status === 'aguardando') {
                titulo.textContent = 'Aguarde ser chamado'; status.textContent = `Seu pedido ${codigo} foi enviado. Aguarde a equipe chamar seu codigo.`;
                enviar.disabled = true;
                setTimeout(() => acompanhar(codigo), 4000); return;
            }
            if (pedido.status === 'chamado') {
                titulo.textContent = 'Voce foi chamado!'; status.textContent = 'Dirija-se ao balcao. A equipe vai confirmar o pagamento.';
                statusPagamento.hidden = true; enviar.disabled = true; setTimeout(() => acompanhar(codigo), 4000); return;
            }
            if (pedido.pagamento) {
                mostrarPagamentoEmAndamento(pedido.pagamento, pedido); return;
            }
            titulo.textContent = 'Pagamento em andamento'; status.textContent = 'Atualizando o status do pagamento...';
            setTimeout(() => acompanhar(codigo), 2000);
        } catch (error) {
            titulo.textContent = 'Pedido enviado'; status.textContent = `Codigo ${codigo}. Aguarde ser chamado. Vamos tentar atualizar novamente.`;
            setTimeout(() => acompanhar(codigo), 5000);
        }
    }

    form.addEventListener('submit', async event => {
        event.preventDefault(); if (!form.reportValidity() || enviar.disabled) return;
        const itens = quantidades.filter(input => Number(input.value) > 0).map(input => ({produto_id: Number(input.dataset.produto), quantidade: Number(input.value)}));
        if (!itens.length) { alert('Selecione ao menos um produto.'); return; }
        enviar.disabled = true; acompanhamento.hidden = false; titulo.textContent = 'Enviando pedido'; status.textContent = 'Aguarde...';
        try {
            const response = await fetch('/cliente/pedidos', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({itens, filial: document.getElementById('filial').value})});
            const result = await lerResposta(response); if (!response.ok) throw new Error(result.detail || 'Nao foi possivel enviar o pedido.');
            sessionStorage.setItem('pedido_cliente_pendente', result.codigo); acompanhar(result.codigo);
        } catch (error) { titulo.textContent = 'Nao foi possivel enviar'; status.textContent = error.message; enviar.disabled = false; }
    });
    const anterior = sessionStorage.getItem('pedido_cliente_pendente'); if (anterior) acompanhar(anterior);
})();
