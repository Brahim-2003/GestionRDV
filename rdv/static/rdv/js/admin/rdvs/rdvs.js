// static/rdv/js/admin/rdvs/rdvs_admin.js
// Comportement aligné sur rdvs_doctor.js : filtres (search/status/date) + pagination + suppression

console.log("rdvs_admin.js chargé");

// ---------- utils ----------
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    document.cookie.split(';').forEach(cookie => {
      cookie = cookie.trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.slice(name.length + 1));
      }
    });
  }
  return cookieValue;
}

function showSimpleError(msg) {
  console.error(msg);
  // possible: afficher un toast/alerte si tu veux
}

// ---------- helpers filtres ----------
function readRdvFiltersFromDom() {
  const searchEl = document.getElementById('search-input');
  const statusEl = document.getElementById('status-select');
  const dateEl = document.getElementById('date-input');

  return {
    search: (searchEl && searchEl.value) ? searchEl.value.trim() : '',
    status: (statusEl && statusEl.value) ? statusEl.value : '',
    date: (dateEl && dateEl.value) ? dateEl.value : ''
  };
}

// small util debounce factory
function debounceFactory(delay = 300) {
  let t = null;
  return function(fn) {
    clearTimeout(t);
    t = setTimeout(fn, delay);
  };
}

// ---------- Table handling (fetch + bind) ----------
function initRdvTable() {
  console.log('🔄 initRdvTable (admin)');

  const container = document.getElementById('rdv-table-container');
  if (!container) return;
  // use dataset.bound to avoid double-binding across multiple init calls
  if (container.dataset.bound === "1") {
    // still re-bind events inside after content replacement if needed
    // but we avoid re-initializing repeated global listeners
  }
  const searchInput = document.getElementById('search-input');
  const statusSelect = document.getElementById('status-select');
  const dateInput = document.getElementById('date-input');
  const baseAjax = container.dataset.ajaxUrl || container.dataset.url || container.dataset.base;

  if (!baseAjax) {
    console.warn('rdv-table-container missing data-url / data-ajax-url');
  }

  const debounce = debounceFactory(300);

  async function fetchRdvTable(params = {}, pushState = false) {
    try {
      if (!baseAjax) return;
      const url = new URL(baseAjax, window.location.origin);
      url.searchParams.set('table-only', '1');

      // merge dom filters with explicit params
      const dom = readRdvFiltersFromDom();
      const final = Object.assign({}, dom, params);

      // normalize: if empty string => remove param
      Object.entries(final).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
        else url.searchParams.delete(k);
      });

      const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const html = await res.text();
      container.innerHTML = html;

      // After injection, bind events inside fragment
      bindTableEvents();

      // If needed, scroll to top of container (optional)
      // container.scrollIntoView({ behavior: 'smooth', block: 'start' });

      // push history (but keep original URL path/query stable per your request)
      if (pushState) {
        // we don't want to change visible URL for filters per your instructions,
        // but if you want pushState for back button, use state-only:
        history.pushState({ virtual: true }, '', window.location.href);
      }
    } catch (err) {
      console.error('fetchRdvTable error:', err);
      showSimpleError('Erreur lors du chargement des rendez-vous.');
    }
  }
  window.fetchRdvTable = fetchRdvTable;

  // bind events inside the container (pagination, delete buttons, etc.)
  function bindTableEvents() {
    // pagination links
    container.querySelectorAll('.pagination a[data-page]').forEach(link => {
      link.onclick = null;
      link.addEventListener('click', e => {
        e.preventDefault();
        const page = link.dataset.page || new URL(link.href).searchParams.get('page');
        // call fetch with current filters + page
        fetchRdvTable({ page }, true);
      });
    });

    // delete buttons: try AJAX if data-delete-url provided, else fallback to normal navigation
    container.querySelectorAll('.action-btn-delete').forEach(btn => {
      btn.onclick = null;
      btn.addEventListener('click', async e => {
        e.preventDefault();
        const ask = btn.dataset.confirm || 'Supprimer ce rendez-vous ?';
        if (!confirm(ask)) return;

        const url = btn.dataset.deleteUrl || btn.getAttribute('href');
        if (!url) return;

        // Try AJAX deletion
        try {
          const res = await fetch(url, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'X-Requested-With': 'XMLHttpRequest'
            }
          });
          // if server returns JSON with status, handle it
          const ct = (res.headers.get('content-type') || '');
          if (ct.includes('application/json')) {
            const json = await res.json().catch(() => ({}));
            if (res.ok && (json.status === 'ok' || json.status === 'success')) {
              // remove row
              const tr = btn.closest('tr');
              if (tr) tr.remove();
            } else {
              alert(json.message || 'Erreur lors de la suppression');
            }
            return;
          }
          // otherwise fallback: redirect (server may respond with redirect)
          if (res.ok && (res.status === 200 || res.status === 204)) {
            const tr = btn.closest('tr');
            if (tr) tr.remove();
            return;
          }
          // fallback to navigation
          window.location.href = url;
        } catch (err) {
          console.error('delete error', err);
          // fallback to navigation if AJAX fails
          window.location.href = url;
        }
      });
    });

    // re-bind any inline AJAX forms inside the container (if any)
    container.querySelectorAll('form[data-ajax="1"]').forEach(form => {
      // use existing global bind if available
      if (typeof window.bindDispoForm === 'function') {
        const wrapper = form.closest('[data-ajax-container]') || form.parentElement;
        window.bindDispoForm(wrapper || form);
      }
    });
  }

  // ---- Filters: bind events (debounced) ----
  // search input
  if (searchInput) {
    searchInput.oninput = null;
    searchInput.addEventListener('input', () => {
      debounce(() => fetchRdvTable({ page: 1 }));
    });
  }

  // status select
  if (statusSelect) {
    statusSelect.onchange = null;
    statusSelect.addEventListener('change', () => {
      fetchRdvTable({ page: 1 });
    });
  }

  // date input
  if (dateInput) {
    dateInput.onchange = null;
    dateInput.addEventListener('change', () => {
      fetchRdvTable({ page: 1 });
    });
  }

  // back/forward: if user navigates history, reload table with params from URL
  function handlePopState() {
    if (!document.body.contains(container)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    fetchRdvTable(params, false);
  }
  window.removeEventListener('popstate', handlePopState);
  window.addEventListener('popstate', handlePopState);

  // mark bound to avoid double-bind when initRdvTable called multiple times
  container.dataset.bound = "1";

  // initial binding on current content
  bindTableEvents();

  // initial load: if table empty, request initial fragment with current filters
  if (!container.querySelector('tbody')) {
    const filters = readRdvFiltersFromDom();
    fetchRdvTable({ search: filters.search, status: filters.status, date: filters.date }, false);
  }
}

// polling (optional)
function initRdvPolling() {
  console.log('🔄 initRdvPolling (admin)');

  const container = document.getElementById('rdv-table-container');
  if (!container) return;
  if (container.dataset.pollBound === "1") return;
  container.dataset.pollBound = "1";

  const baseUrl = container.dataset.url || window.location.href;
  let lastCount = null;

  const poll = async () => {
    try {
      const url = new URL(baseUrl, window.location.origin);
      url.searchParams.set('json', '1');
      if (lastCount !== null) url.searchParams.set('last_count', lastCount);
      const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await res.json().catch(() => null);
      if (data && data.changed) {
        lastCount = data.last_count;
        // refresh current page to page 1 (or keep page param logic if desired)
        if (typeof window.fetchRdvTable === 'function') {
          window.fetchRdvTable({ page: 1 });
        }
      }
    } catch (err) {
      // silent
      console.warn('rdv polling error', err);
    }
  };

  setInterval(poll, 5000);
}

// ---------- INIT exposure ----------
window.initRdvTable = initRdvTable;
window.initRdvPolling = initRdvPolling;
