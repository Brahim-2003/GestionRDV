// static/rdv/js/admin/menu.js

// Seule responsabilité : déclencher la navigation AJAX
document.querySelectorAll('.nav-tab').forEach(link => {
    link.onclick = function(e) {
        e.preventDefault();
        if (typeof window.loadContent === 'function') {
            window.loadContent(this.href);
        }
    };
});

// Fonction pour basculer la sidebar sur mobile
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    sidebar.classList.toggle('open');
    overlay.classList.toggle('active');
}

// Gestion responsive
window.addEventListener('resize', function() {
    if (window.innerWidth > 768) {
        document.getElementById('sidebar')?.classList.remove('open');
        document.querySelector('.sidebar-overlay')?.classList.remove('active');
    }
});

// Confirmation avant déconnexion
document.getElementById('logout-link')?.addEventListener('click', function(e) {
    e.preventDefault();
    if (confirm("Êtes-vous sûr de vouloir vous déconnecter ?")) {
        window.location.href = this.href;
    }
});
