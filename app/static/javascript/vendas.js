let carrinho = [];

document.addEventListener('DOMContentLoaded', () => {
    configurarPagamentoDividido();
    const produto = document.getElementById('select-prod');
    const funcionarioComprador = document.getElementById('funcionario-comprador');
    const descontoManualAplicado = document.getElementById('desconto-manual-aplicado');
    const cortesiaAplicada = document.getElementById('cortesia-aplicada');
    const painelDescontoManual = document.getElementById('painel-desconto-manual');
    const campoDescontoManual = document.getElementById('desconto-manual-percentual');
    const formaPagamento = document.getElementById('forma_pagamento');
    const dividirPagamento = document.getElementById('dividir-pagamento');
    const tamanho = document.getElementById('pdv-tamanho');
    const cor = document.getElementById('pdv-cor');
    const grupoTamanho = document.getElementById('grupo-tamanho');
    const grupoCor = document.getElementById('grupo-cor');
    const quantidade = document.getElementById('pdv-qtd');
    const estoque = document.getElementById('pdv-estoque');
    const dados = document.getElementById('variacoes-produtos');
    const variacoes = JSON.parse(dados ? dados.textContent : '{}');
    const dadosFiliais = document.getElementById('estoque-filiais');
    const estoquesFiliais = JSON.parse(dadosFiliais ? dadosFiliais.textContent : '{}');
    const filial = document.getElementById('filial-pdv');
    const buscaFrozen = document.getElementById('busca-frozen');
    const resultadoBusca = document.getElementById('resultado-busca-frozen');
    const modalCatalogo = document.getElementById('catalogo-pdv-modal');
    const gradeCatalogo = document.getElementById('grade-catalogo-pdv');
    const buscaCatalogo = document.getElementById('busca-catalogo-pdv');

    const atualizarEstadoDesconto = () => {
        const cortesia = cortesiaAplicada?.value === 'true';
        const descontoManual = descontoManualAplicado?.value !== '';
        const botaoCortesia = document.getElementById('btn-cortesia');
        botaoCortesia?.classList.toggle('ativo', cortesia);
        botaoCortesia?.setAttribute('aria-pressed', String(cortesia));
        const status = document.getElementById('pdv-desconto-status');
        if (status) status.textContent = cortesia ? 'Cortesia aplicada: total zerado.' : (descontoManual ? `Desconto manual de ${descontoManualAplicado.value}% aplicado.` : '');
        atualizarTabelaCarrinho();
    };
    const definirCortesia = ativa => {
        cortesiaAplicada.value = ativa ? 'true' : 'false';
        if (ativa) {
            descontoManualAplicado.value = '';
            painelDescontoManual.hidden = true;
            formaPagamento.value = 'cortesia';
            dividirPagamento.checked = false;
            dividirPagamento.disabled = true;
        } else {
            if (formaPagamento.value === 'cortesia') formaPagamento.value = '';
            dividirPagamento.disabled = false;
        }
        formaPagamento.dispatchEvent(new Event('change'));
        dividirPagamento.dispatchEvent(new Event('change'));
        atualizarEstadoDesconto();
    };
    document.getElementById('btn-desconto-manual')?.addEventListener('click', () => {
        if (cortesiaAplicada.value === 'true') definirCortesia(false);
        painelDescontoManual.hidden = false;
        campoDescontoManual.value = descontoManualAplicado.value;
        campoDescontoManual.focus();
    });
    document.getElementById('aplicar-desconto-manual')?.addEventListener('click', () => {
        const valor = campoDescontoManual.value;
        const percentual = Number(valor);
        campoDescontoManual.setCustomValidity('');
        if (valor === '' || !Number.isFinite(percentual) || percentual < 0 || percentual > 100) {
            campoDescontoManual.setCustomValidity('Informe um percentual entre 0 e 100.');
            campoDescontoManual.reportValidity();
            return;
        }
        descontoManualAplicado.value = percentual.toFixed(2);
        cortesiaAplicada.value = 'false';
        if (formaPagamento.value === 'cortesia') formaPagamento.value = '';
        dividirPagamento.disabled = false;
        painelDescontoManual.hidden = true;
        formaPagamento.dispatchEvent(new Event('change'));
        atualizarEstadoDesconto();
    });
    document.getElementById('cancelar-desconto-manual')?.addEventListener('click', () => {
        painelDescontoManual.hidden = true;
        campoDescontoManual.setCustomValidity('');
    });
    document.getElementById('btn-cortesia')?.addEventListener('click', () => {
        definirCortesia(cortesiaAplicada.value !== 'true');
    });
    formaPagamento?.addEventListener('change', () => {
        if (formaPagamento.value === 'cortesia' && cortesiaAplicada.value !== 'true') definirCortesia(true);
        else if (formaPagamento.value !== 'cortesia' && cortesiaAplicada.value === 'true') definirCortesia(false);
    });

    const selecionarProduto = id => {
        produto.value = String(id);
        buscaFrozen.value = produto.options[produto.selectedIndex].textContent.trim();
        resultadoBusca.innerHTML = '';
        buscaFrozen.setAttribute('aria-expanded', 'false');
        produto.dispatchEvent(new Event('change'));
    };
    const renderizarCatalogo = termo => {
        if (!gradeCatalogo) return;
        const filtro = (termo || '').trim().toLocaleLowerCase('pt-BR');
        gradeCatalogo.innerHTML = '';
        [...produto.options].filter(opcao => opcao.value && !opcao.hidden && opcao.textContent.toLocaleLowerCase('pt-BR').includes(filtro)).forEach(opcao => {
            const card = document.createElement('button');
            card.type = 'button'; card.dataset.produtoId = opcao.value;
            card.style.cssText = 'border:1px solid #ddd;border-radius:10px;background:#fff;padding:10px;text-align:left;cursor:pointer;display:grid;gap:8px;';
            const imagem = document.createElement('img');
            imagem.src = opcao.dataset.imagem || '/static/img/produto_padrao.png'; imagem.alt = ''; imagem.style.cssText = 'width:100%;height:105px;object-fit:cover;border-radius:7px;';
            const nome = document.createElement('strong'); nome.textContent = opcao.dataset.nome;
            const detalhe = document.createElement('small'); detalhe.textContent = opcao.dataset.semEstoque === 'true' ? 'Venda sem limite' : `${saldoDaFilial(opcao.value)} un. nesta loja`;
            card.append(imagem, nome, detalhe); gradeCatalogo.appendChild(card);
        });
        if (!gradeCatalogo.children.length) gradeCatalogo.textContent = 'Nenhum produto disponível nesta loja.';
    };

    const opcoes = () => variacoes[produto.value] || [];
    const formatarPreco = preco => `R$ ${Number(preco || 0).toFixed(2).replace('.', ',')}`;
    const saldoDaFilial = id => Number(estoquesFiliais[String(id)]?.[filial?.value] || 0);
    const aplicarFilial = () => {
        [...produto.options].forEach(opcao => {
            if (!opcao.value) return;
            if (opcao.dataset.semEstoque === 'true') {
                opcao.hidden = false;
                opcao.disabled = false;
                return;
            }
            const saldo = saldoDaFilial(opcao.value);
            opcao.hidden = saldo <= 0;
            opcao.disabled = saldo <= 0;
        });
        if (produto.value && saldoDaFilial(produto.value) <= 0) {
            produto.value = '';
            estoque.value = '--';
        }
    };
    const atualizarSaldo = () => {
        const variacao = opcoes().find(item => String(item.tamanho_id) === tamanho.value && item.cor === cor.value);
        const saldo = variacao ? variacao.estoque_atual : 0;
        estoque.value = `${saldo} un`;
        quantidade.max = saldo;
        document.getElementById('pdv-preco').value = formatarPreco(variacao?.preco);
    };
    const preencherCores = () => {
        cor.innerHTML = '<option value="" disabled selected>Selecione a cor...</option>';
        [...new Set(opcoes().filter(item => String(item.tamanho_id) === tamanho.value && item.estoque_atual > 0).map(item => item.cor))]
            .forEach(nome => cor.add(new Option(nome, nome)));
        cor.disabled = cor.options.length === 1;
        atualizarSaldo();
    };

    produto?.addEventListener('change', () => {
        const selecionado = produto.options[produto.selectedIndex];
        const temVariacoes = selecionado.dataset.possuiVariacoes === 'true';
        document.getElementById('pdv-preco').value = formatarPreco(selecionado.dataset.preco);
        quantidade.value = 1;
        grupoTamanho.style.display = temVariacoes ? 'block' : 'none';
        grupoCor.style.display = temVariacoes ? 'block' : 'none';
        tamanho.required = temVariacoes;
        cor.required = temVariacoes;
        tamanho.value = '';
        cor.innerHTML = '<option value="" disabled selected>Selecione a cor...</option>';
        if (temVariacoes) {
            [...tamanho.options].forEach(opcao => {
                if (opcao.value) opcao.disabled = !opcoes().some(item => String(item.tamanho_id) === opcao.value && item.estoque_atual > 0);
            });
        } else {
            if (selecionado.dataset.semEstoque === 'true') {
                estoque.value = 'Sem limite';
                quantidade.removeAttribute('max');
            } else {
                const saldo = saldoDaFilial(produto.value);
                estoque.value = `${saldo} un`;
                quantidade.max = saldo;
            }
        }
    });
    tamanho?.addEventListener('change', preencherCores);
    cor?.addEventListener('change', atualizarSaldo);

    const adicionarAoCarrinho = evento => {
        evento?.preventDefault();
        if (!document.getElementById('form-add-item-pdv').reportValidity()) return;
        if (!produto.value) return;
        const selecionado = produto.options[produto.selectedIndex];
        const temVariacoes = selecionado.dataset.possuiVariacoes === 'true';
        if (temVariacoes && (!tamanho.value || !cor.value)) return;
        const qtd = Number(quantidade.value);
        const saldo = temVariacoes
            ? opcoes().find(item => String(item.tamanho_id) === tamanho.value && item.cor === cor.value)?.estoque_atual
            : (selecionado.dataset.semEstoque === 'true' ? Number.POSITIVE_INFINITY : saldoDaFilial(produto.value));
        if (!qtd || qtd > saldo) return alert('Quantidade excede o estoque disponível.');
        const tamanhoId = temVariacoes ? tamanho.value : null;
        const nomeCor = temVariacoes ? cor.value : null;
        const existente = carrinho.find(item => item.produto_id === Number(produto.value) && item.tamanho_id === tamanhoId && item.cor === nomeCor);
        if (existente) {
            if (existente.quantidade + qtd > saldo) {
                alert('Quantidade excede o estoque disponível.');
                return;
            }
            existente.quantidade += qtd;
        }
        else carrinho.push({
            produto_id: Number(produto.value), nome: selecionado.dataset.nome,
            preco: temVariacoes
                ? Number(opcoes().find(item => String(item.tamanho_id) === tamanhoId && item.cor === nomeCor).preco)
                : Number(selecionado.dataset.preco),
            quantidade: qtd, tamanho_id: tamanhoId, tamanho: temVariacoes ? tamanho.options[tamanho.selectedIndex].text : null, cor: nomeCor
        });
        atualizarTabelaCarrinho();
        produto.value = '';
        grupoTamanho.style.display = 'none'; grupoCor.style.display = 'none';
        estoque.value = '--'; document.getElementById('pdv-preco').value = 'R$ 0,00'; quantidade.value = 1;
    };
    document.getElementById('btn-adicionar-carrinho')?.addEventListener('click', adicionarAoCarrinho);
    document.getElementById('form-add-item-pdv')?.addEventListener('submit', adicionarAoCarrinho);

    document.getElementById('form-finalizar-real')?.addEventListener('submit', async evento => {
        if (!carrinho.length) {
            evento.preventDefault();
            return;
        }

        evento.preventDefault();
        const formulario = evento.currentTarget;
        const botao = document.getElementById('btn-salvar-venda-banco');
        if (formulario.dataset.enviando === 'true') return;

        atualizarPagamentoDividido();
        if (!formulario.reportValidity()) return;
        const descontoConfirmacao = document.getElementById('pdv-linha-desconto').style.display !== 'none'
            ? `\n${document.getElementById('pdv-desconto-label').textContent} ${document.getElementById('pdv-desconto').textContent}` : '';
        const pagamentoConfirmacao = dividirPagamento.checked
            ? `${document.getElementById('forma_pagamento').selectedOptions[0]?.text}: R$ ${document.getElementById('valor_pagamento_1').value} + ${document.getElementById('forma_pagamento_2').selectedOptions[0]?.text}: R$ ${document.getElementById('valor_pagamento_2').value}`
            : document.getElementById('forma_pagamento').selectedOptions[0]?.text;
        const confirmado = await confirmarVendaPDV({
            loja: filial.value,
            cliente: document.getElementById('select-cliente').selectedOptions[0]?.text.trim(),
            itens: carrinho.map(item => `${item.quantidade} x ${item.nome}${item.tamanho ? ` (${item.tamanho}, ${item.cor})` : ''}`),
            desconto: descontoConfirmacao,
            total: document.getElementById('pdv-total-geral').textContent,
            pagamento: pagamentoConfirmacao,
        });
        if (!confirmado) return;

        formulario.dataset.enviando = 'true';
        botao.disabled = true;
        botao.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Realizando venda...';

        const card = document.createElement('div');
        card.className = 'pdv-processando-venda';
        card.innerHTML = '<div class="pdv-processando-venda-card" role="status" aria-live="polite"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i><h2>Realizando venda...</h2><p>Registrando os itens e atualizando o estoque.</p></div>';
        document.body.appendChild(card);
        window.setTimeout(() => formulario.submit(), 150);
    });
    document.getElementById('select-cliente')?.addEventListener('change', atualizarTabelaCarrinho);
    document.getElementById('corpo-carrinho-pdv')?.addEventListener('click', evento => {
        const botao = evento.target.closest('[data-acao-carrinho]'); if (!botao) return;
        if (botao.dataset.acaoCarrinho === 'quantidade') window.alterarQuantidadeCarrinho(botao.dataset.chave, Number(botao.dataset.delta));
        if (botao.dataset.acaoCarrinho === 'remover') window.removerDoCarrinho(Number(botao.dataset.indice));
    });
    document.getElementById('corpo-carrinho-pdv')?.addEventListener('change', evento => {
        if (evento.target.matches('[data-quantidade-carrinho]')) window.definirQuantidadeCarrinho(evento.target.dataset.chave, evento.target.value);
    });
    funcionarioComprador?.addEventListener('change', atualizarTabelaCarrinho);
    filial?.addEventListener('change', aplicarFilial);
    buscaFrozen?.addEventListener('input', () => {
        const termo = buscaFrozen.value.trim().toLocaleLowerCase('pt-BR');
        [...produto.options].forEach(opcao => {
            if (!opcao.value) return;
            const corresponde = !termo || opcao.textContent.toLocaleLowerCase('pt-BR').includes(termo);
            opcao.hidden = !corresponde || (opcao.dataset.semEstoque !== 'true' && saldoDaFilial(opcao.value) <= 0);
        });
        const encontrados = [...produto.options].filter(opcao => opcao.value && !opcao.hidden).slice(0, 6);
        if (resultadoBusca) {
            resultadoBusca.innerHTML = termo ? encontrados.map(opcao => `<button type="button" role="option" aria-selected="false" data-produto-id="${opcao.value}"><i class="fa-solid fa-cube" aria-hidden="true"></i>${escapeHtml(opcao.textContent.trim())} <small>${opcao.dataset.semEstoque === 'true' ? 'Sem limite de estoque' : `${saldoDaFilial(opcao.value)} un. nesta loja`}</small></button>`).join('') || '<p role="status">Nenhum produto disponível nesta loja.</p>' : '';
            buscaFrozen.setAttribute('aria-expanded', String(Boolean(termo)));
        }
    });
    resultadoBusca?.addEventListener('click', evento => {
        const botao = evento.target.closest('[data-produto-id]');
        if (!botao) return;
        selecionarProduto(botao.dataset.produtoId);
    });
    buscaFrozen?.addEventListener('keydown', evento => {
        const opcoesBusca = [...(resultadoBusca?.querySelectorAll('[role="option"]') || [])];
        if (evento.key === 'ArrowDown' && opcoesBusca.length) { evento.preventDefault(); opcoesBusca[0].focus(); }
    });
    resultadoBusca?.addEventListener('keydown', evento => {
        const botoes = [...resultadoBusca.querySelectorAll('[role="option"]')]; const indice = botoes.indexOf(evento.target);
        if (evento.key === 'ArrowDown' || evento.key === 'ArrowUp') { evento.preventDefault(); botoes[(indice + (evento.key === 'ArrowDown' ? 1 : botoes.length - 1)) % botoes.length]?.focus(); }
        if (evento.key === 'Escape') { buscaFrozen.focus(); resultadoBusca.replaceChildren(); buscaFrozen.setAttribute('aria-expanded', 'false'); }
    });
    const botaoAbrirCatalogo = document.getElementById('abrir-catalogo-pdv');
    const fecharCatalogo = () => { modalCatalogo.hidden = true; botaoAbrirCatalogo?.focus(); };
    document.addEventListener('keydown', evento => { if (evento.key === 'Escape' && modalCatalogo && !modalCatalogo.hidden) fecharCatalogo(); });
    botaoAbrirCatalogo?.addEventListener('click', () => {
        aplicarFilial(); renderizarCatalogo(''); modalCatalogo.hidden = false; buscaCatalogo?.focus();
    });
    document.getElementById('fechar-catalogo-pdv')?.addEventListener('click', fecharCatalogo);
    buscaCatalogo?.addEventListener('input', () => renderizarCatalogo(buscaCatalogo.value));
    gradeCatalogo?.addEventListener('click', evento => {
        const card = evento.target.closest('[data-produto-id]');
        if (!card) return;
        selecionarProduto(card.dataset.produtoId); fecharCatalogo();
    });
    modalCatalogo?.addEventListener('click', evento => { if (evento.target === modalCatalogo) fecharCatalogo(); });
    aplicarFilial();
});

function atualizarTabelaCarrinho() {
    const corpo = document.getElementById('corpo-carrinho-pdv');
    if (!corpo) return;
    let total = 0;
    corpo.innerHTML = carrinho.map((item, indice) => {
        const subtotal = item.preco * item.quantidade;
        total += subtotal;
        const variacao = item.tamanho ? ` (Tam: ${item.tamanho} | Cor: ${item.cor})` : '';
        const chave = `${item.produto_id}|${item.tamanho_id || ''}|${item.cor || ''}`;
        return `<tr><td><strong>${escapeHtml(item.nome)}${escapeHtml(variacao)}</strong></td><td><div class="pdv-qtd-carrinho"><button type="button" data-acao-carrinho="quantidade" data-chave="${escapeHtml(chave)}" data-delta="-1" aria-label="Diminuir ${escapeHtml(item.nome)}">−</button><input type="number" min="1" value="${item.quantidade}" data-quantidade-carrinho data-chave="${escapeHtml(chave)}" aria-label="Quantidade de ${escapeHtml(item.nome)}"><button type="button" data-acao-carrinho="quantidade" data-chave="${escapeHtml(chave)}" data-delta="1" aria-label="Aumentar ${escapeHtml(item.nome)}">+</button></div></td><td>R$ ${subtotal.toFixed(2).replace('.', ',')}</td><td><button type="button" data-acao-carrinho="remover" data-indice="${indice}" aria-label="Remover ${escapeHtml(item.nome)}"><i class="fa-solid fa-trash" aria-hidden="true"></i><span class="pdv-remover-texto"> Remover</span></button></td></tr>`;
    }).join('');
    const cortesia = document.getElementById('cortesia-aplicada')?.value === 'true';
    const manual = document.getElementById('desconto-manual-aplicado')?.value || '';
    const compraFuncionario = Boolean(document.getElementById('funcionario-comprador')?.value);
    const percentual = cortesia ? 100 : Math.min(100, (compraFuncionario ? 15 : 0) + Number(manual || 0));
    const descontoValor = Math.round(total * percentual) / 100;
    const totalFinal = Math.round((total - descontoValor) * 100) / 100;
    const linhaDesconto = document.getElementById('pdv-linha-desconto');
    const rotuloDesconto = document.getElementById('pdv-desconto-label');
    if (rotuloDesconto) rotuloDesconto.textContent = cortesia ? 'Cortesia (100%):' : (manual !== '' ? `Desconto manual (${manual}%)${compraFuncionario ? ' + funcionário (15%)' : ''}:` : (compraFuncionario ? 'Desconto funcionário (15%):' : 'Desconto:'));
    document.getElementById('pdv-total-bruto').textContent = `R$ ${total.toFixed(2).replace('.', ',')}`;
    document.getElementById('pdv-desconto').textContent = `- R$ ${descontoValor.toFixed(2).replace('.', ',')}`;
    if (linhaDesconto) linhaDesconto.style.display = percentual > 0 && total > 0 ? 'flex' : 'none';
    document.getElementById('pdv-total-geral').textContent = `R$ ${totalFinal.toFixed(2).replace('.', ',')}`;
    document.getElementById('carrinho_json_input').value = JSON.stringify(carrinho);
    atualizarPagamentoDividido('valor_pagamento_1');
    document.getElementById('btn-salvar-venda-banco').disabled = !carrinho.length;
    document.dispatchEvent(new Event('pdv:carrinho-atualizado'));
}

window.removerDoCarrinho = indice => { carrinho.splice(indice, 1); atualizarTabelaCarrinho(); };
function confirmarVendaPDV(dados) {
    const modal = document.getElementById('pdv-confirmacao-modal');
    const botaoConfirmar = document.getElementById('pdv-confirmacao-confirmar');
    const botaoCancelar = document.getElementById('pdv-confirmacao-cancelar');
    document.getElementById('pdv-confirmacao-loja').textContent = `Loja: ${dados.loja}`;
    document.getElementById('pdv-confirmacao-cliente').textContent = `Cliente: ${dados.cliente}`;
    document.getElementById('pdv-confirmacao-itens').replaceChildren(...dados.itens.map(item => { const li = document.createElement('li'); li.textContent = item; return li; }));
    document.getElementById('pdv-confirmacao-desconto').textContent = dados.desconto.trim();
    document.getElementById('pdv-confirmacao-total').textContent = dados.total;
    document.getElementById('pdv-confirmacao-pagamento').textContent = `Pagamento: ${dados.pagamento}`;
    modal.hidden = false;
    botaoCancelar.focus();
    return new Promise(resolve => {
        const concluir = confirmado => { modal.hidden = true; botaoConfirmar.onclick = null; botaoCancelar.onclick = null; modal.onkeydown = null; if (!confirmado) document.getElementById('btn-salvar-venda-banco').focus(); resolve(confirmado); };
        botaoConfirmar.onclick = () => concluir(true);
        botaoCancelar.onclick = () => concluir(false);
        modal.onclick = evento => { if (evento.target === modal) concluir(false); };
        modal.onkeydown = evento => {
            if (evento.key === 'Escape') concluir(false);
            if (evento.key === 'Tab') { evento.preventDefault(); (document.activeElement === botaoCancelar ? botaoConfirmar : botaoCancelar).focus(); }
        };
    });
}
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function chaveCarrinho(item) { return `${item.produto_id}|${item.tamanho_id || ''}|${item.cor || ''}`; }
window.alterarQuantidadeCarrinho = (chave, delta) => {
    const item = carrinho.find(i => chaveCarrinho(i) === chave); if (!item) return;
    const produto = document.querySelector(`#select-prod option[value="${item.produto_id}"]`);
    const saldo = item.tamanho_id ? (JSON.parse(document.getElementById('variacoes-produtos')?.textContent || '{}')[item.produto_id] || []).find(v => String(v.tamanho_id) === String(item.tamanho_id) && v.cor === item.cor)?.estoque_atual : (produto?.dataset.semEstoque === 'true' ? Infinity : Number(JSON.parse(document.getElementById('estoque-filiais')?.textContent || '{}')[item.produto_id]?.[document.getElementById('filial-pdv')?.value] || 0));
    const qtd = item.quantidade + delta; if (qtd < 1) return;
    if (qtd > saldo) { window.alert('Quantidade acima do estoque disponível.'); atualizarTabelaCarrinho(); return; }
    item.quantidade = qtd; atualizarTabelaCarrinho();
};
window.definirQuantidadeCarrinho = (chave, valor) => {
    const item = carrinho.find(i => chaveCarrinho(i) === chave); if (!item) return;
    const qtd = Number.parseInt(valor, 10); if (!Number.isInteger(qtd) || qtd < 1) return atualizarTabelaCarrinho();
    window.alterarQuantidadeCarrinho(chave, qtd - item.quantidade);
};


function configurarPagamentoDividido() {
    const dividir = document.getElementById('dividir-pagamento');
    if (!dividir) return;
    dividir.addEventListener('change', () => atualizarPagamentoDividido('valor_pagamento_1', dividir.checked));
    ['forma_pagamento', 'forma_pagamento_2'].forEach(id => {
        document.getElementById(id)?.addEventListener('change', () => atualizarPagamentoDividido());
    });
    ['valor_pagamento_1', 'valor_pagamento_2'].forEach(id => {
        document.getElementById(id)?.addEventListener('input', () => atualizarPagamentoDividido(id));
    });
    atualizarPagamentoDividido();
}

function atualizarPagamentoDividido(editado, inicializar = false) {
    const dividir = document.getElementById('dividir-pagamento');
    if (!dividir) return;
    const primeira = document.getElementById('forma_pagamento');
    const segunda = document.getElementById('forma_pagamento_2');
    const valor1 = document.getElementById('valor_pagamento_1');
    const valor2 = document.getElementById('valor_pagamento_2');
    const resumo = document.getElementById('pagamento-dividido-resumo');
    const ativo = dividir.checked;
    document.getElementById('segundo-pagamento').hidden = !ativo;
    [segunda, valor1, valor2].forEach(campo => {
        campo.disabled = !ativo;
        campo.required = ativo;
        campo.setCustomValidity('');
    });
    if (!ativo) {
        segunda.value = ''; valor1.value = ''; valor2.value = '';
        resumo.textContent = '';
        return;
    }
    [...segunda.options].forEach(opcao => {
        opcao.disabled = Boolean(opcao.value && opcao.value === primeira.value);
    });
    if (segunda.value && segunda.value === primeira.value) segunda.value = '';
    const bruto = carrinho.reduce((soma, item) => soma + item.preco * item.quantidade, 0);
    const cortesia = document.getElementById('cortesia-aplicada')?.value === 'true';
    const manual = document.getElementById('desconto-manual-aplicado')?.value || '';
    const descontoAtivo = Boolean(document.getElementById('funcionario-comprador')?.value);
    const percentual = cortesia ? 100 : Math.min(100, (descontoAtivo ? 15 : 0) + Number(manual || 0));
    const total = Math.round((bruto - Math.round(bruto * percentual) / 100) * 100);
    const emCentavos = campo => Math.round(Number(campo.value) * 100);
    if (editado) {
        const origem = editado === 'valor_pagamento_2' ? valor2 : valor1;
        const destino = origem === valor1 ? valor2 : valor1;
        if (!origem.value && total > 0) {
            if (inicializar) {
                origem.value = (Math.ceil(total / 2) / 100).toFixed(2);
                destino.value = (Math.floor(total / 2) / 100).toFixed(2);
            } else destino.value = (total / 100).toFixed(2);
        } else {
            const restante = total - emCentavos(origem);
            destino.value = origem.value && Number.isFinite(restante) && restante > 0 ? (restante / 100).toFixed(2) : '';
        }
    } else if (!valor1.value && total > 0) {
        valor1.value = (total / 100).toFixed(2);
        valor2.value = '';
    } else if (valor1.value && !valor2.value) {
        const restante = total - emCentavos(valor1);
        if (restante > 0) valor2.value = (restante / 100).toFixed(2);
    }
    const soma = emCentavos(valor1) + emCentavos(valor2);
    const valido = valor1.value && valor2.value && emCentavos(valor1) > 0 && emCentavos(valor2) > 0 && soma === total;
    const mensagem = 'Informe dois valores positivos cuja soma seja igual ao total da venda.';
    valor2.setCustomValidity(valido ? '' : mensagem);
    const moeda = centavos => (centavos / 100).toLocaleString('pt-BR', {style: 'currency', currency: 'BRL'});
    resumo.textContent = valido ? `Pagamento dividido: ${moeda(emCentavos(valor1))} + ${moeda(emCentavos(valor2))} = ${moeda(total)}` : mensagem;
}
