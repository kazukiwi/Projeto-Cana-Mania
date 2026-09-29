document.addEventListener('DOMContentLoaded', () => {
    const painel = document.getElementById('pix-painel');
    if (!painel) return;
    const pagamento = document.getElementById('forma_pagamento');
    const gerar = document.getElementById('pix-gerar');
    const resultado = document.getElementById('pix-resultado');
    const mensagem = document.getElementById('pix-mensagem');
    const codigo = document.getElementById('pix-codigo');
    const imagem = document.getElementById('pix-imagem');
    let versao = 0;
    let requisicao;

    function invalidar() {
        versao++;
        requisicao?.abort();
        painel.hidden = pagamento.value !== 'pix';
        resultado.hidden = true;
        codigo.value = '';
        imagem.removeAttribute('src');
        gerar.disabled = !carrinho.length;
        mensagem.textContent = carrinho.length ? '' : 'Adicione itens ao carrinho para gerar o Pix.';
    }
    pagamento.addEventListener('change', invalidar);
    document.addEventListener('pdv:carrinho-alterado', invalidar);
    document.getElementById('filial-pdv').addEventListener('change', invalidar);
    gerar.addEventListener('click', async () => {
        invalidar();
        if (!carrinho.length) return;
        const atual = versao;
        requisicao = new AbortController();
        gerar.disabled = true;
        mensagem.textContent = 'Gerando QR Code...';
        const dados = new FormData();
        dados.set('carrinho_json', JSON.stringify(carrinho));
        dados.set('filial', document.getElementById('filial-pdv').value);
        try {
            const resposta = await fetch('/pdv/pix', {
                method: 'POST', body: dados, signal: requisicao.signal,
                credentials: 'same-origin', headers: {'Accept': 'application/json'},
            });
            if (atual !== versao) return;
            if (resposta.status === 401 || resposta.redirected) {
                throw new Error('Sua sessão expirou. Entre novamente e tente gerar o Pix.');
            }
            const tipo = resposta.headers.get('content-type') || '';
            if (!tipo.includes('application/json')) {
                throw new Error(resposta.status === 404
                    ? 'A rota Pix não está disponível. Reinicie o servidor e recarregue a página.'
                    : 'O servidor retornou uma resposta inválida. Recarregue a página e tente novamente.');
            }
            let conteudo;
            try {
                conteudo = await resposta.json();
            } catch {
                throw new Error('O servidor retornou uma resposta inválida. Tente novamente.');
            }
            if (atual !== versao) return;
            if (!resposta.ok) throw new Error(typeof conteudo?.detail === 'string' ? conteudo.detail : 'Não foi possível gerar o Pix.');
            if (!conteudo || typeof conteudo.copia_cola !== 'string' || typeof conteudo.qr_code !== 'string' || !Number.isFinite(Number(conteudo.valor))) {
                throw new Error('A resposta não contém um código Pix válido. Tente novamente.');
            }
            codigo.value = conteudo.copia_cola;
            imagem.src = conteudo.qr_code;
            document.getElementById('pix-valor').textContent = Number(conteudo.valor).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
            resultado.hidden = false;
            mensagem.textContent = '';
        } catch (erro) {
            if (atual === versao && erro.name !== 'AbortError') {
                mensagem.textContent = erro instanceof TypeError ? 'Falha de conexão. Tente novamente.' : erro.message;
            }
        } finally {
            if (atual === versao) gerar.disabled = false;
        }
    });
    document.getElementById('pix-copiar').addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(codigo.value);
            mensagem.textContent = 'Código Pix copiado.';
        } catch {
            codigo.focus();
            codigo.select();
            mensagem.textContent = 'Selecione e copie o código com Ctrl+C ou pelo menu do celular.';
        }
    });
    invalidar();
});
