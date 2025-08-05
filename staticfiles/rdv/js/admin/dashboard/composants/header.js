// ===============================
// Header JS – Notifications & Logout
// ===============================

// Déconnexion avec confirmation
function handleLogoutClick(event) {
    event.preventDefault(); // Bloque le href direct
    event.stopPropagation();

    if (confirm('Êtes-vous sûr de vouloir vous déconnecter ?')) {
        window.location.href = event.currentTarget.href;
    }
}

// Affiche/Cache le dropdown notifications
function handleNotificationToggle(event) {
    event.stopPropagation();
    const dropdown = document.getElementById('notificationDropdown');
    dropdown?.classList.toggle('show');
}

// Ferme le dropdown si clic en dehors
function closeDropdownOnClickOutside(event) {
    const dropdown = document.getElementById('notificationDropdown');
    const notifBtn = document.querySelector('.notification-btn');

    if (
        dropdown &&
        notifBtn &&
        !dropdown.contains(event.target) &&
        !notifBtn.contains(event.target)
    ) {
        dropdown.classList.remove('show');
    }
}

// Initialise les événements du header
function initHeader() {
    console.log('🔄 initHeader');

    const notifBtn = document.querySelector('.notification-btn');
    const logoutBtn = document.querySelector('.logout-btn');

    // Supprime d'abord les anciens listeners
    notifBtn?.removeEventListener('click', handleNotificationToggle);
    logoutBtn?.removeEventListener('click', handleLogoutClick);

    // Ré-attache proprement
    notifBtn?.addEventListener('click', handleNotificationToggle);
    logoutBtn?.addEventListener('click', handleLogoutClick);

    // Gestion clic en dehors
    document.removeEventListener('click', closeDropdownOnClickOutside);
    document.addEventListener('click', closeDropdownOnClickOutside);
}

// Rendre disponible globalement
window.initHeader = initHeader;

// Exécuter au chargement initial
document.addEventListener('DOMContentLoaded', initHeader);
