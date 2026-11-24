(() => {
  const input = document.getElementById('busca-cardapio');
  const botoes = [...document.querySelectorAll('[data-category-filter]')];
  const cards = [...document.querySelectorAll('[data-product-card]')];
  const secoes = [...document.querySelectorAll('[data-category-section]')];
  const resultado = document.getElementById('resultado-cardapio');
  const vazio = document.getElementById('sem-resultados');
  if (!input || !botoes.length || !cards.length) return;

  let categoriaAtiva = 'all';
  const normalizar = texto => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('pt-BR').trim();

  const filtrar = () => {
    const termo = normalizar(input.value);
    let visiveis = 0;
    cards.forEach(card => {
      const pertence = categoriaAtiva === 'all' || card.dataset.category === categoriaAtiva;
      const corresponde = !termo || normalizar(card.dataset.search || '').includes(termo);
      card.hidden = !(pertence && corresponde);
      if (!card.hidden) visiveis += 1;
    });
    secoes.forEach(secao => {
      secao.hidden = !secao.querySelector('[data-product-card]:not([hidden])');
    });
    vazio.hidden = visiveis > 0;
    resultado.textContent = visiveis === 1 ? '1 produto encontrado' : `${visiveis} produtos encontrados`;
  };

  botoes.forEach(botao => botao.addEventListener('click', () => {
    categoriaAtiva = botao.dataset.categoryFilter;
    botoes.forEach(item => {
      const ativo = item === botao;
      item.classList.toggle('is-active', ativo);
      item.setAttribute('aria-pressed', String(ativo));
    });
    filtrar();
  }));
  input.addEventListener('input', filtrar);
  filtrar();
})();
