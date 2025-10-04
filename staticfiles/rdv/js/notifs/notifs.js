// static/rdv/js/notifs/notifs.js

function initNotifs() {
  console.log('🔄 initNotifs');

  const root = document.getElementById('notif-root');
  if (!root) return;

  const urlCount      = root.dataset.urlCount;
  const urlMarkRead   = root.dataset.urlMarkRead.replace('/0/', '/');      // on remplacera le 0 par l’ID
  const urlMarkAll    = root.dataset.urlMarkAll;
  const urlDelete     = root.dataset.urlDelete.replace('/0/', '/');
  const urlDeleteAll  = root.dataset.urlDeleteAll;

  // CSRF token
  function getCSRFToken() {
    const name = 'csrftoken';
    return document.cookie.split(';')
      .map(c => c.trim())
      .find(c => c.startsWith(name + '='))?.split('=')[1] || '';
  }
  const csrftoken = getCSRFToken();

  function makeRequest(url, method = 'POST', data = {}) {
    return fetch(url, {
      method,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrftoken,
        'X-Requested-With': 'XMLHttpRequest'
      },
      body: method === 'POST' ? JSON.stringify(data) : null
    });
  }

  // Met à jour le compteur
  function updateCount() {
    makeRequest(urlCount, 'GET')
      .then(r => r.json())
      .then(d => {
        const c = document.querySelector('.notifications-count');
        if (c) c.textContent = d.unread_count
          ? `${d.unread_count} nouvelle${d.unread_count>1?'s':''}`
          : 'Aucune nouvelle';
      });
  }

  // État vide
  function checkEmpty() {
    const items = [...document.querySelectorAll('.notification-item')]
      .filter(i => i.style.display !== 'none');
    const empty = document.querySelector('.empty-state');
    if (!empty) return;
    empty.classList.toggle('hidden', items.length>0);
  }

  // Alerte temporaire
  function showAlert(msg, type='info') {
    const a = document.createElement('div');
    a.className = `alert alert-${type}`;
    a.textContent = msg;
    document.body.prepend(a);
    setTimeout(() => a.remove(), 3000);
  }

  // Filtrage
  document.querySelectorAll('.filter-tab').forEach(tab => {
    tab.type = 'button';
    tab.onclick = null;
    tab.addEventListener('click', e => {
      e.stopImmediatePropagation();
      e.preventDefault();
      document.querySelectorAll('.filter-tab').forEach(t=>t.classList.remove('active'));
      tab.classList.add('active');
      const type = tab.dataset.type;
      document.querySelectorAll('.notification-item')
        .forEach(item => {
          item.style.display = (type==='all' || item.classList.contains(type))
            ? '' : 'none';
        });
      checkEmpty();
    });
  });

  // Marquer une seule
  document.querySelectorAll('.mark-read').forEach(btn => {
    btn.type = 'button';
    btn.onclick = null;
    btn.addEventListener('click', e => {
      e.stopImmediatePropagation(); e.preventDefault();
      const id = btn.dataset.id;
      const item = btn.closest('.notification-item');
      btn.disabled = true;
      btn.innerHTML = '…';

      makeRequest(urlMarkRead + id + '/')
        .then(r=>r.json())
        .then(d=>{
          if (d.status==='success') {
            item.classList.remove('unread');
            item.querySelector('.unread-indicator')?.remove();
            btn.remove();
            updateCount();
          }
        })
        .catch(()=>{
          showAlert('Erreur maj lecture','error');
          btn.disabled=false;
          btn.innerHTML = '<i class="fas fa-eye"></i>';
        });
    });
  });

  // Supprimer une seule
  document.querySelectorAll('.delete-single').forEach(btn => {
    btn.type = 'button';
    btn.onclick = null;
    btn.addEventListener('click', e => {
      e.stopImmediatePropagation(); e.preventDefault();
      if (!confirm('Supprimer cette notification ?')) return;
      const id = btn.dataset.id;
      const item = btn.closest('.notification-item');
      item.classList.add('removing');

      makeRequest(urlDelete + id + '/', 'POST')
        .then(r=>r.json())
        .then(d=>{
          if (d.status==='success') {
            item.remove();
            updateCount();
            checkEmpty();
          }
        })
        .catch(()=>{
          showAlert('Erreur suppression','error');
          item.classList.remove('removing');
        });
    });
  });

  // Tout marquer lu
  const markAll = document.getElementById('mark-all-read');
  if (markAll) {
    markAll.type = 'button';
    markAll.onclick = null;
    markAll.addEventListener('click', e => {
      e.stopImmediatePropagation(); e.preventDefault();
      markAll.disabled = true;
      markAll.textContent = '…';
      makeRequest(urlMarkAll, 'POST')
        .then(r=>r.json())
        .then(d=>{
          if (d.status==='success') {
            document.querySelectorAll('.notification-item.unread')
              .forEach(item=>{
                item.classList.remove('unread');
                item.querySelector('.unread-indicator')?.remove();
              });
            document.querySelectorAll('.mark-read').forEach(b=>b.remove());
            updateCount();
          } else showAlert(d.message,'error');
        })
        .finally(()=>{
          markAll.disabled=false;
          markAll.textContent = 'Marquer toutes comme lues';
        });
    });
  }

  // Tout supprimer
  const deleteAll = document.getElementById('delete-all');
  if (deleteAll) {
    deleteAll.type = 'button';
    deleteAll.onclick = null;
    deleteAll.addEventListener('click', e => {
      e.stopImmediatePropagation(); e.preventDefault();
      if (!confirm('Supprimer toutes les notifications ?')) return;
      deleteAll.disabled = true;
      deleteAll.textContent = '…';
      makeRequest(urlDeleteAll, 'POST')
        .then(r=>r.json())
        .then(d=>{
          if (d.status==='success') {
            document.querySelectorAll('.notification-item').forEach(i=>i.remove());
            updateCount();
            checkEmpty();
          } else showAlert(d.message,'error');
        })
        .finally(()=>{
          deleteAll.disabled=false;
          deleteAll.textContent = 'Supprimer toutes';
        });
    });
  }

  // Initial
  updateCount();
  checkEmpty();
}

window.initNotifs = initNotifs;
