(() => {
    const painel = document.querySelector('.access-panel');
    const movimentoReduzido = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (!painel) return;
    painel.addEventListener('pointermove', evento => {
        if (evento.pointerType === 'touch' || movimentoReduzido.matches) return;
        const area = painel.getBoundingClientRect();
        painel.style.setProperty('--luz-x', `${((evento.clientX - area.left) / area.width) * 100}%`);
        painel.style.setProperty('--luz-y', `${((evento.clientY - area.top) / area.height) * 100}%`);
    }, {passive: true});
    painel.addEventListener('pointerleave', () => {
        painel.style.removeProperty('--luz-x');
        painel.style.removeProperty('--luz-y');
    });
})();
