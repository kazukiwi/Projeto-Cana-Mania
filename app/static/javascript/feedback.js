document.addEventListener('DOMContentLoaded', () => {
    const boasVindas = document.getElementById('feedback-bem-vindo');

    if (boasVindas) {
        boasVindas.classList.add('feedback-bem-vindo');
        window.setTimeout(() => {
            boasVindas.classList.add('feedback-bem-vindo-saindo');
            window.setTimeout(() => boasVindas.remove(), 350);
        }, 2200);
    }

    let processando = false;

    function mostrarProcessando(mensagem = 'Aguarde enquanto concluímos sua solicitação.') {
        if (processando) return;
        processando = true;
        const modal = document.createElement('div');
        modal.className = 'feedback-processando-modal';
        modal.setAttribute('role', 'status');
        modal.setAttribute('aria-live', 'assertive');
        modal.innerHTML = '<div class="feedback-processando-card"><i class="fa-solid fa-spinner fa-spin" aria-hidden="true"></i><h2>Processando...</h2><p></p></div>';
        modal.querySelector('p').textContent = mensagem;
        document.body.appendChild(modal);
    }

    function desabilitarEnvio(formulario) {
        formulario.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((botao) => {
            botao.disabled = true;
            botao.classList.add('feedback-processando');
        });
    }

    document.querySelectorAll('form').forEach((formulario) => {
        formulario.addEventListener('submit', (evento) => {
            if (evento.defaultPrevented || formulario.dataset.semProcessando !== undefined || formulario.matches('[data-confirm], [data-confirmacao]')) return;
            desabilitarEnvio(formulario);
            mostrarProcessando();
        });
    });

    document.querySelectorAll('a[href]').forEach((link) => {
        link.addEventListener('click', (evento) => {
            const destino = link.getAttribute('href');
            if (evento.defaultPrevented || !destino || destino.startsWith('#') || link.target === '_blank' || evento.metaKey || evento.ctrlKey || evento.shiftKey || evento.altKey) return;
            if (link.classList.contains('btn-sair')) return;
            mostrarProcessando('Carregando a página solicitada.');
        });
    });

    document.querySelectorAll('.btn-sair').forEach((link) => {
        link.addEventListener('click', (evento) => {
            evento.preventDefault();
            if (document.getElementById('feedback-confirmar-saida')) return;

            const modal = document.createElement('div');
            modal.className = 'feedback-modal';
            modal.id = 'feedback-confirmar-saida';
            modal.innerHTML = '<div class="feedback-modal-card" role="dialog" aria-modal="true" aria-labelledby="feedback-saida-titulo"><div class="feedback-modal-icone"><i class="fa-solid fa-right-from-bracket" aria-hidden="true"></i></div><h2 id="feedback-saida-titulo">Sair da conta?</h2><p>Você precisará entrar novamente para acessar o sistema.</p><div class="feedback-modal-acoes"><button type="button" class="feedback-modal-cancelar">Cancelar</button><button type="button" class="feedback-modal-confirmar">Sair</button></div></div>';
            document.body.appendChild(modal);

            const fechar = () => modal.remove();
            modal.querySelector('.feedback-modal-cancelar').addEventListener('click', fechar);
            modal.addEventListener('click', (clique) => { if (clique.target === modal) fechar(); });
            modal.querySelector('.feedback-modal-confirmar').addEventListener('click', () => {
                mostrarProcessando('Encerrando sua sessão.');
                window.location.assign(link.href);
            });
        });
    });
});
