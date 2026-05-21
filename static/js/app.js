// Add some interactive effects
document.addEventListener('DOMContentLoaded', function() {
    const cards = document.querySelectorAll('.service-card');
    
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
        card.style.animation = 'fadeInUp 0.6s ease forwards';
    });
});

// Centralized click handler for service cards
function onServiceCardClick(event, url) {
    // If the click originated from an interactive element (edit button, action buttons, links, inputs), ignore
    const interactive = event.target.closest && event.target.closest('.edit-service-btn, .item-actions, a, button, input, select, textarea');
    if (interactive) return;
    // Otherwise open the service URL
    if (url) {
        window.open(url, '_blank');
    }
}

// Helper to read service JSON from data attribute and call openEditServiceModal
function openEditServiceModalFromDataset(event, el) {
    if (!el) return;
    event && event.stopPropagation && event.stopPropagation();
    try {
        const svcJson = el.getAttribute('data-service');
        const svc = svcJson ? JSON.parse(svcJson) : {};
        // Call existing settings handler
        if (typeof openEditServiceModal === 'function') {
            openEditServiceModal(event, svc);
        }
    } catch (err) {
        console.error('Failed to parse service JSON from data-service', err);
    }
}
