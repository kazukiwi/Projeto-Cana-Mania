(() => {
  if (window.__logoutConfirmInitialized) return;
  window.__logoutConfirmInitialized = true;

  const style = document.createElement("style");
  style.textContent = `
    .logout-dialog-backdrop { position: fixed; inset: 0; z-index: 10000; display: grid; place-items: center; padding: 24px; background: rgba(9, 20, 92, .56); backdrop-filter: blur(5px); opacity: 0; visibility: hidden; transition: opacity .2s ease, visibility .2s ease; }
    .logout-dialog-backdrop.is-open { opacity: 1; visibility: visible; }
    .logout-dialog { width: min(100%, 420px); overflow: hidden; border: 1px solid rgba(255,255,255,.65); border-radius: 22px; background: #fff; box-shadow: 0 24px 70px rgba(5, 10, 52, .34); transform: translateY(12px) scale(.98); transition: transform .2s ease; }
    .logout-dialog-backdrop.is-open .logout-dialog { transform: translateY(0) scale(1); }
    .logout-dialog__content { padding: 32px 32px 26px; text-align: center; }
    .logout-dialog__icon { display: grid; width: 58px; height: 58px; margin: 0 auto 18px; place-items: center; border-radius: 50%; background: #fff1f2; color: #dc2626; font-size: 25px; }
    .logout-dialog h2 { margin: 0; color: #09145c; font-size: 24px; }
    .logout-dialog p { margin: 10px 0 0; color: #596080; line-height: 1.55; }
    .logout-dialog__actions { display: flex; gap: 12px; padding: 18px 24px; background: #f6f7ff; }
    .logout-dialog button { flex: 1; min-height: 44px; border: 0; border-radius: 10px; padding: 10px 16px; font: inherit; font-weight: 700; cursor: pointer; }
    .logout-dialog__cancel { background: #e7e9f7; color: #27316b; }
    .logout-dialog__confirm { background: #dc2626; color: #fff; box-shadow: 0 6px 14px rgba(220,38,38,.25); }
    .logout-dialog__cancel:hover { background: #d8dced; }
    .logout-dialog__confirm:hover { background: #b91c1c; }
    @media (max-width: 460px) { .logout-dialog__content { padding: 28px 22px 22px; } .logout-dialog__actions { padding: 14px; } }
  `;
  document.head.appendChild(style);

  const dialog = document.createElement("div");
  dialog.className = "logout-dialog-backdrop";
  dialog.setAttribute("aria-hidden", "true");
  dialog.innerHTML = `
    <section class="logout-dialog" role="dialog" aria-modal="true" aria-labelledby="logout-dialog-title">
      <div class="logout-dialog__content">
        <div class="logout-dialog__icon" aria-hidden="true">↪</div>
        <h2 id="logout-dialog-title">Sair da conta?</h2>
        <p>Você precisará informar seu e-mail e senha para entrar novamente.</p>
      </div>
      <div class="logout-dialog__actions">
        <button class="logout-dialog__cancel" type="button">Cancelar</button>
        <button class="logout-dialog__confirm" type="button">Sair da conta</button>
      </div>
    </section>`;
  document.body.appendChild(dialog);

  let logoutUrl = "/auth/logout";
  let trigger = null;
  const cancelButton = dialog.querySelector(".logout-dialog__cancel");
  const confirmButton = dialog.querySelector(".logout-dialog__confirm");

  function closeDialog() {
    dialog.classList.remove("is-open");
    dialog.setAttribute("aria-hidden", "true");
    trigger?.focus();
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-logout-confirm]");
    if (!link) return;
    event.preventDefault();
    logoutUrl = link.href;
    trigger = link;
    dialog.classList.add("is-open");
    dialog.setAttribute("aria-hidden", "false");
    cancelButton.focus();
  });

  cancelButton.addEventListener("click", closeDialog);
  confirmButton.addEventListener("click", () => { window.location.assign(logoutUrl); });
  dialog.addEventListener("click", (event) => { if (event.target === dialog) closeDialog(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && dialog.classList.contains("is-open")) closeDialog(); });
})();
