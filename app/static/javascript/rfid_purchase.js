(() => {
    const startButton = document.getElementById('btn-rfid-demo');
    const cancelButton = document.getElementById('btn-rfid-cancelar');
    const message = document.getElementById('rfid-demo-status');
    const total = document.getElementById('pdv-total-geral');
    if (!startButton || !cancelButton || !message || !total) return;
    let operationId = null;
    let cancelled = false;
    const pause = ms => new Promise(resolve => window.setTimeout(resolve, ms));
    const centsFromTotal = () => Math.round(Number(total.textContent.replace(/[^\d,]/g, '').replace(/\./g, '').replace(',', '.')) * 100);
    const errorMessage = async response => {
        const body = await response.json().catch(() => ({}));
        return body.detail || `Falha na comunicação (${response.status}).`;
    };
    async function begin() {
        const cents = centsFromTotal();
        const cart = document.getElementById('carrinho_json_input')?.value || '[]';
        const discount = document.getElementById('desconto-manual-aplicado')?.value || '0';
        const employee = document.getElementById('funcionario-comprador')?.value || '';
        const split = document.getElementById('dividir-pagamento');
        if (split?.checked) { message.textContent = 'Desative o pagamento dividido para iniciar uma compra simulada RFID.'; return; }
        if (!Number.isSafeInteger(cents) || cents < 1) { message.textContent = 'Monte um carrinho com total maior que zero.'; return; }
        startButton.disabled = true;
        message.textContent = 'Aproxime o cartão para a compra demonstrativa…';
        try {
            const response = await fetch('/rfid/operacoes', {method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({tipo: 'pagar', centavos: cents, carrinho_json: cart,
                    desconto_percentual: discount, funcionario_comprador_id: employee})});
            if (!response.ok) throw new Error(await errorMessage(response));
            const operation = await response.json();
            operationId = operation.id;
            cancelButton.hidden = false;
            let result;
            while (operationId && !cancelled) {
                await pause(350);
                const statusResponse = await fetch(`/rfid/operacoes/${encodeURIComponent(operationId)}`, {cache: 'no-store'});
                if (!statusResponse.ok) throw new Error(await errorMessage(statusResponse));
                result = await statusResponse.json();
                if (result.status !== 'aguardando_tag') break;
            }
            if (!result) return;
            if (result.status === 'aprovado') {
                message.textContent = 'Saldo debitado. Abrindo o comprovante da demonstração…';
                window.location.assign(`/pdv/rfid/recibo/${encodeURIComponent(operation.id)}`);
            } else if (result.status === 'negado_saldo_insuficiente') {
                message.textContent = `Saldo insuficiente. Disponível: ${new Intl.NumberFormat('pt-BR', {style: 'currency', currency: 'BRL'}).format((result.saldo_centavos || 0) / 100)}.`;
            } else if (result.status === 'negado_nao_cadastrado') message.textContent = 'Cartão não cadastrado. Peça ao administrador para cadastrá-lo.';
            else if (result.status === 'expirado') message.textContent = 'Leitura expirada. Inicie uma nova tentativa.';
            else if (result.status === 'erro_comunicacao') message.textContent = 'Leitor desconectado ou falha na comunicação serial.';
            else message.textContent = `Operação encerrada: ${result.status}.`;
        } catch (error) { message.textContent = error.message || 'Não foi possível iniciar a leitura RFID.'; }
        finally { operationId = null; cancelled = false; cancelButton.hidden = true; cancelButton.disabled = false; startButton.disabled = false; }
    }
    startButton.addEventListener('click', begin);
    cancelButton.addEventListener('click', async () => {
        if (!operationId) return;
        cancelButton.disabled = true;
        try {
            const response = await fetch(`/rfid/operacoes/${encodeURIComponent(operationId)}/cancelar`, {method: 'POST'});
            if (!response.ok) throw new Error(await errorMessage(response));
            cancelled = true; operationId = null; message.textContent = 'Leitura cancelada.';
        } catch (error) { cancelButton.disabled = false; message.textContent = error.message; }
    });
})();
