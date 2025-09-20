// static/rdv/js/doctor/dispo.js
// Version inspirée de users.js : filtres (type, jour, date) + pagination + polling

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

function initDispoTable() {
  console.log('🔄 initDispoTable');

  const container   = document.getElementById('dispo-table-container');
  const typeSelect  = document.getElementById('type-select');
  const jourSelect  = document.getElementById('jour-select');
  // prefer explicit date input id; fallback to class
  const dateInput   = document.getElementById('date-input') || document.querySelector('.date-input');

  if (!container) return;

  const baseAjax = container.dataset.ajaxUrl || container.dataset.url || container.dataset.base;
  if (!baseAjax) return;

  let debounceTimer;

  function debounce(fn, delay = 300) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
  }

  function readFiltersFromDom() {
    return {
      type:  (typeSelect && typeSelect.value) ? typeSelect.value : '',
      jour:  (jourSelect && jourSelect.value) ? jourSelect.value : '',
      date:  (dateInput && dateInput.value) ? dateInput.value : ''
    };
  }

  function applyTypeUx() {
    const t = typeSelect ? typeSelect.value : '';
    if (!typeSelect) return;
    if (t === 'ponctuel') {
      if (jourSelect) { jourSelect.value = ''; jourSelect.disabled = true; }
      if (dateInput)  { dateInput.disabled = false; }
    } else if (t === 'hebdomadaire') {
      if (dateInput) { dateInput.value = ''; dateInput.disabled = true; }
      if (jourSelect) { jourSelect.disabled = false; }
    } else {
      if (jourSelect) { jourSelect.disabled = false; }
      if (dateInput)  { dateInput.disabled = false; }
    }
  }

  // fetch table fragment (table-only=1)
  function fetchTable(params = {}) {
    const url = new URL(baseAjax, window.location.origin);
    url.searchParams.set('table-only', '1');

    // merge DOM filters + explicit params (params override)
    const filters = readFiltersFromDom();
    const final = Object.assign({}, filters, params);

    // normalization: if type=ponctuel -> ignore jour ; type=hebdomadaire -> ignore date
    if (final.type === 'ponctuel') delete final.jour;
    if (final.type === 'hebdomadaire') delete final.date;

    Object.entries(final).forEach(([k, v]) => {
      if (v || v === 0) url.searchParams.set(k, v);
      else url.searchParams.delete(k);
    });

    fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(r => r.ok ? r.text() : Promise.reject(r.statusText))
      .then(html => {
        container.innerHTML = html;
        // after replacement, bind events inside new table
        bindTableEvents();
        // ensure UX: filters may have been re-rendered by server-side; re-apply UX and rebind filter controls
        applyTypeUx();
      })
      .catch(err => {
        console.error('fetchDispoTable error:', err);
      });
  }

  // Expose for polling / other scripts
  window.fetchDispoTable = fetchTable;

  function bindTableEvents() {
    // Guard: prevent multiple bindings on same container
    // We'll still rebind controls each time (idempotent)
    // DELETE buttons
    container.querySelectorAll('.action-btn-delete').forEach(btn => {
      // neutralize potential inline onclick
      try { btn.onclick = null; } catch (e) {}
      // remove existing named listener by dataset flag approach is harder; use addEventListener but ensure not duplicated:
      if (btn.dataset.boundDelete === '1') return;
      btn.dataset.boundDelete = '1';
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        if (btn.dataset.busy === '1') return;
        if (!confirm('Supprimer ce créneau ?')) return;
        btn.dataset.busy = '1';
        try {
          const url = btn.dataset.deleteUrl || btn.getAttribute('href');
          const res = await fetch(url, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'X-Requested-With': 'XMLHttpRequest'
            }
          });
          const json = await res.json().catch(() => ({}));
          if (json.success || json.status === 'ok') {
            const row = btn.closest('tr');
            if (row) row.remove();
          } else {
            alert(json.message || 'Erreur lors de la suppression');
          }
        } catch (err) {
          console.error('delete error:', err);
          alert('Impossible de supprimer (erreur réseau)');
        } finally {
          delete btn.dataset.busy;
        }
      });
    });

    // Pagination links (delegated within container)
    // We can clear previous delegated listener by using dataset flag on container
    if (container.dataset.boundPagination !== '1') {
      container.dataset.boundPagination = '1';
      container.addEventListener('click', function (e) {
        const pageLink = e.target.closest('.pagination a[data-page]');
        if (pageLink) {
          e.preventDefault();
          const page = pageLink.dataset.page;
          fetchTable({ page });
        }
      });
    }

    // If there are inline forms with data-ajax="1", bind them (they can be in the table)
    container.querySelectorAll('form[data-ajax="1"]').forEach(f => {
      // use closest container as the form's container
      const c = f.closest('[data-ajax-container]') || f.parentElement;
      if (typeof bindDispoForm === 'function') {
        try { bindDispoForm(c || f); } catch (e) { /* ignore */ }
      }
    });
  }

  // Bind filters UI controls (debounced)
  applyTypeUx();

  if (typeSelect) {
    try { typeSelect.onchange = null; } catch (e) {}
    if (typeSelect.dataset.bound !== '1') {
      typeSelect.dataset.bound = '1';
      typeSelect.addEventListener('change', () => {
        applyTypeUx();
        debounce(() => fetchTable({ page: 1 }), 200);
      });
    }
  }

  if (jourSelect) {
    try { jourSelect.onchange = null; } catch (e) {}
    if (jourSelect.dataset.bound !== '1') {
      jourSelect.dataset.bound = '1';
      jourSelect.addEventListener('change', () => {
        debounce(() => fetchTable({ page: 1 }), 200);
      });
    }
  }

  if (dateInput) {
    try { dateInput.onchange = null; } catch (e) {}
    if (dateInput.dataset.bound !== '1') {
      dateInput.dataset.bound = '1';
      dateInput.addEventListener('change', () => {
        debounce(() => fetchTable({ page: 1 }), 200);
      });
    }
  }

  // handle popstate: if user navigates back/forward we reload the table params from URL
  function handlePopState() {
    if (!document.body.contains(container)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    // map URL params to fetchTable (we don't push state on filter changes, so this is mostly for completeness)
    fetchTable(params);
  }
  window.removeEventListener('popstate', handlePopState);
  window.addEventListener('popstate', handlePopState);

  // initial bind & maybe initial fetch if table area empty
  bindTableEvents();
  if (!container.querySelector('tbody')) {
    fetchTable({ page: 1 });
  }
}

function initDispoPolling() {
  console.log('🔄 initDispoPolling');

  const container = document.getElementById('dispo-table-container');
  if (!container) return;
  if (container.dataset.pollBound === '1') return;
  container.dataset.pollBound = '1';

  const ajaxUrl = container.dataset.url || window.location.href;
  let lastCount = null;

  async function poll() {
    try {
      const url = new URL(ajaxUrl, window.location.origin);
      url.searchParams.set('json', '1');
      if (lastCount !== null) url.searchParams.set('last_count', lastCount);
      const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      const data = await res.json().catch(() => null);
      if (data && data.changed) {
        lastCount = data.last_count;
        if (typeof window.fetchDispoTable === 'function') {
          // reload first page with current filters
          window.fetchDispoTable({ page: 1 });
        }
      }
    } catch (err) {
      // silent
    }
  }

  setInterval(poll, 5000);
}

// Auto-init on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  if (window.flatpickr) {
    try { flatpickr(".date-input", { dateFormat: "Y-m-d" }); } catch (e) { /* ignore */ }
  }

  document.querySelectorAll('form[data-ajax="1"]').forEach(node => {
    const container = node.closest('[data-ajax-container]') || node.parentElement;
    if (typeof bindDispoForm === 'function') {
      try { bindDispoForm(container || node); } catch (e) {}
    }
  });

  initDispoTable();
  initDispoPolling();
});

// Expose for debug
window.initDispoTable = initDispoTable;
window.initDispoPolling = initDispoPolling;
window.fetchDispoTable = window.fetchDispoTable || function(){ console.warn('fetchDispoTable not initialized yet'); };
