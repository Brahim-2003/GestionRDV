// dashboard_admin.js

// Mets à jour les statistiques via l'API
function updateDashboard() {
    fetch('{% url "rdv : api_dashboard_stats" %}')
        .then(resp => resp.json())
        .then(data => {
            document.querySelectorAll('.stat-card').forEach(card => {
                const key = card.dataset.statKey;
                const valueEl = card.querySelector('.stat-value');
                if (data[key] !== undefined) {
                    valueEl.textContent = data[key];
                }
            });
        })
        .catch(err => console.error('Erreur API stats:', err));
}

// Initialise les animations de cards
function setupAnimations() {
    const cards = document.querySelectorAll('.card');
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.2 });
    cards.forEach(card => observer.observe(card));
}

// Définit les événements spécifiques (ex : boutons refresh)
function setupEvents() {
    document.querySelectorAll('.refresh-btn').forEach(btn => {
        btn.addEventListener('click', updateDashboard);
    });
}

// Fonction principale d'initialisation
function initDashboard() {
    console.log('initDashboard');
    updateDashboard();
    setupAnimations();
    setupEvents();
}

// Pour que base.js puisse la trouver
window.initDashboard = initDashboard;

// Exécution initiale si la page n'est pas chargée en AJAX
document.addEventListener('DOMContentLoaded', initDashboard);
