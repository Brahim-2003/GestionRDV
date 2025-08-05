// static/rdv/js/admin/users/table.js

/**
 * initUsersTable()
 * – Initialise la pagination, la recherche, les filtres et le reset
 *   pour la page Utilisateurs.
 * – À appeler à chaque injection AJAX (navigation) ou au chargement complet.
 */
function initUsersTable() {
  const tableContainer = document.getElementById('users-table-container');
  const searchInput     = document.getElementById('search-input');
  const roleSelect      = document.getElementById('role-select');
  const resetBtn        = document.getElementById('reset-btn');

  // Si on n'est pas sur la page Utilisateurs, on quitte
  if (!tableContainer || !searchInput || !roleSelect || !resetBtn) {
    return;
  }

  const baseUrl = tableContainer.dataset.url;

  // Utility : debounce pour la recherche live
  let debounceTimer;
  function debounce(fn, delay = 300) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
  }

  /**
   * Recharge via AJAX le seul fragment <table> (table-only=1)
   * NE MODIFIE PAS l'URL du navigateur, pour éviter de bloquer en fragment au refresh.
   */
  function fetchTable(params = {}) {
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('table-only', '1');
    Object.entries(params).forEach(([key, value]) => {
      if (value) url.searchParams.set(key, value);
      else       url.searchParams.delete(key);
    });

    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(resp => resp.ok ? resp.text() : Promise.reject(resp.statusText))
      .then(html => {
        tableContainer.innerHTML = html;
        bindTableEvents();
      })
      .catch(err => console.error('Erreur AJAX Table:', err));
  }

  // Expose pour les autres modules (users.js reset déclenche fetchTable)
  window.fetchTable = fetchTable;

  /**
   * Lie les clics sur les liens de pagination
   */
  function bindTableEvents() {
    tableContainer.querySelectorAll('.pagination a').forEach(link => {
      link.onclick = null;
      link.addEventListener('click', e => {
        e.preventDefault();
        const page   = link.dataset.page || new URL(link.href).searchParams.get('page');
        const search = searchInput.value;
        const role   = roleSelect.value;
        fetchTable({ search, role, page });
      });
    });

    // Re-bind suppression utilisateur (icônes 🗑️)
    tableContainer.querySelectorAll('.action-btn-delete').forEach(btn => {
      btn.onclick = null;
      btn.addEventListener('click', e => {
        e.preventDefault();
        if (confirm('Confirmer la suppression de cet utilisateur ?')) {
          window.location.href = btn.href;
        }
      });
    });
  }

  /**
   * Lie la recherche et le filtre rôle
   */
  function bindFilterEvents() {
    // recherche live
    searchInput.oninput = null;
    searchInput.addEventListener('input', () => {
      debounce(() => {
        fetchTable({ search: searchInput.value, role: roleSelect.value });
      });
    });

    // changement de rôle
    roleSelect.onchange = null;
    roleSelect.addEventListener('change', () => {
      fetchTable({ search: searchInput.value, role: roleSelect.value });
    });

    // reset total
    resetBtn.onclick = null;
    resetBtn.addEventListener('click', e => {
      e.preventDefault();
      searchInput.value = '';
      roleSelect.value  = '';
      fetchTable({});
    });
  }

  // Historique navigateur back/forward
  // Recharge le tableau en fonction des paramètres d'URL
  window.removeEventListener('popstate', handlePopState);
  function handlePopState() {
    // si table container n'existe plus, on ne fait rien
    if (!document.body.contains(tableContainer)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    fetchTable(params);
  }
  window.addEventListener('popstate', handlePopState);

  // Liaisons initiales
  bindFilterEvents();
  bindTableEvents();
}

// Expose pour base.js
window.initUsersTable = initUsersTable;
