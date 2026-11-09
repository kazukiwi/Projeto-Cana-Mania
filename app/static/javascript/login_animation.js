document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('.login-card');
    const tela = document.querySelector('.login-welcome');
    if (!form || !tela) return;

    let enviando = false;
    form.addEventListener('submit', evento => {
        if (enviando) {
            evento.preventDefault();
            return;
        }
        if (!form.reportValidity()) {
            evento.preventDefault();
            return;
        }

        evento.preventDefault();
        enviando = true;
        form.querySelectorAll('input, button').forEach(campo => { campo.disabled = true; });
        const botao = form.querySelector('button[type="submit"]');
        if (botao) botao.innerHTML = '<i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i> Validando...';
        tela.hidden = false;
        document.body.classList.add('is-entering');
        requestAnimationFrame(() => {
            tela.classList.add('login-welcome--visible');
            window.setTimeout(() => HTMLFormElement.prototype.submit.call(form), 100);
        });
    });
});
