// static/rdv/js/modal/profile_modal.js
(function () {
  'use strict';

  const DEFAULTS = {
    modalSelector: '#edit-user-modal',
    containerSelector: '#edit-user-modal-form-container',
    hiddenClass: 'hidden',
    ajaxHeader: { 'X-Requested-With': 'XMLHttpRequest' }
  };

  const STYLE_ID = 'profile-modal-default-styles';
  const DEFAULT_STYLES = `
  .modal-overlay { position: fixed; inset: 0; display:flex; align-items:center; justify-content:center; background: rgba(0,0,0,0.45); z-index:9999; }
  .modal-overlay.hidden { display:none; }
  .modal { background:#fff; border-radius:8px; width:min(720px, 96%); box-shadow: 0 10px 30px rgba(0,0,0,0.15); overflow:hidden; }
  .modal-header { padding:12px 16px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #eee; }
  .modal-title { margin:0; font-size:1.05rem; display:flex; gap:8px; align-items:center; }
  .modal-body { padding:14px 16px; max-height:70vh; overflow:auto; }
  .modal-close { background:none; border:0; font-size:1.25rem; line-height:1; cursor:pointer; }
  .errorlist { color: #b1202e; margin-top:6px; font-size:0.95rem; }
  `;

  const ProfileModal = (function () {
    let opts = Object.assign({}, DEFAULTS);
    let modalEl = null;
    let containerEl = null;
    let closeBtn = null;

    function _ensureStyles() {
      if (!document.getElementById(STYLE_ID)) {
        const s = document.createElement('style');
        s.id = STYLE_ID;
        s.textContent = DEFAULT_STYLES;
        document.head.appendChild(s);
      }
    }

    function _ensureElements() {
      modalEl = document.querySelector(opts.modalSelector);
      if (!modalEl) return false;

      containerEl = modalEl.querySelector(opts.containerSelector) || modalEl.querySelector('[data-modal-container]');
      closeBtn = modalEl.querySelector('.modal-close');

      _ensureStyles();
      return !!containerEl;
    }

    function init(custom = {}) {
      opts = Object.assign({}, opts, custom);

      _ensureElements();

      if (!modalEl) return;

      if (closeBtn && !closeBtn.dataset.bound) {
        closeBtn.dataset.bound = '1';
        closeBtn.addEventListener('click', (e) => { e.preventDefault(); close(); });
      }

      if (!modalEl.dataset.overlayBound) {
        modalEl.addEventListener('click', (e) => {
          if (e.target === modalEl) close();
        });
        modalEl.dataset.overlayBound = '1';
      }
    }

    function open() {
      if (!_ensureElements()) return;
      modalEl.classList.remove(opts.hiddenClass);
      modalEl.setAttribute('aria-hidden', 'false');
    }

    function close() {
      if (!modalEl) return;
      modalEl.classList.add(opts.hiddenClass);
      modalEl.setAttribute('aria-hidden', 'true');
      if (containerEl) containerEl.innerHTML = '<p>Chargement du formulaire…</p>';
    }

    async function loadFragment(url) {
      if (!_ensureElements()) throw new Error('Modal container not found');
      const res = await fetch(url, { headers: opts.ajaxHeader, credentials: 'same-origin' });
      if (!res.ok) throw new Error('Impossible de charger le fragment');
      const html = await res.text();
      containerEl.innerHTML = html;
      return containerEl;
    }

    return { init, open, close, loadFragment };
  })();

  // Initialisation pour les 3 modals
  document.addEventListener('DOMContentLoaded', () => {
    try {
      ProfileModal.init({ modalSelector: '#edit-user-modal', containerSelector: '#edit-user-modal-form-container' });
      ProfileModal.init({ modalSelector: '#edit-patient-modal', containerSelector: '#edit-patient-modal-form-container' });
      ProfileModal.init({ modalSelector: '#edit-medecin-modal', containerSelector: '#edit-medecin-modal-form-container' });
    } catch (e) { /* ignore */ }
  });

  window.ProfileModal = ProfileModal;
})();
