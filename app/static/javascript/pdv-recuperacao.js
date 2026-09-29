(() => {
    const form = document.getElementById('form-finalizar-real');
    if (!form) return;
    const chave = 'canamania-pdv-' + form.dataset.operador;
    const campoToken = document.getElementById('pedido_token');
    const status = document.getElementById('pdv-status');
    const botao = document.getElementById('btn-salvar-venda-banco');
    let pendente = false;
    let ocupado = false;
    const campos = ['filial-pdv', 'forma_pagamento', 'observacao'];
    function salvar() {
        try {
            const estado = {token: campoToken.value, carrinho, pendente};
            campos.forEach(id => estado[id] = document.getElementById(id).value);
            sessionStorage.setItem(chave, JSON.stringify(estado));
        } catch {
            status.textContent = 'O navegador não permitiu salvar o carrinho nesta aba.';
        }
    }
    function bloquear(valor) {
        window.pdvEnviando = valor;
        document.querySelectorAll('.pdv-layout-split input:not([type="hidden"]), .pdv-layout-split select, .pdv-layout-split button:not(#btn-salvar-venda-banco)').forEach(el => {
            if (valor) {
                el.dataset.desabilitadoAntes = String(el.disabled);
                el.disabled = true;
            } else if (el.dataset.desabilitadoAntes !== undefined) {
                el.disabled = el.dataset.desabilitadoAntes === 'true';
                delete el.dataset.desabilitadoAntes;
            }
        });
    }
    window.enviarVenda = async evento => {
        evento.preventDefault();
        if (ocupado || !carrinho.length) return;
        if (!pendente && !form.reportValidity()) return;
        ocupado = true;
        if (!pendente) bloquear(true);
        pendente = true;
        salvar();
        botao.disabled = true;
        botao.textContent = 'Registrando venda…';
        status.textContent = 'Aguarde a confirmação da venda.';
        const dados = new FormData();
        dados.set('carrinho_json', JSON.stringify(carrinho));
        dados.set('pedido_token', campoToken.value);
        dados.set('filial', document.getElementById('filial-pdv').value);
        dados.set('forma_pagamento', document.getElementById('forma_pagamento').value);
        dados.set('observacao', document.getElementById('observacao').value);
        const abortar = new AbortController();
        const limite = setTimeout(() => abortar.abort(), 20000);
        try {
            const resposta = await fetch('/pdv/finalizar', {method:'POST', body:dados, headers:{Accept:'application/json'}, signal:abortar.signal});
            const tipo = resposta.headers.get('content-type') || '';
            if (!tipo.includes('application/json')) throw new Error('Não foi possível confirmar o resultado. Tente novamente com este mesmo pedido.');
            const resultado = await resposta.json();
            if (!resposta.ok) {
                if (resposta.status >= 400 && resposta.status < 500 && resposta.status !== 409) {
                    pendente = false;
                    bloquear(false);
                    salvar();
                }
                throw new Error(resultado.detail || 'Não foi possível confirmar o resultado. Tente novamente.');
            }
            if (!Number.isInteger(resultado.venda_id)) throw new Error('Resposta inesperada. Tente novamente com este mesmo pedido.');
            try { sessionStorage.removeItem(chave); } catch {}
            window.location.assign('/pdv/venda/' + resultado.venda_id + '?sucesso=ok');
        } catch (erro) {
            status.textContent = erro.name === 'AbortError' || erro instanceof TypeError
                ? 'A conexão falhou. Clique em Tentar novamente: o mesmo pedido será verificado para evitar duplicidade.'
                : erro.message;
            botao.disabled = false;
            botao.textContent = pendente ? 'Tentar novamente' : 'Finalizar e emitir cupom';
        } finally {
            clearTimeout(limite);
            ocupado = false;
        }
    };
    document.addEventListener('DOMContentLoaded', async () => {
        try {
            const estado = JSON.parse(sessionStorage.getItem(chave) || 'null');
            if (estado && Array.isArray(estado.carrinho) && typeof estado.token === 'string') {
                campoToken.value = estado.token;
                campos.forEach(id => { if (typeof estado[id] === 'string') document.getElementById(id).value = estado[id]; });
                pendente = estado.pendente === true;
                carrinho = estado.carrinho.filter(item => Number.isInteger(item.produto_id) && Number.isInteger(item.quantidade) && item.quantidade > 0);
                if (!pendente) {
                    const opcoes = [...document.getElementById('select-prod').options];
                    carrinho = carrinho.flatMap(item => {
                        const produto = opcoes.find(o => Number(o.value) === item.produto_id);
                        return produto ? [{...item, nome:produto.dataset.nome, preco:Number(produto.dataset.preco)}] : [];
                    });
                }
                atualizarTabelaCarrinho();
                document.getElementById('filial-pdv').dispatchEvent(new Event('change'));
                document.getElementById('forma_pagamento').dispatchEvent(new Event('change'));
                status.textContent = pendente ? 'Há um envio sem confirmação. Verificando o pedido…' : 'Carrinho recuperado. Os preços foram atualizados; confira os itens antes de finalizar.';
                if (pendente) {
                    bloquear(true);
                    botao.textContent = 'Tentar novamente';
                    try {
                        const resposta = await fetch('/pdv/pedido/' + encodeURIComponent(campoToken.value), {headers:{Accept:'application/json'}});
                        if (resposta.ok) {
                            const dados = await resposta.json();
                            if (Number.isInteger(dados.venda_id)) {
                                sessionStorage.removeItem(chave);
                                window.location.assign('/pdv/venda/' + dados.venda_id);
                                return;
                            }
                        }
                        status.textContent = 'Envio anterior sem confirmação. Clique em Tentar novamente para verificar e concluir o mesmo pedido.';
                    } catch { status.textContent = 'Sem conexão para verificar o pedido. Tente novamente quando a conexão voltar.'; }
                }
            }
        } catch {
            status.textContent = 'Não foi possível recuperar o carrinho salvo.';
        }
        document.addEventListener('pdv:carrinho-alterado', salvar);
        campos.forEach(id => document.getElementById(id).addEventListener('change', salvar));
        document.getElementById('observacao').addEventListener('input', salvar);
        document.addEventListener('keydown', evento => {
            if (evento.altKey || evento.ctrlKey || evento.metaKey || window.pdvEnviando) return;
            const acoes = {
                F2: () => document.getElementById('busca-frozen').focus(),
                F4: () => document.getElementById('abrir-catalogo-pdv').click(),
                F8: () => document.getElementById('forma_pagamento').focus(),
                F9: () => form.requestSubmit(),
            };
            if (acoes[evento.key]) { evento.preventDefault(); acoes[evento.key](); }
        });
    });
})();
