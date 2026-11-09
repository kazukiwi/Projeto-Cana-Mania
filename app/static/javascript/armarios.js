document.addEventListener("DOMContentLoaded", function () {
    const cards = Array.from(document.querySelectorAll("[data-armario-card]"));
    const botoesFiltro = Array.from(document.querySelectorAll("[data-filtro]"));
    const modal = document.getElementById("modal-armario");
    const form = document.getElementById("form-armario");
    const modalTitulo = document.getElementById("modal-titulo");
    const modalSubtitulo = document.getElementById("modal-subtitulo");
    const modalInfo = document.getElementById("modal-info");
    const inputArmarioId = document.getElementById("modal-armario-id");
    const selectStatus = document.getElementById("modal-status");
    const selectFilial = document.getElementById("modal-filial");
    const inputObservacoes = document.getElementById("modal-observacoes");
    const campoObservacao = document.querySelector(".campo-observacao");
    const btnFechar = document.getElementById("btn-fechar-modal");
    const btnCancelar = document.getElementById("btn-cancelar");
    const tabs = Array.from(document.querySelectorAll("[data-armarios-tab]"));
    const panels = Array.from(document.querySelectorAll("[data-armarios-panel]"));
    const buscaReserva = document.getElementById("busca-reserva");
    const filtroSemestre = document.getElementById("filtro-semestre");
    const btnDesativarArmario = document.getElementById("btn-desativar-armario");
    const modalConfirmacao = document.getElementById("modal-confirmacao");
    const formConfirmacao = document.getElementById("form-confirmacao");
    const textoConfirmacao = document.getElementById("confirmacao-texto");
    const tituloConfirmacao = document.getElementById("confirmacao-titulo");
    const btnFecharConfirmacao = document.getElementById("btn-fechar-confirmacao");

    function abrirAba(nome) {
        tabs.forEach(function (tab) { tab.classList.toggle("active", tab.dataset.armariosTab === nome); });
        panels.forEach(function (panel) { panel.hidden = panel.dataset.armariosPanel !== nome; });
    }

    function filtrarReservas() {
        const termo = (buscaReserva ? buscaReserva.value : "").toLocaleLowerCase("pt-BR");
        const semestre = filtroSemestre ? filtroSemestre.value : "";
        document.querySelectorAll("[data-reserva]").forEach(function (linha) {
            const local = (linha.dataset.local || "").toLocaleLowerCase("pt-BR");
            linha.hidden = !(local.includes(termo) && (!semestre || linha.dataset.semestre === semestre));
        });
    }

    function aplicarFiltro(status) {
        cards.forEach(function (card) {
            const statusCard = card.getAttribute("data-status");
            card.style.display = !status || statusCard === status ? "" : "none";
        });
    }

    function atualizarCamposModal() {
        const status = selectStatus ? selectStatus.value : "";

        if (campoObservacao) {
            campoObservacao.style.display = status === "manutencao" ? "" : "none";
        }

        if (inputObservacoes) {
            inputObservacoes.required = status === "manutencao";
        }
    }

    function abrirModal(card) {
        const numero = card.getAttribute("data-numero") || "";
        const status = card.getAttribute("data-status") || "disponivel";
        const filial = card.getAttribute("data-filial") || "";
        const observacoes = card.getAttribute("data-observacoes") || "";

        if (modalTitulo) modalTitulo.textContent = "M?quina " + numero;
        if (modalSubtitulo) modalSubtitulo.textContent = "Estado atual: " + status;
        if (modalInfo) modalInfo.textContent = "Filial: " + filial;
        if (inputArmarioId) inputArmarioId.value = card.getAttribute("data-id") || "";
        if (selectStatus) selectStatus.value = status;
        if (selectFilial) selectFilial.value = filial;
        if (inputObservacoes) inputObservacoes.value = observacoes;

        atualizarCamposModal();

        if (modal) {
            modal.classList.add("open");
            modal.setAttribute("aria-hidden", "false");
        }
    }

    function fecharModal() {
        if (modal) {
            modal.classList.remove("open");
            modal.setAttribute("aria-hidden", "true");
        }
    }

    function abrirConfirmacao(action, titulo, texto, botao) {
        if (!modalConfirmacao || !formConfirmacao) return;
        formConfirmacao.action = action;
        if (tituloConfirmacao) tituloConfirmacao.textContent = titulo;
        if (textoConfirmacao) textoConfirmacao.textContent = texto;
        const confirmar = document.getElementById("btn-confirmar-acao");
        if (confirmar) confirmar.textContent = botao;
        modalConfirmacao.classList.add("open");
        modalConfirmacao.setAttribute("aria-hidden", "false");
    }

    function fecharConfirmacao() {
        if (!modalConfirmacao) return;
        modalConfirmacao.classList.remove("open");
        modalConfirmacao.setAttribute("aria-hidden", "true");
    }

    botoesFiltro.forEach(function (botao) {
        botao.addEventListener("click", function () {
            botoesFiltro.forEach(function (item) {
                item.classList.remove("active");
            });
            botao.classList.add("active");
            aplicarFiltro(botao.getAttribute("data-filtro") || "");
        });
    });

    cards.forEach(function (card) {
        card.addEventListener("click", function () {
            abrirModal(card);
        });
    });

    if (selectStatus) {
        selectStatus.addEventListener("change", atualizarCamposModal);
    }

    if (btnFechar) btnFechar.addEventListener("click", fecharModal);
    if (btnCancelar) btnCancelar.addEventListener("click", fecharModal);
    if (modal) {
        modal.addEventListener("click", function (event) {
            if (event.target === modal) fecharModal();
        });
    }
    if (btnDesativarArmario) {
        btnDesativarArmario.addEventListener("click", function () {
            const id = inputArmarioId?.value;
            const numero = modalTitulo?.textContent.replace("M\u00e1quina ", "") || "";
            if (id) abrirConfirmacao(`/armarios/${id}/desativar`, "Desativar m\u00e1quina?", `A m\u00e1quina ${numero} deixar\u00e1 de aparecer como dispon\u00edvel. O hist\u00f3rico de reservas ser\u00e1 mantido.`, "Desativar m\u00e1quina");
        });
    }

    tabs.forEach(function (tab) {
        tab.addEventListener("click", function () { abrirAba(tab.dataset.armariosTab); });
    });
    if (buscaReserva) buscaReserva.addEventListener("input", filtrarReservas);
    if (filtroSemestre) filtroSemestre.addEventListener("change", filtrarReservas);

    document.querySelectorAll("[data-confirmacao]").forEach(function (formulario) {
        formulario.addEventListener("submit", function (event) {
            event.preventDefault();
            const linha = formulario.closest("tr");
            const maquina = linha?.cells[0]?.textContent || "esta m\u00e1quina";
            const local = linha?.cells[1]?.textContent || "o local";
            abrirConfirmacao(formulario.action, "Cancelar reserva?", `A reserva da m\u00e1quina ${maquina} para ${local} ser\u00e1 cancelada e registrada no hist\u00f3rico.`, "Cancelar reserva");
        });
    });
    if (btnFecharConfirmacao) btnFecharConfirmacao.addEventListener("click", fecharConfirmacao);
    if (modalConfirmacao) modalConfirmacao.addEventListener("click", function (event) { if (event.target === modalConfirmacao) fecharConfirmacao(); });
    document.querySelectorAll("[data-feedback-form]").forEach(function (formulario) {
        formulario.addEventListener("submit", function () {
            const botao = formulario.querySelector("button[type='submit']");
            if (botao) { botao.disabled = true; botao.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...'; }
        });
    });
});
