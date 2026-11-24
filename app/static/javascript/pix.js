document.addEventListener('DOMContentLoaded', () => {
    const painel = document.getElementById('pix-painel');
    if (!painel) return;
    const gerar = document.getElementById('pix-gerar');
    const mensagem = document.getElementById('pix-mensagem');
    const resultado = document.getElementById('pix-resultado');
    const codigo = document.getElementById('pix-codigo');
    const imagem = document.getElementById('pix-imagem');
    const campo = id => document.getElementById(id);
    let revisao = 0;
    const atualizar = () => {
        revisao++;
        const dividido = campo('dividir-pagamento').checked;
        painel.hidden = !(campo('forma_pagamento').value === 'pix' || (dividido && campo('forma_pagamento_2').value === 'pix'));
        resultado.hidden = true;
        codigo.value = '';
        imagem.removeAttribute('src');
        mensagem.textContent = '';
    };
    ['forma_pagamento', 'forma_pagamento_2', 'dividir-pagamento', 'valor_pagamento_1', 'valor_pagamento_2', 'filial-pdv'].forEach(id => {
        campo(id)?.addEventListener('input', atualizar);
        campo(id)?.addEventListener('change', atualizar);
    });
    document.addEventListener('pdv:carrinho-atualizado', atualizar);
    gerar.addEventListener('click', async () => {
        atualizar();
        if (painel.hidden) return;
        if (!carrinho.length) {
            mensagem.textContent = 'Adicione itens ao carrinho antes de gerar o Pix.';
            return;
        }
        const dados = new FormData();
        dados.set('carrinho_json', JSON.stringify(carrinho));
        dados.set('filial', campo('filial-pdv').value);
        dados.set('funcionario_comprador_id', campo('funcionario-comprador').value);
        dados.set('desconto_manual_percentual', campo('desconto-manual-aplicado')?.value || '0');
        if (campo('dividir-pagamento').checked) {
            const valor = campo(campo('forma_pagamento').value === 'pix' ? 'valor_pagamento_1' : 'valor_pagamento_2');
            if (![campo('forma_pagamento'), campo('forma_pagamento_2'), campo('valor_pagamento_1'), campo('valor_pagamento_2')].every(item => item.reportValidity())) return;
            dados.set('valor_pix', valor.value);
        }
        const versao = revisao;
        gerar.disabled = true;
        mensagem.textContent = 'Gerando QR Code...';
        try {
            const resposta = await fetch('/pdv/pix', {method: 'POST', body: dados, headers: {'Accept': 'application/json'}});
            const tipo = resposta.headers.get('content-type') || '';
            if (!tipo.includes('application/json')) throw new Error('Não foi possível gerar o Pix. Recarregue a página e confira sua sessão.');
            const pix = await resposta.json();
            if (versao !== revisao) return;
            if (!resposta.ok) throw new Error(typeof pix.detail === 'string' ? pix.detail : 'Confira os dados do pagamento Pix.');
            if (!pix.qr_code || !pix.copia_cola) throw new Error('O servidor retornou um Pix incompleto. Tente novamente.');
            imagem.src = pix.qr_code;
            codigo.value = pix.copia_cola;
            campo('pix-valor').textContent = Number(pix.valor).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
            resultado.hidden = false;
            mensagem.textContent = 'QR Code pronto. Confira o recebimento antes de finalizar.';
        } catch (erro) {
            if (versao === revisao) mensagem.textContent = erro.message || 'Falha ao gerar o Pix. Tente novamente.';
        } finally {
            gerar.disabled = false;
        }
    });
    campo('pix-copiar').addEventListener('click', async () => {
        if (!codigo.value) return;
        try {
            await navigator.clipboard.writeText(codigo.value);
            mensagem.textContent = 'Código Pix copiado.';
        } catch {
            codigo.focus();
            codigo.select();
            mensagem.textContent = 'Selecione e copie o código Pix com Ctrl+C.';
        }
    });
    atualizar();
});
