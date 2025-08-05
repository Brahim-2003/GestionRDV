// static/rdv/js/doctor/dispo_modal.js

function initCreateDispoModal() {
  const openBtn   = document.getElementById('open-create-dispo');
  const modal     = document.getElementById('create-dispo-modal');
  const closeBtn  = modal?.querySelector('.modal-close');
  const container = document.getElementById('modal-form-container');

  if (!openBtn || !modal || !closeBtn || !container) return;

  // Désactive les anciens handlers
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
      .then(html => {
        container.innerHTML = html;
        // Après chargement, initie le handler de soumission
        if (window.initDispoForm) window.initDispoForm();
      })
      .catch(() => container.innerHTML = '<p>Impossible de charger le formulaire.</p>');
  });

  closeBtn.addEventListener('click', () => {
    modal.classList.add('hidden');
  });

  modal.addEventListener('click', e => {
    if (e.target === modal) modal.classList.add('hidden');
  });
}

document.addEventListener('click', e => {
  if (e.target.closest('.modal-cancel')) {
    const modal = document.getElementById('create-dispo-modal');
    if (modal) modal.classList.add('hidden');
  }
});

window.initCreateDispoModal = initCreateDispoModal;
