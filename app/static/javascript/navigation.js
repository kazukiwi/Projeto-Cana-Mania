document.addEventListener('DOMContentLoaded', () => {
    const botao = document.querySelector('.menu-toggle');
    const menu = document.getElementById('menu-principal');
    if (!botao || !menu) return;
    const fechar = () => {
        menu.classList.remove('menu-aberto');
        botao.setAttribute('aria-expanded', 'false');
        botao.innerHTML = '<i class="fa-solid fa-bars"></i>';
    };
    botao.addEventListener('click', () => {
        const aberto = menu.classList.toggle('menu-aberto');
        botao.setAttribute('aria-expanded', String(aberto));
        botao.innerHTML = aberto ? '<i class="fa-solid fa-xmark"></i>' : '<i class="fa-solid fa-bars"></i>';
    });
    menu.querySelectorAll('a').forEach(link => link.addEventListener('click', fechar));
    window.addEventListener('resize', () => { if (window.innerWidth > 760) fechar(); });
});
