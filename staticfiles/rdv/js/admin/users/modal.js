// static/rdv/js/admin/users/modal.js

function initCreateUserModal() {
  const openBtn   = document.getElementById('open-create-user');
  const modal     = document.getElementById('create-user-modal');
  const closeBtn  = modal?.querySelector('.modal-close');
  const container = document.getElementById('modal-form-container');

  if (!openBtn || !modal || !closeBtn || !container) return;

  // Pour éviter doublons d'écouteurs
  openBtn.onclick = null;
  closeBtn.onclick = null;
  modal.onclick    = null;

  openBtn.addEventListener('click', () => {
    modal.classList.remove('hidden');
    container.innerHTML = '<p>Chargement du formulaire…</p>';
    fetch(openBtn.dataset.formUrl, {
      headers: {'X-Requested-With':'XMLHttpRequest'}
    })
      .then(r => r.ok ? r.text() : Promise.reject())
      .then(html => container.innerHTML = html)
      .catch(() => container.innerHTML = '<p>Impossible de charger le formulaire.</p>');
  });

  closeBtn.addEventListener('click', () => {
    modal.classList.add('hidden');
  });

}

document.addEventListener('click', function(e) {
  // Si on clique sur un bouton Annuler dans un modal
  if (e.target.closest('.modal-cancel')) {
    const modal = document.getElementById('create-user-modal');
    if (modal) modal.classList.add('hidden');
  }
});

window.initCreateUserModal = initCreateUserModal;
