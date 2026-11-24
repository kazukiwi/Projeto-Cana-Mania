(() => {
    let contexto;

    function preparar() {
        try {
            const AudioContexto = window.AudioContext || window.webkitAudioContext;
            if (!AudioContexto) return;
            contexto ||= new AudioContexto();
            if (contexto.state === 'suspended') contexto.resume().catch(() => {});
        } catch (_) {
            // O som é opcional; uma falha de áudio nunca deve impedir a venda.
        }
    }

    function confirmar() {
        try {
            if (!contexto || contexto.state !== 'running') return;
            const inicio = contexto.currentTime;
            [660, 880].forEach((frequencia, indice) => {
                const oscilador = contexto.createOscillator();
                const volume = contexto.createGain();
                const tempo = inicio + indice * 0.14;
                oscilador.type = 'sine';
                oscilador.frequency.value = frequencia;
                volume.gain.setValueAtTime(0.0001, tempo);
                volume.gain.exponentialRampToValueAtTime(0.1, tempo + 0.02);
                volume.gain.exponentialRampToValueAtTime(0.0001, tempo + 0.23);
                oscilador.connect(volume);
                volume.connect(contexto.destination);
                oscilador.start(tempo);
                oscilador.stop(tempo + 0.24);
            });
        } catch (_) {
            // A confirmação da compra continua mesmo sem suporte a áudio.
        }
    }

    document.addEventListener('pointerdown', preparar, {once: true});
    document.addEventListener('keydown', preparar, {once: true});
    window.somPagamento = {preparar, confirmar};
})();
