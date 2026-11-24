(() => {
    const readButton = document.getElementById('rfid-ler');
    const cancelButton = document.getElementById('rfid-cancelar');
    const pingButton = document.getElementById('rfid-ping');
    const status = document.getElementById('rfid-status');
    const cardBox = document.getElementById('rfid-cartao-atual');
    if (!readButton || !status || !cardBox) return;

    let activeId = null;
    let cancelled = false;
    let confirmationPending = false;
    const wait = ms => new Promise(resolve => window.setTimeout(resolve, ms));
    const money = cents => new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format((cents || 0) / 100);
    async function request(url, options = {}) {
        const response = await fetch(url, {headers: {'Content-Type': 'application/json'}, ...options});
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || `Falha na comunicação (${response.status}).`);
        return data;
    }
    function displayCard(info, canRegister, allowRecarga = true) {
        cardBox.hidden = false;
        cardBox.replaceChildren();
        const heading = document.createElement('h3');
        heading.textContent = canRegister ? 'Cartão ainda não cadastrado' : (info.nome || 'Cartão cadastrado');
        const details = document.createElement('p');
        details.textContent = `UID ${info.uid} · ${canRegister ? 'Defina nome e saldo inicial.' : `Saldo atual: ${money(info.saldo_centavos)}.`}`;
        cardBox.append(heading, details);
        if (!canRegister && !allowRecarga) { loadHistory(info.uid); return; }
        const form = document.createElement('form');
        form.className = 'rfid-form';
        form.innerHTML = canRegister
            ? '<label>Nome do cartão<input name="nome" maxlength="100" required></label><label>Saldo inicial (R$)<input name="valor" type="number" min="0.01" step="0.01" required></label><button type="submit" data-acao="cadastro">Cadastrar cartão</button>'
            : '<label>Acrescentar créditos fictícios (R$)<input name="valor" type="number" min="0.01" step="0.01" required></label><button type="submit" data-acao="recarga">Adicionar créditos</button>';
        form.addEventListener('submit', async event => {
            event.preventDefault();
            const action = event.submitter?.dataset.acao || (canRegister ? 'cadastro' : 'recarga');
            const formData = new FormData(form);
            const raw = formData.get('valor');
            const amount = raw ? Math.round(Number(String(raw).replace(',', '.')) * 100) : 0;
            if (action !== 'consultar' && (!Number.isSafeInteger(amount) || amount < 1)) { status.textContent = 'Informe um valor válido.'; return; }
            const payload = {acao: action, centavos: amount};
            if (canRegister) payload.nome = new FormData(form).get('nome').trim();
            try {
                status.textContent = 'Atualizando o saldo no sistema e confirmando no leitor…';
                const result = await request(`/admin/cartoes-rfid/operacoes/${encodeURIComponent(activeId)}/concluir`, {method: 'POST', body: JSON.stringify(payload)});
                status.textContent = `${action === 'cadastro' ? 'Cartão cadastrado' : action === 'recarga' ? 'Recarga concluída' : 'Consulta concluída'}. Saldo atual: ${money(result.saldo_centavos)}.`;
                confirmationPending = false;
                cancelButton.hidden = true;
                activeId = null;
                displayCard({...info, nome: payload.nome || info.nome, saldo_centavos: result.saldo_centavos}, false, false);
                loadHistory(info.uid);
                window.setTimeout(() => { cardBox.hidden = true; }, 4000);
            } catch (error) { status.textContent = error.message; }
        });
        cardBox.append(form);
        if (!canRegister) loadHistory(info.uid);
    }
    async function loadHistory(uid) {
        try {
            const rows = await request(`/admin/cartoes-rfid/${encodeURIComponent(uid)}/historico`);
            const table = document.createElement('table');
            table.className = 'rfid-table';
            const head = document.createElement('thead');
            head.innerHTML = '<tr><th>Operação</th><th>Valor</th><th>Saldo depois</th><th>Resultado</th></tr>';
            const body = document.createElement('tbody');
            rows.forEach(row => {
                const tr = document.createElement('tr');
                [row.tipo, money(row.valor_centavos), money(row.saldo_depois), row.status].forEach(value => {
                    const td = document.createElement('td'); td.textContent = value; tr.append(td);
                });
                body.append(tr);
            });
            table.append(head, body);
            cardBox.append(table);
        } catch (error) { status.textContent = error.message; }
    }
    async function readCard() {
        readButton.disabled = true;
        cardBox.hidden = true;
        status.textContent = 'Aproxime o cartão do leitor…';
        try {
            const started = await request('/rfid/operacoes', {method: 'POST', body: JSON.stringify({tipo: 'identificar'})});
            activeId = started.id;
            cancelButton.hidden = false;
            let result;
            while (activeId && !cancelled) {
                await wait(400);
                result = await request(`/rfid/operacoes/${encodeURIComponent(activeId)}`);
                if (result.status !== 'aguardando_tag') break;
            }
            if (!result) return;
            if (result.status === 'tag_recebida') {
                confirmationPending = true;
                const cadastrado = Boolean(result.nome);
                status.textContent = cadastrado ? `Cartão ${result.nome} identificado. Saldo: ${money(result.saldo_centavos)}.` : `Cartão ${result.uid} identificado. Escolha o nome e o saldo inicial.`;
                displayCard(result, !cadastrado);
            } else if (result.status === 'expirado') status.textContent = 'Leitura expirada. Clique em “Ler cartão” para iniciar outra.';
            else if (result.status === 'erro_comunicacao') status.textContent = 'Leitor desconectado. Confira o cabo e a porta COM.';
            else status.textContent = `Leitura encerrada: ${result.status}.`;
        } catch (error) { status.textContent = error.message; }
        finally { cancelButton.hidden = !confirmationPending; cancelButton.disabled = false; readButton.disabled = false; cancelled = false; }
    }
    readButton.addEventListener('click', readCard);
    cancelButton.addEventListener('click', async () => {
        if (!activeId) return;
        cancelButton.disabled = true;
        try { await request(`/rfid/operacoes/${encodeURIComponent(activeId)}/cancelar`, {method: 'POST'}); cancelled = true; activeId = null; confirmationPending = false; cardBox.hidden = true; cancelButton.hidden = true; status.textContent = 'Leitura cancelada.'; }
        catch (error) { cancelButton.disabled = false; status.textContent = error.message; }
    });
    pingButton?.addEventListener('click', async () => {
        pingButton.disabled = true;
        try { const result = await request('/admin/cartoes-rfid/ping', {method: 'POST'}); status.textContent = `Arduino conectado (${result.status}).`; }
        catch (error) { status.textContent = error.message; }
        finally { pingButton.disabled = false; }
    });
})();
