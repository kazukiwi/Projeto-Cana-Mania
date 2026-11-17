(() => {
    const iniciar = document.getElementById('btn-rfid-demo');
    const carregar = document.getElementById('btn-rfid-carregar');
    const cancelar = document.getElementById('btn-rfid-cancelar');
    const status = document.getElementById('rfid-demo-status');
    const total = document.getElementById('pdv-total-geral');
    if (!iniciar || !cancelar || !status || !total) return;

    let idTransacao = null;
    let cancelando = false;
    const aguardar = ms => new Promise(resolve => window.setTimeout(resolve, ms));
    const erroDaResposta = async resposta => {
        const dados = await resposta.json().catch(() => ({}));
        return dados.detail || dados.erro || `Falha na comunicacao (${resposta.status}).`;
    };
    const formatarDinheiro = centavos => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format((centavos || 0) / 100);
    const formatarStatus = atual => {
        const uid = atual.cartao_uid ? ` UID ${atual.cartao_uid}.` : '';
        if (atual.status === 'aprovado') return `Saldo debitado (${formatarDinheiro(atual.saldo_centavos)} restante). Finalizando a venda...${uid}`;
        if (atual.status === 'saldo_carregado') return `Saldo carregado: ${formatarDinheiro(atual.saldo_centavos)}.${uid}`;
        if (atual.status === 'saldo_insuficiente') return `Saldo insuficiente. Disponivel: ${formatarDinheiro(atual.saldo_centavos)}.${uid}`;
        if (atual.status === 'erro_cartao') return `Nao foi possivel usar o cartao: ${atual.erro_cartao || 'tipo ou dados nao compativeis'}.${uid}`;
        return ({
            aguardando_tag: 'Aproxime o cartao do leitor.',
            expirado: 'Tempo esgotado. Tente novamente.',
            cancelado: 'Leitura cancelada.',
            erro_comunicacao: 'Comunicacao com o Arduino interrompida.'
        }[atual.status] || `Estado: ${atual.status}.`);
    };
    const centavosDoCampo = campo => {
        const valor = Number(campo.textContent.replace(/[^\d,]/g, '').replace(/\./g, '').replace(',', '.'));
        return Math.round(valor * 100);
    };

    async function iniciarOperacao(operacao, centavos) {
        if (!Number.isSafeInteger(centavos) || centavos < 1 || centavos > 999999) {
            status.textContent = 'Informe um valor entre R$ 0,01 e R$ 9.999,99.';
            return;
        }
        const dividir = document.getElementById('dividir-pagamento');
        if (operacao === 'pagar' && dividir?.checked) {
            status.textContent = 'Desative o pagamento dividido para usar o cartao pre-pago.';
            return;
        }
        iniciar.disabled = true;
        if (carregar) carregar.disabled = true;
        status.textContent = operacao === 'carregar' ? 'Aproxime o cartao para carregar saldo...' : 'Aproxime o cartao para pagar...';
        try {
            const resposta = await fetch('/pdv/rfid/iniciar', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({centavos, operacao})
            });
            if (!resposta.ok) throw new Error(await erroDaResposta(resposta));
            const transacao = await resposta.json();
            idTransacao = transacao.id;
            cancelar.hidden = false;
            let resultado = null;
            while (idTransacao) {
                await aguardar(500);
                const consulta = await fetch(`/pdv/rfid/status/${encodeURIComponent(idTransacao)}`);
                if (!consulta.ok) throw new Error(await erroDaResposta(consulta));
                resultado = await consulta.json();
                status.textContent = formatarStatus(resultado);
                if (resultado.status !== 'aguardando_tag') break;
            }
            if (operacao === 'pagar' && resultado?.status === 'aprovado') {
                const formulario = document.getElementById('form-finalizar-real');
                document.getElementById('forma_pagamento').value = 'rfid_pre_pago';
                document.getElementById('rfid-transacao-id').value = transacao.id;
                const forma2 = document.getElementById('forma_pagamento_2');
                const valor1 = document.getElementById('valor_pagamento_1');
                const valor2 = document.getElementById('valor_pagamento_2');
                if (forma2) forma2.value = '';
                if (valor1) valor1.value = '';
                if (valor2) valor2.value = '';
                formulario.dataset.enviando = 'true';
                document.getElementById('btn-salvar-venda-banco').disabled = true;
                window.setTimeout(() => HTMLFormElement.prototype.submit.call(formulario), 500);
            }
        } catch (erro) {
            status.textContent = erro.message || 'Nao foi possivel completar a operacao do cartao.';
        } finally {
            idTransacao = null;
            cancelando = false;
            cancelar.hidden = true;
            cancelar.disabled = false;
            iniciar.disabled = false;
            if (carregar) carregar.disabled = false;
        }
    }

    iniciar.addEventListener('click', () => iniciarOperacao('pagar', centavosDoCampo(total)));
    carregar?.addEventListener('click', () => {
        const campo = document.getElementById('rfid-valor-carga');
        const valor = Number((campo?.value || '').replace(',', '.'));
        iniciarOperacao('carregar', Math.round(valor * 100));
    });
    cancelar.addEventListener('click', async () => {
        if (!idTransacao || cancelando) return;
        cancelando = true;
        cancelar.disabled = true;
        try {
            const resposta = await fetch(`/pdv/rfid/cancelar/${encodeURIComponent(idTransacao)}`, {method: 'POST'});
            if (!resposta.ok) throw new Error(await erroDaResposta(resposta));
            status.textContent = 'Leitura cancelada.';
            idTransacao = null;
        } catch (erro) {
            status.textContent = erro.message || 'Nao foi possivel cancelar a leitura.';
            cancelando = false;
            cancelar.disabled = false;
        }
    });
})();