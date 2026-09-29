(() => {
    const normalizar = texto => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    const busca = document.getElementById('cardapio-busca');
    busca.addEventListener('input', () => {
        const termo = normalizar(busca.value.trim());
        let encontrados = 0;
        document.querySelectorAll('[data-categoria]').forEach(secao => {
            let visiveis = 0;
            secao.querySelectorAll('[data-nome]').forEach(card => {
                card.hidden = !normalizar(card.dataset.nome).includes(termo);
                if (!card.hidden) visiveis++;
            });
            secao.hidden = Boolean(termo) && !visiveis;
            encontrados += visiveis;
        });
        document.getElementById('cardapio-sem-resultados').hidden = !termo || encontrados > 0;
    });
    try { document.documentElement.dataset.theme = localStorage.getItem('canamania-theme') || 'light'; } catch {}
    document.getElementById('cardapio-tema').addEventListener('click', () => {
        const tema = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = tema;
        try { localStorage.setItem('canamania-theme', tema); } catch {}
    });
})();
