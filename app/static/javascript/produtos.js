document.addEventListener("DOMContentLoaded", () => {
    carregarProdutos();
});

async function carregarProdutos() {
    try {
        // Altere para a rota correta da sua API que retorna o JSON dos produtos
        const response = await fetch('/produtos'); 
        const produtos = await response.json();
        
        const corpoTabela = document.getElementById('corpo-tabela');
        const contador = document.getElementById('contador-produtos');
        
        corpoTabela.innerHTML = '';
        contador.textContent = `${produtos.length} produtos encontrados`;

        if (produtos.length === 0) {
            corpoTabela.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px;">Nenhum produto encontrado.</td></tr>`;
            return;
        }

        produtos.forEach(produto => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><img src="${produto.imagem_url || '/static/img/default.png'}" width="50" style="border-radius:4px;"></td>
                <td><strong>${produto.nome}</strong></td>
                <td>${produto.categoria_nome || 'Sem categoria'}</td>
                <td>${produto.estoque_atual}</td>
                <td>R$ ${parseFloat(produto.preco).toFixed(2)}</td>
                <td>${produto.estoque_atual <= 5 ? '<span style="color:red; font-weight:bold;">Estoque Baixo</span>' : '<span style="color:green;">Ativo</span>'}</td>
                <td style="text-align: center;">
                    <button style="background:none; border:none; color:#1e1b4b; cursor:pointer; margin-right:10px;"><i class="fa-solid fa-pen-to-square"></i></button>
                    <button style="background:none; border:none; color:red; cursor:pointer;"><i class="fa-solid fa-trash"></i></button>
                </td>
            `;
            corpoTabela.appendChild(tr);
        });
    } catch (error) {
        console.error("Erro ao carregar produtos:", error);
    }
}

document.addEventListener("DOMContentLoaded", function () {
    // Captura os elementos dos filtros
    const inputBusca = document.getElementById("input-busca");
    const selectCategoria = document.getElementById("select-categoria");
    const checkEstoqueBaixo = document.getElementById("check-estoque-baixo");
    const tabelaLinhas = document.querySelectorAll("#corpo-tabela tr");
    const contadorProdutos = document.getElementById("contador-produtos");

    function filtrarProdutos() {
        let textoBusca = inputBusca.value.toLowerCase();
        let categoriaSelecionada = selectCategoria.value; // Pega o ID da categoria
        let apenasEstoqueBaixo = checkEstoqueBaixo.checked;
        let produtosVisiveis = 0;

        tabelaLinhas.forEach(linha => {
            // Captura os dados de cada linha da tabela
            // Nota: Ajuste os índices [0, 1, 2...] se a ordem das suas colunas for diferente
            const nomeProduto = linha.cells[1]?.textContent.toLowerCase() || "";
            const categoriaTexto = linha.cells[2]?.textContent || "";
            const estoqueAtual = parseInt(linha.cells[3]?.textContent || "0", 10);

            // Se você colocou o ID da categoria em algum atributo na linha (ex: <tr data-categoria-id="...">), 
            // use ele. Se não, podemos comparar pelo nome do texto que está no <select>
            const textoOpcaoCategoria = selectCategoria.options[selectCategoria.selectedIndex]?.text;

            // Condições do Filtro
            const bateNome = nomeProduto.includes(textoBusca);
            const bateCategoria = categoriaSelecionada === "" || categoriaTexto.trim() === textoOpcaoCategoria.trim();
            const bateEstoque = !apenasEstoqueBaixo || estoqueAtual <= 5; // Defina "5" como o seu limite de estoque baixo

            // Decide se mostra ou esconde a linha
            if (bateNome && bateCategoria && bateEstoque) {
                linha.style.display = "";
                produtosVisiveis++;
            } else {
                linha.style.display = "none";
            }
        });

        // Atualiza o contador de produtos na tela dinamicamente
        if (contadorProdutos) {
            contadorProdutos.textContent = `${produtosVisiveis} produto(s) encontrado(s)`;
        }
    }

    // Escuta os eventos de digitação, mudança no select e clique no checkbox
    inputBusca.addEventListener("input", filtrarProdutos);
    selectCategoria.addEventListener("change", filtrarProdutos);
    checkEstoqueBaixo.addEventListener("change", filtrarProdutos);
});