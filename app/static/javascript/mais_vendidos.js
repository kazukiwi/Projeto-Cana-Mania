document.addEventListener('DOMContentLoaded', () => {
    const containerDados = document.getElementById('dados-jinja');
    const seletorCategoria = document.getElementById('select-categoria-filtro');
    const btnQuantidade = document.getElementById('btn-ordem-qtd');
    const btnReceita = document.getElementById('btn-ordem-receita');
    const corpoRanking = document.getElementById('ranking-produtos-corpo');

    if (!containerDados || !seletorCategoria || !corpoRanking) return;

    let produtos = [];
    try {
        produtos = JSON.parse(containerDados.textContent || '[]');
    } catch (erro) {
        console.error('Não foi possível carregar os dados dos produtos.', erro);
    }

    let ordenacao = 'quantidade';
    let graficoProdutos;
    let graficoCategorias;
    const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

    const escaparHtml = (valor) => String(valor ?? '').replace(/[&<>"']/g, caractere => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[caractere]));

    function produtosFiltrados() {
        return produtos
            .filter(produto => seletorCategoria.value === 'todas' || produto.categoria === seletorCategoria.value)
            .sort((a, b) => ordenacao === 'receita'
                ? Number(b.receita) - Number(a.receita)
                : Number(b.vendas) - Number(a.vendas));
    }

    function atualizarIndicadores(lista) {
        const unidades = lista.reduce((total, produto) => total + Number(produto.vendas || 0), 0);
        const receita = lista.reduce((total, produto) => total + Number(produto.receita || 0), 0);
        document.getElementById('indicador-total-vendas').innerHTML = `${unidades} <span style="font-size:13px; color:#64748b; font-weight:normal;">unidades</span>`;
        document.getElementById('indicador-receita-total').textContent = moeda.format(receita);
        document.getElementById('indicador-ticket-medio').textContent = moeda.format(unidades ? receita / unidades : 0);
    }

    function atualizarTabela(lista) {
        const totalUnidades = lista.reduce((total, produto) => total + Number(produto.vendas || 0), 0);
        if (!lista.length) {
            corpoRanking.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:24px; color:#64748b;">Nenhum produto encontrado para esta categoria.</td></tr>';
            return;
        }

        corpoRanking.innerHTML = lista.map((produto, indice) => {
            const vendas = Number(produto.vendas || 0);
            const receita = Number(produto.receita || 0);
            const percentual = totalUnidades ? ((vendas / totalUnidades) * 100).toFixed(1) : '0.0';
            return `<tr>
                <td><strong>#${indice + 1}</strong></td>
                <td><strong>${escaparHtml(produto.nome)}</strong><br><span style="font-size:11px; color:#94a3b8;">${escaparHtml(produto.codigo)}</span></td>
                <td><span class="badge-categoria">${escaparHtml(produto.categoria)}</span></td>
                <td>${vendas} <span style="font-size:12px; color:#64748b;">unidades</span></td>
                <td style="color:#16a34a; font-weight:600;">${moeda.format(receita)}</td>
                <td>${moeda.format(vendas ? receita / vendas : 0)}</td>
                <td><div style="display:flex; align-items:center; gap:8px;"><div style="flex:1; background:#f1f5f9; height:8px; border-radius:4px; overflow:hidden;"><div style="background:#2563eb; width:${percentual}%; height:100%;"></div></div><span style="font-size:12px; font-weight:600;">${percentual}%</span></div></td>
            </tr>`;
        }).join('');
    }

    function atualizarGraficos(lista) {
        const dadosCategorias = lista.reduce((resultado, produto) => {
            const valor = ordenacao === 'receita' ? Number(produto.receita || 0) : Number(produto.vendas || 0);
            resultado[produto.categoria] = (resultado[produto.categoria] || 0) + valor;
            return resultado;
        }, {});
        const rotulo = ordenacao === 'receita' ? 'Receita (R$)' : 'Unidades Vendidas';
        const valoresProdutos = lista.map(produto => ordenacao === 'receita' ? Number(produto.receita) : Number(produto.vendas));
        document.getElementById('titulo-grafico-categorias').textContent = ordenacao === 'receita' ? 'Receita por Categoria' : 'Vendas por Categoria';

        if (graficoProdutos) graficoProdutos.destroy();
        if (graficoCategorias) graficoCategorias.destroy();

        const ctxProdutos = document.getElementById('chartTopProdutos');
        const ctxCategorias = document.getElementById('chartCategorias');
        if (ctxProdutos) graficoProdutos = new Chart(ctxProdutos, { type: 'bar', data: { labels: lista.map(p => p.nome), datasets: [{ label: rotulo, data: valoresProdutos, backgroundColor: '#2563eb', borderRadius: 6, barThickness: 25 }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#f1f5f9' } }, x: { grid: { display: false } } } } });
        if (ctxCategorias) graficoCategorias = new Chart(ctxCategorias, { type: 'doughnut', data: { labels: Object.keys(dadosCategorias), datasets: [{ data: Object.values(dadosCategorias), backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ec4899', '#8b5cf6'], borderWidth: 2, borderColor: '#ffffff' }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, padding: 15 } } }, cutout: '70%' } });
    }

    function atualizarTela() {
        const lista = produtosFiltrados();
        atualizarIndicadores(lista);
        atualizarTabela(lista);
        atualizarGraficos(lista);
    }

    function definirOrdenacao(tipo) {
        ordenacao = tipo;
        btnQuantidade.classList.toggle('active', tipo === 'quantidade');
        btnReceita.classList.toggle('active', tipo === 'receita');
        atualizarTela();
    }

    seletorCategoria.addEventListener('change', atualizarTela);
    btnQuantidade.addEventListener('click', () => definirOrdenacao('quantidade'));
    btnReceita.addEventListener('click', () => definirOrdenacao('receita'));

    document.querySelector('.btn-exportar-csv')?.addEventListener('click', () => {
        const linhas = [...document.querySelectorAll('table.tabela-vendas tr')].map(linha =>
            [...linha.querySelectorAll('td, th')].map(celula => `"${celula.innerText.replace(/\s+/g, ' ').trim().replace(/"/g, '""')}"`).join(';')
        );
        const link = document.createElement('a');
        link.href = URL.createObjectURL(new Blob([`\uFEFF${linhas.join('\n')}`], { type: 'text/csv;charset=utf-8;' }));
        link.download = 'relatorio_mais_vendidos.csv';
        link.click();
        URL.revokeObjectURL(link.href);
    });

    atualizarTela();
});
