document.addEventListener("click", (event) => {
    const button = event.target.closest(".password-eye");
    if (!button) return;

    const field = button.parentElement.querySelector('input[type="password"], input[type="text"]');
    if (!field) return;

    const mostrar = field.type === "password";
    field.type = mostrar ? "text" : "password";
    button.setAttribute("aria-pressed", String(mostrar));
    button.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
    const icon = button.querySelector("i");
    if (icon) {
        icon.classList.toggle("fa-eye", !mostrar);
        icon.classList.toggle("fa-eye-slash", mostrar);
    }
});
