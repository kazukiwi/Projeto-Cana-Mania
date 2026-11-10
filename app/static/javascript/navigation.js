const inicializarNavegacao = () => {
    const botao = document.querySelector('.menu-toggle');
    const menu = document.getElementById('menu-principal');
    if (!botao || !menu) return;
    const fechar = () => {
        menu.classList.remove('menu-aberto');
        botao.setAttribute('aria-expanded', 'false');
        botao.setAttribute('aria-label', 'Abrir menu');
        botao.innerHTML = '<i class="fa-solid fa-bars" aria-hidden="true"></i>';
    };
    botao.addEventListener('click', () => {
        const aberto = menu.classList.toggle('menu-aberto');
        botao.setAttribute('aria-expanded', String(aberto));
        botao.setAttribute('aria-label', aberto ? 'Fechar menu' : 'Abrir menu');
        botao.innerHTML = aberto ? '<i class="fa-solid fa-xmark" aria-hidden="true"></i>' : '<i class="fa-solid fa-bars" aria-hidden="true"></i>';
        if (aberto) menu.querySelector('a')?.focus();
    });
    menu.querySelectorAll('a').forEach(link => link.addEventListener('click', fechar));
    document.addEventListener('click', evento => { if (menu.classList.contains('menu-aberto') && !menu.contains(evento.target) && !botao.contains(evento.target)) fechar(); });
    document.addEventListener('keydown', evento => { if (evento.key === 'Escape' && menu.classList.contains('menu-aberto')) { fechar(); botao.focus(); } });
    window.addEventListener('resize', () => { if (window.innerWidth > 900) fechar(); });
};

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inicializarNavegacao);
else inicializarNavegacao();
