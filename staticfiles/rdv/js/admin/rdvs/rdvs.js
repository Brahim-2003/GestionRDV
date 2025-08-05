// static/rdv/js/admin/rdvs/rdvs.js

/**
 * initRdvTable()
 * – Initialisation de la recherche, du filtre statut, de la pagination et
 *   de la confirmation de suppression sur la page RDV.
 */
function initRdvTable() {
  console.log('🔄 initRdvTable');

  const container    = document.getElementById('rdv-table-container');
  const searchInput  = document.getElementById('rdv-search-input');
  const statusSelect = document.getElementById('rdv-status-select');
  const resetBtn     = document.getElementById('rdv-reset-btn');

  if (!container || !searchInput || !statusSelect || !resetBtn) return;

  const baseUrl = container.dataset.url;

  let debounceTimer;
  function debounce(fn, delay = 300) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
  }

  function fetchTable(params = {}) {
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('table-only', '1');
    Object.entries(params).forEach(([k,v]) => {
      v ? url.searchParams.set(k,v) : url.searchParams.delete(k);
    });
    fetch(url, { headers: {'X-Requested-With':'XMLHttpRequest'} })
      .then(r => r.ok ? r.text() : Promise.reject(r.statusText))
      .then(html => {
        container.innerHTML = html;
        bindTableEvents();
      })
      .catch(console.error);
  }
  window.fetchTable = fetchTable;

  function bindTableEvents() {
    container.querySelectorAll('.pagination a').forEach(link => {
      link.onclick = null;
      link.addEventListener('click', e => {
        e.preventDefault();
        const page   = link.dataset.page || new URL(link.href).searchParams.get('page');
        const search = searchInput.value;
        const status = statusSelect.value;
        fetchTable({ search, status, page });
      });
    });
    container.querySelectorAll('.action-btn-delete').forEach(btn => {
      btn.onclick = null;
      btn.addEventListener('click', e => {
        e.preventDefault();
        if (confirm('Supprimer ce rendez‑vous ?')) {
          window.location.href = btn.href;
        }
      });
    });
  }

  searchInput.oninput = null;
  searchInput.addEventListener('input', () => {
    debounce(() => fetchTable({ search: searchInput.value, status: statusSelect.value }));
  });

  statusSelect.onchange = null;
  statusSelect.addEventListener('change', () => {
    fetchTable({ search: searchInput.value, status: statusSelect.value });
  });

  resetBtn.onclick = null;
  resetBtn.addEventListener('click', e => {
    e.preventDefault();
    searchInput.value = '';
    statusSelect.value = '';
    fetchTable({});
  });

  // history back/forward
  window.removeEventListener('popstate', handlePopState);
  function handlePopState() {
    if (!document.body.contains(container)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    fetchTable(params);
  }
  window.addEventListener('popstate', handlePopState);

  bindTableEvents();
}

// on expose pour base.js
window.initRdvTable = initRdvTable;
