(() => {
    const form = document.querySelector('.canamania-login .login-card');
    const orb = document.querySelector('.login-orb');
    if (!form || !orb || !window.fetch || !window.AbortController) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let lastPulse = -Infinity;
    let submitting = false;
    let glowTimer;
    const pulse = () => {
        if (submitting) return;
        const now = performance.now();
        if (now - lastPulse < 500) return;
        lastPulse = now;
        orb.classList.add('is-sensing');
        clearTimeout(glowTimer);
        glowTimer = setTimeout(() => orb.classList.remove('is-sensing'), 650);
        const wave = document.createElement('span');
        wave.className = 'login-orb-wave';
        orb.append(wave);
        wave.addEventListener('animationend', () => wave.remove(), { once: true });
    };
    document.addEventListener('pointermove', pulse, { passive: true });
    document.addEventListener('pointerdown', pulse, { passive: true });
    document.addEventListener('focusin', pulse);
    document.addEventListener('input', pulse);
    document.addEventListener('keydown', pulse);
    document.addEventListener('scroll', pulse, { passive: true });

    const feedback = () => {
        let node = form.querySelector('.login-feedback--error');
        if (!node) {
            node = document.createElement('p');
            node.className = 'login-feedback login-feedback--error';
            form.querySelector('button[type="submit"]').before(node);
        }
        node.setAttribute('role', 'alert');
        return node;
    };

    const enter = async (destination) => {
        const rect = orb.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const radius = Math.max(...[
            [0, 0], [innerWidth, 0], [0, innerHeight], [innerWidth, innerHeight]
        ].map(([cx, cy]) => Math.hypot(cx - x, cy - y)));
        clearTimeout(glowTimer);
        orb.classList.remove('is-sensing');
        orb.querySelectorAll('.login-orb-wave').forEach(wave => wave.remove());
        const cover = orb;
        cover.classList.add('login-transition');
        Object.assign(cover.style, {
            left: `${rect.left}px`, top: `${rect.top}px`, right: 'auto', bottom: 'auto',
            width: `${rect.width}px`, height: `${rect.height}px`
        });
        document.body.append(cover);
        document.body.classList.add('is-entering');
        const expanded = `scale(${radius / (rect.width / 2) + 0.2})`;
        const welcome = document.querySelector('.login-welcome');
        const expansionDuration = reducedMotion.matches ? 240 : 1050;
        let expansion;
        if (cover.animate) {
            const frames = reducedMotion.matches
                ? [{ transform: expanded, opacity: 0 }, { transform: expanded, opacity: 1 }]
                : [{ transform: 'scale(1)' }, { transform: expanded }];
            expansion = cover.animate(frames, {
                duration: expansionDuration,
                easing: 'cubic-bezier(.55,0,.2,1)', fill: 'forwards'
            });
        } else {
            cover.style.transform = expanded;
        }
        // Show the complete wordmark after the pink background fills the screen.
        if (expansion) await expansion.finished.catch(() => {});
        if (welcome) {
            welcome.hidden = false;
            welcome.focus({ preventScroll: true });
            if (welcome.animate) {
                const reveal = welcome.animate([
                    { opacity: 0, transform: reducedMotion.matches ? 'none' : 'translateY(12px)' },
                    { opacity: 1, transform: 'translateY(0)' }
                ], { duration: reducedMotion.matches ? 180 : 520, easing: 'ease-out', fill: 'forwards' });
                await reveal.finished.catch(() => {});
            } else {
                welcome.style.opacity = '1';
            }
        }
        await new Promise(resolve => setTimeout(resolve, reducedMotion.matches ? 400 : 2000));
        // The welcome has already confirmed access; avoid repeating the dashboard notice.
        const nextPage = new URL(destination);
        nextPage.searchParams.delete('login');
        window.location.assign(nextPage.href);
    };

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (submitting) return;
        submitting = true;
        const button = form.querySelector('button[type="submit"]');
        const original = button.innerHTML;
        button.disabled = true;
        button.textContent = 'Entrando\u2026';
        form.setAttribute('aria-busy', 'true');
        const previousError = form.querySelector('.login-feedback--error');
        if (previousError) previousError.remove();
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 20000);
        let success = false;
        try {
            const response = await fetch(form.action, {
                method: 'POST', body: new URLSearchParams(new FormData(form)),
                credentials: 'same-origin', signal: controller.signal
            });
            const destination = new URL(response.url);
            if (response.ok && response.redirected && destination.origin === location.origin &&
                destination.searchParams.get('login') === 'ok') {
                clearTimeout(timeout);
                await enter(destination.href);
                success = true;
                return;
            }
            const html = new DOMParser().parseFromString(await response.text(), 'text/html');
            const error = html.querySelector('.login-feedback--error');
            feedback().textContent = error?.textContent.trim() || 'N\u00e3o foi poss\u00edvel entrar agora. Tente novamente.';
        } catch (error) {
            feedback().textContent = error.name === 'AbortError'
                ? 'A conex\u00e3o demorou demais. Tente novamente.'
                : 'N\u00e3o foi poss\u00edvel conectar. Verifique sua conex\u00e3o e tente novamente.';
        } finally {
            clearTimeout(timeout);
            if (!success) {
                submitting = false;
                button.disabled = false;
                button.innerHTML = original;
                form.removeAttribute('aria-busy');
            }
        }
    });
})();
