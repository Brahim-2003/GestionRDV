// static/rdv/js/doctor/dispo.js

// =========================
// 1) UTILS
// =========================
console.log('dispo.js chargé');

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    document.cookie.split(';').forEach(c => {
      c = c.trim();
      if (c.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(c.slice(name.length + 1));
      }
    });
  }
  return cookieValue;
}

// =========================
// 2) FORM AJAX (création)
// =========================
function initDispoForm() {
  const form = document.querySelector('#create-dispo-form');
  if (!form) return;

  // Désactive d'éventuels anciens handlers
  form.onsubmit = null;

  form.addEventListener('submit', e => {
    e.preventDefault();
    const url = form.action;
    const data = new FormData(form);

    fetch(url, {
      method: 'POST',
      headers: {
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: data
    })
    .then(r => r.ok ? r.json() : r.json().then(err => Promise.reject(err)))
    .then(json => {
      if (json.status === 'ok') {
        // Recharge la table
        if (window.fetchDispoTable) window.fetchDispoTable();
        else location.reload();
        // Ferme le modal
        document.getElementById('create-dispo-modal').classList.add('hidden');
      } else {
        console.error(json.errors);
        alert('Erreurs : ' + JSON.stringify(json.errors));
      }
    })
    .catch(err => {
      console.error('Erreur AJAX disposition:', err);
      alert('Une erreur est survenue');
    });
  });
}

// =========================
// 3) MODAL create dispo
// =========================
function initCreateDispoModal() {
  const openBtn   = document.getElementById('open-create-dispo');
  const modal     = document.getElementById('create-dispo-modal');
  const closeBtns = modal?.querySelectorAll('.modal-close, .modal-cancel');
  const container = document.getElementById('modal-form-container');
  if (!openBtn || !modal || !closeBtns.length || !container) return;

  openBtn.onclick = () => {
    modal.classList.remove('hidden');
    container.innerHTML = '<p>Chargement du formulaire…</p>';
    fetch(openBtn.dataset.formUrl, {
      headers: {'X-Requested-With':'XMLHttpRequest'}
    })
    .then(r => r.ok ? r.text() : Promise.reject())
    .then(html => {
      container.innerHTML = html;
      initDispoForm();  // Bind form handler
      // Init flatpickr on the injected inputs
      if (window.flatpickr) {
        flatpickr(container.querySelectorAll('input[type="text"]'), {
          enableTime: true,
          noCalendar: true,
          dateFormat: "H:i"
        });
      }
    })
    .catch(() => {
      container.innerHTML = '<p>Impossible de charger le formulaire.</p>';
    });
  };

  closeBtns.forEach(btn => btn.onclick = () => modal.classList.add('hidden'));
  modal.onclick = e => { if (e.target === modal) modal.classList.add('hidden'); };
}

// =========================
// 4) TABLE: search, date, pagination, delete
// =========================
function initDispoTable() {
  console.log('🔄 initDispoTable');
  const container   = document.getElementById('dispo-table-container');
  const searchInput = document.getElementById('search-input');
  const dateInput   = document.querySelector('.date-input');
  if (!container || !searchInput || !dateInput) return;

  const baseUrl = container.dataset.url;
  let debounceTimer;

  function debounce(fn, delay=300) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, delay);
  }

  async function fetchDispoTable(params={}) {
  const url = new URL(container.dataset.ajaxUrl, window.location.origin);
  Object.entries(params).forEach(([k,v])=>{
    v ? url.searchParams.set(k,v) : url.searchParams.delete(k);
  });
  const r = await fetch(url, { headers:{ 'X-Requested-With':'XMLHttpRequest' } });
  const html = await r.text();
  // on s'attend à du <table>…</table> ou au moins <tbody>…</tbody>
  container.innerHTML = html;
  bindTableEvents();
}
  window.fetchDispoTable = fetchDispoTable;

  function bindTableEvents() {
    // DELETE
    container.querySelectorAll('.action-btn-delete').forEach(btn => {
      btn.onclick = null;
      btn.addEventListener('click', async e => {
        e.preventDefault();
        if (!confirm('Supprimer ce créneau ?')) return;
        const url = btn.dataset.deleteUrl;
        const row = btn.closest('tr');
        try {
          const r = await fetch(url, {
            method: 'POST',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'X-Requested-With':'XMLHttpRequest'
            }
          });
          const json = await r.json();
          if (json.status==='success' || json.success) row.remove();
          else alert(json.message||'Erreur suppression');
        } catch(err) {
          console.error('delete error:', err);
          alert('Impossible de supprimer');
        }
      });
    });

    // PAGINATION
    container.querySelectorAll('.pagination a[data-page]').forEach(link => {
      link.onclick = null;
      link.addEventListener('click', e => {
        e.preventDefault();
        const page = link.dataset.page;
        fetchDispoTable({
          search: searchInput.value,
          date:   dateInput.value,
          page
        });
        history.pushState(null,'',`?page=${page}&search=${encodeURIComponent(searchInput.value)}&date=${encodeURIComponent(dateInput.value)}`);
      });
    });
  }

  bindTableEvents();

  // LIVE SEARCH
  searchInput.oninput = null;
  searchInput.addEventListener('input', () => debounce(() => {
    fetchDispoTable({ search: searchInput.value, date: dateInput.value });
  }));

  // DATE FILTER
  dateInput.onchange = null;
  dateInput.addEventListener('change', () => {
    fetchDispoTable({ search: searchInput.value, date: dateInput.value });
  });

  // HISTORY NAV
  window.addEventListener('popstate', () => {
    if (!document.body.contains(container)) return;
    const params = Object.fromEntries(new URLSearchParams(location.search));
    fetchDispoTable(params);
  });
}

// =========================
// 5) POLLING
// =========================
function initDispoPolling() {
  console.log('🔄 initDispoPolling');
  const container = document.getElementById('dispo-table-container');
  if (!container) return;
  const ajaxUrl = container.dataset.ajaxUrl;
  let lastCount = null;

  async function poll() {
    let url = ajaxUrl;
    if (lastCount !== null) url += `?last_count=${lastCount}`;
    try {
      const res  = await fetch(url, { headers:{'X-Requested-With':'XMLHttpRequest'} });
      const data = await res.json();
      if (data.changed) {
        lastCount = data.last_count;
        window.fetchDispoTable({
          search: document.getElementById('search-input').value,
          date:   document.querySelector('.date-input').value
        });
      }
    } catch(e) {
      console.error('polling error:', e);
    }
  }

  setInterval(poll, 5000);
}

// =========================
// 6) INIT ON DOM READY
// =========================
document.addEventListener('DOMContentLoaded', () => {
  // Init Flatpickr for date field if loaded
  if (window.flatpickr) {
    flatpickr('.date-input', { dateFormat: 'Y-m-d' });
  }
  initCreateDispoModal();
  initDispoForm();
  initDispoTable();
  initDispoPolling();
});
