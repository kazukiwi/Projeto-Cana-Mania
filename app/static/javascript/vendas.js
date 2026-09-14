let carrinho = [];

document.addEventListener('DOMContentLoaded', () => {
    const produto = document.getElementById('select-prod');
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

    const opcoes = () => variacoes[produto.value] || [];
    const formatarPreco = preco => `R$ ${Number(preco || 0).toFixed(2).replace('.', ',')}`;
    const saldoDaFilial = id => Number(estoquesFiliais[String(id)]?.[filial?.value] || 0);
    const aplicarFilial = () => {
        [...produto.options].forEach(opcao => {
            if (!opcao.value) return;
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
            const saldo = saldoDaFilial(produto.value);
            estoque.value = `${saldo} un`;
            quantidade.max = saldo;
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
            : Number(selecionado.dataset.estoque);
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

    document.getElementById('form-finalizar-real')?.addEventListener('submit', evento => {
        if (!carrinho.length) {
            evento.preventDefault();
            return;
        }

        evento.preventDefault();
        const formulario = evento.currentTarget;
        const botao = document.getElementById('btn-salvar-venda-banco');
        if (formulario.dataset.enviando === 'true') return;

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
    filial?.addEventListener('change', aplicarFilial);
    buscaFrozen?.addEventListener('input', () => {
        const termo = buscaFrozen.value.trim().toLocaleLowerCase('pt-BR');
        [...produto.options].forEach(opcao => {
            if (!opcao.value) return;
            const corresponde = !termo || opcao.textContent.toLocaleLowerCase('pt-BR').includes(termo);
            opcao.hidden = !corresponde || saldoDaFilial(opcao.value) <= 0;
        });
        const encontrados = [...produto.options].filter(opcao => opcao.value && !opcao.hidden).slice(0, 6);
        if (resultadoBusca) {
            resultadoBusca.innerHTML = termo ? encontrados.map(opcao => `<button type="button" data-produto-id="${opcao.value}"><i class="fa-solid fa-cube"></i>${opcao.textContent.trim()} <small>${saldoDaFilial(opcao.value)} un.</small></button>`).join('') || '<p>Nenhum frozen disponível nesta loja.</p>' : '';
            buscaFrozen.setAttribute('aria-expanded', String(Boolean(termo)));
        }
    });
    resultadoBusca?.addEventListener('click', evento => {
        const botao = evento.target.closest('[data-produto-id]');
        if (!botao) return;
        produto.value = botao.dataset.produtoId;
        buscaFrozen.value = produto.options[produto.selectedIndex].textContent.trim();
        resultadoBusca.innerHTML = '';
        buscaFrozen.setAttribute('aria-expanded', 'false');
        produto.dispatchEvent(new Event('change'));
    });
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
        return `<tr><td><strong>${item.nome}${variacao}</strong></td><td>${item.quantidade}x</td><td>R$ ${subtotal.toFixed(2).replace('.', ',')}</td><td><button type="button" onclick="removerDoCarrinho(${indice})">Remover</button></td></tr>`;
    }).join('');
    const cliente = document.getElementById('select-cliente');
    const associado = cliente?.options[cliente.selectedIndex]?.dataset.associado === 'true';
    const percentual = associado ? Number(cliente.dataset.descontoAssociado || 10) : 0;
    const desconto = total * percentual / 100;
    document.getElementById('pdv-total-bruto').textContent = `R$ ${total.toFixed(2).replace('.', ',')}`;
    document.getElementById('pdv-desconto').textContent = `- R$ ${desconto.toFixed(2).replace('.', ',')}`;
    document.getElementById('pdv-linha-desconto').style.display = associado && total ? 'flex' : 'none';
    document.getElementById('pdv-total-geral').textContent = `R$ ${(total - desconto).toFixed(2).replace('.', ',')}`;
    document.getElementById('carrinho_json_input').value = JSON.stringify(carrinho);
    document.getElementById('btn-salvar-venda-banco').disabled = !carrinho.length;
}

window.removerDoCarrinho = indice => { carrinho.splice(indice, 1); atualizarTabelaCarrinho(); };
