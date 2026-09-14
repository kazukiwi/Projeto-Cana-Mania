document.addEventListener("DOMContentLoaded", function () {
    const form = document.getElementById("form-finalizar-dia");
    const modal = document.getElementById("modal-finalizar-dia");
    const cancelar = document.getElementById("btn-cancelar-finalizacao");
    const confirmar = document.getElementById("btn-confirmar-finalizacao");
    const botao = document.getElementById("btn-finalizar-dia");
    if (!form || !modal || !confirmar) return;

    const fechar = function () { modal.classList.remove("aberto"); modal.setAttribute("aria-hidden", "true"); };
    form.addEventListener("submit", function (event) {
        event.preventDefault();
        modal.classList.add("aberto");
        modal.setAttribute("aria-hidden", "false");
    });
    cancelar?.addEventListener("click", fechar);
    modal.addEventListener("click", function (event) { if (event.target === modal) fechar(); });
    confirmar.addEventListener("click", function () {
        confirmar.disabled = true;
        confirmar.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Finalizando...';
        if (botao) { botao.disabled = true; botao.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Finalizando...'; }
        form.submit();
    });
});
