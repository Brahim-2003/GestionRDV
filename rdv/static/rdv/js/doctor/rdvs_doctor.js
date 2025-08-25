// static/rdv/js/doctor/rdvs_doctor.js
// Version finale : recherche par nom patient + filtre status + date + pagination + polling
// Inspiré de users.js / dispo.js — évite l'empilement d'event listeners.

(function () {
  'use strict';

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

  function initRdvsTable() {
    console.log('🔄 initRdvsTable');

    const container = document.getElementById('dispo-table-container'); // c'est le conteneur pour le tableau
    const searchInput = document.getElementById('search-input');
    const statusSelect = document.getElementById('status-select');
    const dateInput = document.getElementById('date-input') || document.querySelector('.date-input');

    if (!container) return;

    const baseUrl = container.dataset.ajaxUrl || container.dataset.url || container.dataset.base;
    if (!baseUrl) {
      console.warn('rdvs: base ajax url introuvable sur #dispo-table-container');
      return;
    }

    // debounce utility (single timer per init)
    let debounceTimer;
    function debounce(fn, delay = 300) {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(fn, delay);
    }

    // read current filters from DOM
    function readFilters() {
      return {
        search: (searchInput && searchInput.value) ? searchInput.value.trim() : '',
        status: (statusSelect && statusSelect.value) ? statusSelect.value : '',
        date: (dateInput && dateInput.value) ? dateInput.value : ''
      };
    }

    // fetch table fragment with provided params (merges with DOM filters)
    function fetchTable(params = {}) {
      const url = new URL(baseUrl, window.location.origin);
      url.searchParams.set('table-only', '1');

      // merge DOM filters then override with explicit params
      const filters = readFilters();
      const final = Object.assign({}, filters, params);

      // attach params to URL (only non-empty)
      Object.entries(final).forEach(([k, v]) => {
        if (v || v === 0) url.searchParams.set(k, v);
        else url.searchParams.delete(k);
      });

      fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(r => r.ok ? r.text() : Promise.reject(r.statusText))
        .then(html => {
          container.innerHTML = html;
          // after injecting new HTML, re-bind events on the table
          bindTableEvents();
        })
        .catch(err => {
          console.error('rdvs fetchTable error:', err);
        });
    }

    // expose for external use (polling)
    window.fetchRdvsTable = fetchTable;

    // bind interactive controls inside the table (delete, pagination, inline forms)
    function bindTableEvents() {
      // DELETE buttons: ensure idempotent binding
      container.querySelectorAll('.action-btn-delete').forEach(btn => {
        try { btn.onclick = null; } catch (e) {}
        if (btn.dataset.boundDelete === '1') return;
        btn.dataset.boundDelete = '1';

        btn.addEventListener('click', async (ev) => {
          ev.preventDefault();
          if (btn.dataset.busy === '1') return;
          if (!confirm('Supprimer ce rendez-vous ?')) return;
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
            if (json.status === 'success' || json.success === true || json.status === 'ok') {
              const row = btn.closest('tr');
              if (row) row.remove();
            } else {
              alert(json.message || 'Erreur lors de la suppression');
            }
          } catch (err) {
            console.error('rdvs delete error:', err);
            alert('Impossible de supprimer (erreur réseau)');
          } finally {
            delete btn.dataset.busy;
          }
        });
      });

      // Pagination delegation (attach once on container)
      if (container.dataset.boundPagination !== '1') {
        container.dataset.boundPagination = '1';
        container.addEventListener('click', function (e) {
          const pageLink = e.target.closest('.pagination a[data-page]');
          if (!pageLink) return;
          e.preventDefault();
          const page = pageLink.dataset.page;
          // fetch new page preserving current filters
          fetchTable({ page });
        });
      }

      // Bind any inline AJAX forms in the injected fragment
      container.querySelectorAll('form[data-ajax="1"]').forEach(f => {
        const c = f.closest('[data-ajax-container]') || f.parentElement;
        if (typeof bindDispoForm === 'function') {
          try { bindDispoForm(c || f); } catch (err) { /* ignore */ }
        }
      });
    }

    // Bind filter controls (search, status, date) — idempotent
    if (searchInput) {
      try { searchInput.oninput = null; } catch (e) {}
      if (searchInput.dataset.bound !== '1') {
        searchInput.dataset.bound = '1';
        searchInput.addEventListener('input', () => {
          debounce(() => fetchTable({ page: 1 }), 300);
        });
      }
    }

    if (statusSelect) {
      try { statusSelect.onchange = null; } catch (e) {}
      if (statusSelect.dataset.bound !== '1') {
        statusSelect.dataset.bound = '1';
        statusSelect.addEventListener('change', () => {
          fetchTable({ page: 1 });
        });
      }
    }

    if (dateInput) {
      try { dateInput.onchange = null; } catch (e) {}
      if (dateInput.dataset.bound !== '1') {
        dateInput.dataset.bound = '1';
        dateInput.addEventListener('change', () => {
          fetchTable({ page: 1 });
        });
      }
    }

    // handle back/forward: reload table with params from location.search
    function handlePopState() {
      if (!document.body.contains(container)) return;
      const params = Object.fromEntries(new URLSearchParams(location.search));
      fetchTable(params);
    }
    window.removeEventListener('popstate', handlePopState);
    window.addEventListener('popstate', handlePopState);

    // initial binding + initial fetch if necessary
    bindTableEvents();
    if (!container.querySelector('tbody')) {
      // initial load (first page)
      fetchTable({ page: 1 });
    }
  }

  // optional polling — only if container.dataset.ajaxUrl (or data-url) supports a json endpoint;
  // it will request ?json=1 and expect {changed: true, last_count: N}
  function initRdvsPolling() {
    console.log('🔄 initRdvsPolling');
    const container = document.getElementById('dispo-table-container');
    if (!container) return;
    if (container.dataset.pollBound === '1') return;
    container.dataset.pollBound = '1';

    const ajaxUrl = container.dataset.url || container.dataset.ajaxUrl || window.location.href;
    let lastCount = null;

    async function poll() {
      try {
        const url = new URL(ajaxUrl, window.location.origin);
        url.searchParams.set('json', '1');
        if (lastCount !== null) url.searchParams.set('last_count', lastCount);
        const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        const data = await res.json().catch(() => null);
        if (data && data.changed) {
          lastCount = data.last_count || null;
          if (typeof window.fetchRdvsTable === 'function') {
            window.fetchRdvsTable({ page: 1 });
          }
        }
      } catch (err) {
        // silent
        // console.error('rdvs poll error', err);
      }
    }

    setInterval(poll, 5000);
  }

  // Auto-init when DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    // init any datepicker if present
    if (window.flatpickr) {
      try { flatpickr('.date-input', { dateFormat: 'Y-m-d' }); } catch (e) {}
    }

    // Bind any inline ajax forms already present
    document.querySelectorAll('form[data-ajax="1"]').forEach(node => {
      const c = node.closest('[data-ajax-container]') || node.parentElement;
      if (typeof bindDispoForm === 'function') {
        try { bindDispoForm(c || node); } catch (e) {}
      }
    });

    initRdvsTable();
    initRdvsPolling();
  });

  // Expose to global for runAllInits / debugging
  window.initRdvsTable = initRdvsTable;
  window.initRdvsPolling = initRdvsPolling;
  window.fetchRdvsTable = window.fetchRdvsTable || function () { console.warn('fetchRdvsTable not initialized yet'); };
})();
