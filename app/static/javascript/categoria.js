/**
 * SISTEMA AAPM - GERENCIAMENTO DE USUÁRIOS
 * Scripts de comportamento da página de listagem
 */

document.addEventListener("DOMContentLoaded", function () {
    
    // 1. Inicializa os ícones do Lucide cadastrados via data-lucide="..."
    if (typeof lucide !== "undefined") {
        lucide.createIcons();
    } else {
        console.warn("A biblioteca Lucide não foi carregada corretamente.");
    }

    // 2. Confirmação de segurança antes de alterar o status de um usuário
    const formToggles = document.querySelectorAll('form[action*="/toggle-ativo"]');
    
    formToggles.forEach(form => {
        form.addEventListener("submit", function (event) {
            const button = form.querySelector(".btn-toggle");
            if (!button) return; // Proteção caso o botão não exista na árvore

            const isDeactivate = button.classList.contains("deactivate");
            
            // Encontra o nome do usuário na mesma linha da tabela para personalizar a mensagem
            const row = form.closest("tr");
            const userName = row ? row.querySelector("td").textContent.trim() : "este usuário";

            const mensagem = isDeactivate
                ? `Tem certeza que deseja DESATIVAR o acesso do usuário "${userName}"?`
                : `Deseja ATIVAR novamente o acesso do usuário "${userName}"?`;

            // Se o usuário clicar em "Cancelar", cancela o envio do formulário POST
            if (!confirm(mensagem)) {
                event.preventDefault();
            }
        });
    });

    // 3. Desaparecer com as caixas de alerta após 5 segundos de forma suave
    const alertBoxes = document.querySelectorAll(".alert-box");
    
    alertBoxes.forEach(alert => {
        setTimeout(() => {
            // Aplica a transição para opacidade e colapso de altura
            alert.style.transition = "opacity 0.4s ease, transform 0.4s ease, max-height 0.4s ease, margin 0.4s ease, padding 0.4s ease";
            alert.style.opacity = "0";
            alert.style.transform = "translateY(-10px)";
            
            // Força o colapso visual para evitar buracos brancos na tela
            alert.style.maxHeight = "0";
            alert.style.paddingTop = "0";
            alert.style.paddingBottom = "0";
            alert.style.marginTop = "0";
            alert.style.marginBottom = "0";
            alert.style.overflow = "hidden";

            // Remove definitivamente do HTML após a animação acabar
            setTimeout(() => {
                alert.remove();
            }, 400);
        }, 5000); // 5 segundos
    });
});