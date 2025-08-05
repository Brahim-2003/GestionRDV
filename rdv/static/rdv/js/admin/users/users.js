/**
 * initUsersTable()
 * – Recherche live + filtre rôle + pagination + history
 */

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

  const container   = document.getElementById('users-table-container');
  const searchInput = document.getElementById('search-input');
  const roleSelect  = document.getElementById('role-select');
  if (!container || !searchInput || !roleSelect) return;

  const baseUrl = container.dataset.url;
  let debounceTimer;

  function debounce(fn, delay = 300) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
  }

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

  function bindTableEvents() {
  // … pagination code …

  // suppression AJAX
  container.querySelectorAll('.action-btn-delete').forEach(link => {
    link.onclick = null;
    link.addEventListener('click', e => {
      e.preventDefault();
      if (!confirm('Confirmer la suppression de cet utilisateur ?')) return;

      const url = link.dataset.deleteUrl;
      const row = link.closest('tr');
      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': getCookie('csrftoken'),
          'X-Requested-With': 'XMLHttpRequest',
        },
      })
      .then(res => res.ok ? res.json() : Promise.reject(res.statusText))
      .then(data => {
        if (data.status === 'success') {
          row.remove();
        } else {
          alert(data.message || 'Erreur lors de la suppression');
        }
      })
      .catch(err => {
        console.error('Delete error:', err);
        alert('Impossible de supprimer l’utilisateur');
      });
    });
  });
}


  // recherche live
  searchInput.oninput = null;
  searchInput.addEventListener('input', () => {
    debounce(() => {
      fetchTable({ 
        search: searchInput.value, 
        role:  roleSelect.value 
      });
    });
  });

  // filtre rôle
  roleSelect.onchange = null;
  roleSelect.addEventListener('change', () => {
    fetchTable({ 
      search: searchInput.value, 
      role:  roleSelect.value 
    });
  });

  // history back/forward
  function handlePopState() {
    if (!document.body.contains(container)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    fetchTable(params);
  }
  window.removeEventListener('popstate', handlePopState);
  window.addEventListener('popstate', handlePopState);

  // initial bindings
  bindTableEvents();
}
window.initUsersTable = initUsersTable;

/**
 * initUsersPolling()
 * – Polling optimisé : ne recharge que si les données ont changé
 */
function initUsersPolling() {
  console.log('🔄 initUsersPolling');

  const container = document.getElementById('users-table-container');
  if (!container) return;
  const ajaxUrl = container.dataset.ajaxUrl;
  let lastVersion = null;

  async function poll() {
    let url = ajaxUrl;
    if (lastVersion) {
      url += `?last_version=${encodeURIComponent(lastVersion)}`;
    }
    try {
      const res  = await fetch(url, { headers: {'X-Requested-With':'XMLHttpRequest'} });
      const data = await res.json();
      if (data.changed) {
        lastVersion = data.last_version;
        // recharge intégralement la table via AJAX
        window.fetchTable({
          search: document.getElementById('search-input').value,
          role:   document.getElementById('role-select').value
        });
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }

  // Démarre le polling toutes les 5s (ou 3000 pour 3s, etc.)
  setInterval(poll, 5000);
}

window.initUsersPolling = initUsersPolling;
