// static/rdv/js/admin/rdvs/rdvs.js

/**
 * initRdvTable()
 * – Recherche en live, filtre statut, pagination, confirmation suppression.
 */
function initRdvTable() {
  console.log('🔄 initRdvTable');

  const container    = document.getElementById('rdv-table-container');
  const searchInput  = document.getElementById('rdv-search-input');
  const statusSelect = document.getElementById('rdv-status-select');
  if (!container || !searchInput || !statusSelect) return;

  const baseUrl = container.dataset.url;
  let debounceTimer;

  function debounce(fn, delay = 300) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
  }

  // Fetch & replace table fragment
  function fetchTable(params = {}) {
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('table-only', '1');
    Object.entries(params).forEach(([k, v]) => {
      v ? url.searchParams.set(k, v) : url.searchParams.delete(k);
    });
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(r => r.ok ? r.text() : Promise.reject(r.statusText))
      .then(html => {
        container.innerHTML = html;
        bindTableEvents();
      })
      .catch(console.error);
  }
  window.fetchTable = fetchTable;

  // Lie pagination & suppression dans le fragment
  function bindTableEvents() {
    container.querySelectorAll('.pagination a').forEach(link => {
      link.onclick = null;
      link.addEventListener('click', e => {
        e.preventDefault();
        const page   = link.dataset.page || new URL(link.href).searchParams.get('page');
        fetchTable({
          search: searchInput.value,
          status: statusSelect.value,
          page
        });
      });
    });
    container.querySelectorAll('.action-btn-delete').forEach(link => {
      link.onclick = null;
      link.addEventListener('click', e => {
        e.preventDefault();
        if (confirm('Supprimer ce rendez‑vous ?')) {
          window.location.href = link.href;
        }
      });
    });
  }

  // Recherche live
  searchInput.oninput = null;
  searchInput.addEventListener('input', () => {
    debounce(() => fetchTable({
      search: searchInput.value,
      status: statusSelect.value
    }));
  });

  // Filtre statut
  statusSelect.onchange = null;
  statusSelect.addEventListener('change', () => {
    fetchTable({
      search: searchInput.value,
      status: statusSelect.value
    });
  });

  // gestion navigation back/forward
  function handlePopState() {
    if (!document.body.contains(container)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    fetchTable(params);
  }
  window.removeEventListener('popstate', handlePopState);
  window.addEventListener('popstate', handlePopState);

  // première attache
  bindTableEvents();
}

// Expose pour base.js
window.initRdvTable = initRdvTable;
