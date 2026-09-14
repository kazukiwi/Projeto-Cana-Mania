document.addEventListener("DOMContentLoaded", function () {
    const modal = document.getElementById("modal-confirmacao-acao");
    const formConfirmacao = document.getElementById("form-confirmacao-acao");
    const titulo = document.getElementById("confirmacao-acao-titulo");
    const texto = document.getElementById("confirmacao-acao-texto");
    const confirmar = document.getElementById("confirmacao-acao-confirmar");
    const cancelar = document.getElementById("confirmacao-acao-cancelar");
    if (!modal || !formConfirmacao || !confirmar) return;

    const fechar = () => { modal.classList.remove("aberto"); modal.setAttribute("aria-hidden", "true"); };
    document.querySelectorAll("form[data-confirmacao]").forEach((formulario) => {
        formulario.addEventListener("submit", (event) => {
            event.preventDefault();
            formConfirmacao.action = formulario.action;
            titulo.textContent = formulario.dataset.titulo || "Confirmar ação";
            texto.textContent = formulario.dataset.mensagem || "Deseja continuar?";
            confirmar.innerHTML = `<i class="fa-solid fa-check"></i> ${formulario.dataset.confirmar || "Confirmar"}`;
            modal.classList.add("aberto");
            modal.setAttribute("aria-hidden", "false");
        });
    });
    cancelar?.addEventListener("click", fechar);
    modal.addEventListener("click", (event) => { if (event.target === modal) fechar(); });
    confirmar.addEventListener("click", () => {
        confirmar.disabled = true;
        confirmar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processando...';
        formConfirmacao.submit();
    });
});
