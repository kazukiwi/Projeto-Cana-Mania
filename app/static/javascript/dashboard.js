document.addEventListener("DOMContentLoaded", () => {
    const prefereMovimentoReduzido = window.matchMedia("(prefers-reduced-motion: reduce)");
    const seletorCategoria = document.querySelector("#categoria-produtos");

    if (seletorCategoria) {
        seletorCategoria.addEventListener("change", () => {
            document.querySelectorAll(".vitrine-categoria").forEach((categoria) => {
                categoria.hidden = categoria.id !== seletorCategoria.value;
            });
        });
    }

    document.querySelectorAll(".card-link").forEach((card) => {
        card.addEventListener("click", (evento) => {
            // Mantém intactos os comportamentos esperados de abrir em outra aba.
            if (
                evento.defaultPrevented ||
                evento.button !== 0 ||
                evento.metaKey ||
                evento.ctrlKey ||
                evento.shiftKey ||
                evento.altKey ||
                prefereMovimentoReduzido.matches
            ) {
                return;
            }

            evento.preventDefault();
            card.classList.add("is-navigating");
            document.body.classList.add("dashboard-navigating");

            window.setTimeout(() => {
                window.location.assign(card.href);
            }, 280);
        });
    });
});
