document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".btn-visualizar-variacoes").forEach((botao) => {
        botao.addEventListener("click", () => {
            const linha = botao.closest(".produto-com-variacoes");
            const preview = linha?.nextElementSibling;
            if (!linha || !preview?.matches("[data-variacoes-preview]")) return;

            const aberto = linha.classList.toggle("is-preview-open");
            botao.setAttribute("aria-expanded", String(aberto));
            preview.setAttribute("aria-hidden", String(!aberto));
        });
    });
});
