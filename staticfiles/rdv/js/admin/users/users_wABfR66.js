// static/rdv/js/admin/users/users.js
// Version finale — recherche live + filtres role/active + pagination + suppression AJAX
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

  function initUsersTable() {
    console.log('🔄 initUsersTable');

    const container = document.getElementById('users-table-container');
    const searchInput = document.getElementById('search-input');
    const roleSelect = document.getElementById('role-select');
    const activeSelect = document.getElementById('active-select');

    if (!container) return;
    if (!searchInput || !roleSelect || !activeSelect) {
      console.warn('initUsersTable: éléments manquants (search/role/active). Abandon.');
      return;
    }

    const baseUrl = container.dataset.url;
    if (!baseUrl) {
      console.warn('initUsersTable: container.dataset.url manquant');
      return;
    }

    let debounceTimer = null;
    function debounce(fn, delay = 300) {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(fn, delay);
    }

    async function fetchTable(params = {}) {
      const url = new URL(baseUrl, window.location.origin);
      url.searchParams.set('table-only', '1');

      Object.entries(params).forEach(([k, v]) => {
        if (v || v === 0) url.searchParams.set(k, v);
        else url.searchParams.delete(k);
      });

      try {
        const res = await fetch(url.toString(), { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const html = await res.text();
        container.innerHTML = html;
        bindTableEvents();
        // dispatch event so other modules (modals, etc.) can react
        window.dispatchEvent(new CustomEvent('users:table:updated', { detail: { containerId: container.id } }));
        return html;
      } catch (err) {
        console.error('fetchTable error:', err);
      }
    }

    window.fetchTable = fetchTable;

    function bindTableEvents() {
      // DELETE buttons
      container.querySelectorAll('.action-btn-delete').forEach(link => {
        link.onclick = null;
        link.addEventListener('click', function (e) {
          e.preventDefault();
          if (!confirm('Confirmer la suppression de cet utilisateur ?')) return;

          const url = link.dataset.deleteUrl || link.getAttribute('href');
          const row = link.closest('tr');
          if (!url) { console.warn('delete: url manquante pour', link); return; }

          fetch(url, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'X-Requested-With': 'XMLHttpRequest'
            }
          })
          .then(res => {
            if (!res.ok) return res.json().then(j => Promise.reject(j));
            return res.json();
          })
          .then(data => {
            if (data && (data.status === 'success' || data.status === 'ok')) {
              if (row) row.remove();
            } else {
              alert(data && (data.message || data.error) ? (data.message || data.error) : 'Erreur lors de la suppression');
            }
          })
          .catch(err => {
            console.error('Delete error:', err);
            alert('Impossible de supprimer cet utilisateur (erreur réseau ou serveur).');
          });
        });
      });

      // Pagination links
      container.querySelectorAll('.pagination a[data-page]').forEach(a => {
        a.onclick = null;
        a.addEventListener('click', function (ev) {
          ev.preventDefault();
          const page = this.dataset.page;
          if (!page) return;
          const params = {
            page: page,
            search: searchInput.value || '',
            role: roleSelect.value || '',
            active: activeSelect.value || ''
          };
          fetchTable(params);
        });
      });

      // (Optional) re-bind other interactive elements if needed
    }

    // initial binding
    bindTableEvents();

    searchInput.oninput = null;
    searchInput.addEventListener('input', () => {
      debounce(() => {
        fetchTable({
          search: searchInput.value || '',
          role: roleSelect.value || '',
          active: activeSelect.value || '',
          page: 1
        });
      }, 250);
    });

    roleSelect.onchange = null;
    roleSelect.addEventListener('change', () => {
      fetchTable({
        search: searchInput.value || '',
        role: roleSelect.value || '',
        active: activeSelect.value || '',
        page: 1
      });
    });

    activeSelect.onchange = null;
    activeSelect.addEventListener('change', () => {
      fetchTable({
        search: searchInput.value || '',
        role: roleSelect.value || '',
        active: activeSelect.value || '',
        page: 1
      });
    });

    function handlePopState() {
      if (!document.body.contains(container)) return;
      const params = Object.fromEntries(new URLSearchParams(location.search));
      const p = {
        search: params.search || '',
        role: params.role || '',
        active: params.active || '',
        page: params.page || 1
      };
      fetchTable(p);
    }
    window.removeEventListener('popstate', handlePopState);
    window.addEventListener('popstate', handlePopState);
  }

  function initUsersPolling() {
    console.log('🔄 initUsersPolling');
    const container = document.getElementById('users-table-container');
    if (!container) return;
    const ajaxUrl = container.dataset.ajaxUrl;
    if (!ajaxUrl) return;
    let lastVersion = null;

    async function poll() {
      let url = ajaxUrl;
      if (lastVersion) url += `?last_version=${encodeURIComponent(lastVersion)}`;
      try {
        const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (data && data.changed) {
          lastVersion = data.last_version;
          const search = document.getElementById('search-input')?.value || '';
          const role = document.getElementById('role-select')?.value || '';
          const active = document.getElementById('active-select')?.value || '';
          if (typeof window.fetchTable === 'function') {
            window.fetchTable({ search, role, active, page: 1 });
          }
        }
      } catch (e) {
        console.error('Polling error:', e);
      }
    }

    if (container.dataset.pollBound === '1') return;
    container.dataset.pollBound = '1';
    setInterval(poll, 5000);
  }

  window.initUsersTable = initUsersTable;
  window.initUsersPolling = initUsersPolling;

  document.addEventListener('DOMContentLoaded', () => {
    try { initUsersTable(); } catch (e) { /* ignore */ }
    try { initUsersPolling(); } catch (e) { /* ignore */ }
  });

})();
