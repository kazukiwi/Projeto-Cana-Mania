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

    // 2. Desaparecer com as caixas de alerta após 5 segundos de forma suave
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
