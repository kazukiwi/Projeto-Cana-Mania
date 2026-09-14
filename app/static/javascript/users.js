document.addEventListener("DOMContentLoaded", function () {
    const inputBusca = document.getElementById("inputBusca");
    const selectPerfil = document.getElementById("selectPerfil");
    const checkAtivos = document.getElementById("checkAtivos");
    
    // Captura as linhas tanto da estrutura antiga quanto da nova unificada
    const linhasTabela = document.querySelectorAll(".table-container table tbody tr, .tabela-produtos tbody tr");

    function filtrarUsuarios() {
        // Remove acentos e espaços do que foi digitado
        const termoBusca = inputBusca.value.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
        const perfilSelecionado = selectPerfil.value.toLowerCase().trim();
        const apenasAtivos = checkAtivos.checked;

        linhasTabela.forEach(linha => {
            const celulaNome = linha.cells[0];
            const celulaEmail = linha.cells[1];

            // Pega nome e e-mail limpando acentos
            const nome = (celulaNome ? celulaNome.textContent : "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
            const email = (celulaEmail ? celulaEmail.textContent : "").toLowerCase().trim();
            
            // Pega o perfil textual (admin, funcionario, etc)
            const perfil = linha.querySelector(".badge-role, .badge-categoria")?.textContent.toLowerCase().trim() || "";
            
            // SOLUÇÃO DEFINITIVA: Lê o texto escrito na tela. Se o texto conter "ativo", ele é ativo.
            const textoStatus = linha.cells[3]?.textContent.toLowerCase().trim() || "";
            const statusAtivo = textoStatus.includes("ativo") && !textoStatus.includes("inativo");

            // Filtros lógicos combinados
            const bateBusca = termoBusca === "" || nome.includes(termoBusca) || email.includes(termoBusca);
            const batePerfil = perfilSelecionado === "" || perfil === perfilSelecionado;
            
            // Se 'apenasAtivos' for true, a linha só passa se 'statusAtivo' também for true
            const bateStatus = !apenasAtivos || statusAtivo;

            // Aplica o resultado visual na linha
            if (bateBusca && batePerfil && bateStatus) {
                linha.style.display = "";
            } else {
                linha.style.display = "none";
            }
        });
    }

    // Ouvintes de eventos
    if (inputBusca) inputBusca.addEventListener("input", filtrarUsuarios);
    if (selectPerfil) selectPerfil.addEventListener("change", filtrarUsuarios);
    if (checkAtivos) checkAtivos.addEventListener("change", filtrarUsuarios);

    // Roda ao carregar a página para respeitar o estado inicial do checkbox
    filtrarUsuarios();

    // Inicializa ícones do Lucide
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
});