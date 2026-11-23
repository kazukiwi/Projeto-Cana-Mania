(() => {
    const form = document.getElementById('pedido');
    const enviar = document.getElementById('enviar');
    const status = document.getElementById('status');
    const titulo = document.getElementById('titulo');
    const acompanhamento = document.getElementById('acompanhamento');
    const cancelar = document.getElementById('cancelar');
    const comprovante = document.getElementById('comprovante');
    const qr = document.getElementById('qr');
    const qrLink = document.getElementById('qr-link');
    const total = document.getElementById('total');
    const itensResumo = document.getElementById('pedido-itens');
    const quantidades = [...document.querySelectorAll('[data-produto]')];
    const moeda = value => (value / 100).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    const valor = () => quantidades.reduce((sum, input) => sum + Math.round(Number(input.dataset.preco) * 100) * Number(input.value || 0), 0);
    const esperar = ms => new Promise(resolve => setTimeout(resolve, ms));
    let operacaoId = null;
    let cancelando = false;
    function atualizarResumo() {
        total.textContent = moeda(valor());
        const selecionados = quantidades.filter(input => Number(input.value) > 0);
        if (!selecionados.length) {
            const linha = document.createElement('tr');
            const celula = document.createElement('td');
            celula.colSpan = 3; celula.className = 'cliente-pdv-vazio'; celula.textContent = 'Adicione produtos do cardápio.';
            linha.append(celula); itensResumo.replaceChildren(linha); return;
        }
        itensResumo.replaceChildren(...selecionados.map(input => {
            const quantidade = Number(input.value);
            const subtotal = Math.round(Number(input.dataset.preco) * 100) * quantidade;
            const linha = document.createElement('tr');
            const nome = document.createElement('td'); nome.textContent = input.dataset.nome;
            const qtd = document.createElement('td'); qtd.textContent = String(quantidade);
            const valorItem = document.createElement('td'); valorItem.textContent = moeda(subtotal);
            linha.append(nome, qtd, valorItem); return linha;
        }));
    }
    quantidades.forEach(input => input.addEventListener('input', atualizarResumo));
    atualizarResumo();

    async function acompanhar(id) {
        operacaoId = id;
        acompanhamento.hidden = false;
        enviar.disabled = true;
        while (operacaoId === id) {
            try {
                const response = await fetch(`/rfid/operacoes/${encodeURIComponent(id)}`, {cache: 'no-store'});
                const resultado = await response.json();
                if ([401, 403, 404].includes(response.status)) {
                    sessionStorage.removeItem('pedido_pendente');
                    operacaoId = null;
                    titulo.textContent = 'Não foi possível acompanhar o pedido';
                    status.textContent = 'Verifique sua sessão e consulte seus comprovantes antes de fazer outro pedido.';
                    cancelar.hidden = true;
                    enviar.disabled = false;
                    return;
                }
                if (!response.ok) throw new Error(resultado.detail || 'Falha ao consultar pedido.');
                if (resultado.status === 'na_fila') {
                    titulo.textContent = 'Você está na fila';
                    status.textContent = `Posição na fila: ${resultado.posicao || 'aguardando'}. Seu código é ${id.slice(0, 6).toUpperCase()}. Aguarde sua vez.`;
                    cancelar.hidden = false;
                } else if (['aguardando_tag', 'tag_recebida', 'processando'].includes(resultado.status)) {
                    titulo.textContent = 'Sua vez chegou';
                    status.textContent = `Confira o código ${id.slice(0, 6).toUpperCase()} no visor e aproxime seu cartão quando ele aparecer.`;
                    cancelar.hidden = resultado.status !== 'aguardando_tag';
                } else if (resultado.status === 'aguardando_qr') {
                    titulo.textContent = 'Confirme o Pix simulado';
                    status.textContent = 'Use o QR Code ou o link para confirmar a simulação.';
                    qrLink.href = `/confirmar-qr/${encodeURIComponent(id)}`;
                    qrLink.hidden = false;
                    cancelar.hidden = true;
                } else {
                    sessionStorage.removeItem('pedido_pendente');
                    operacaoId = null;
                    cancelar.hidden = true; qr.hidden = true; qrLink.hidden = true;
                    if (resultado.status === 'aprovado' && resultado.venda_id) {
                        window.somPagamento?.confirmar();
                        titulo.textContent = 'Compra realizada!';
                        status.textContent = 'Pagamento simulado confirmado. Mostre seu comprovante à equipe.';
                        comprovante.href = `/pdv/venda/${resultado.venda_id}`;
                        comprovante.hidden = false;
                        await esperar(450);
                        window.location.assign(comprovante.href);
                    } else {
                        titulo.textContent = 'Pedido não concluído';
                        if (resultado.status === 'negado_saldo_insuficiente') {
                            status.textContent = 'Saldo insuficiente. Seus produtos continuam selecionados; tente novamente ou escolha outra forma de pagamento.';
                        } else if (resultado.erro?.startsWith('Arduino recusou o valor')) {
                            status.textContent = 'A maquininha precisa ser atualizada. Avise a equipe; seus produtos continuam selecionados.';
                        } else {
                            status.textContent = 'O pagamento não foi concluído. Seus produtos continuam selecionados; tente novamente.';
                        }
                        enviar.disabled = false;
                    }
                    return;
                }
            } catch (error) {
                titulo.textContent = 'Reconectando';
                status.textContent = 'Aguardando conexão com o sistema para consultar seu pedido.';
            }
            await esperar(1000);
        }
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();
        window.somPagamento?.preparar();
        if (operacaoId || !form.reportValidity()) return;
        const carrinho = quantidades.filter(input => Number(input.value) > 0).map(input => ({produto_id: Number(input.dataset.produto), quantidade: Number(input.value)}));
        if (!carrinho.length) { alert('Selecione ao menos um produto.'); return; }
        enviar.disabled = true;
        acompanhamento.hidden = false;
        titulo.textContent = 'Preparando pedido'; status.textContent = 'Aguarde...'; comprovante.hidden = true;
        const forma = document.getElementById('forma').value;
        try {
            const response = await fetch('/rfid/operacoes', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({
                tipo: 'pagar', centavos: valor(), carrinho_json: JSON.stringify(carrinho),
                filial: document.getElementById('filial').value, forma_pagamento: forma,
                cortesia: 'false', confirmacao: forma === 'pix' ? 'qr' : 'cartao'
            })});
            const result = await response.json();
            if (!response.ok) throw new Error(result.detail || 'Não foi possível iniciar o pedido.');
            if (result.qr_code) { qr.src = result.qr_code; qr.hidden = false; qrLink.href = result.qr_url; qrLink.hidden = false; }
            sessionStorage.setItem('pedido_pendente', result.id);
            acompanhar(result.id);
        } catch (error) {
            titulo.textContent = 'Não foi possível iniciar'; status.textContent = error.message; enviar.disabled = false;
        }
    });
    cancelar.addEventListener('click', async () => {
        if (!operacaoId || cancelando) return;
        cancelando = true;
        try {
            const response = await fetch(`/rfid/operacoes/${encodeURIComponent(operacaoId)}/cancelar`, {method: 'POST'});
            if (!response.ok) throw new Error('Não foi possível cancelar.');
        } catch (error) { status.textContent = error.message; }
        finally { cancelando = false; }
    });
    const anterior = sessionStorage.getItem('pedido_pendente');
    if (anterior) acompanhar(anterior);
})();
