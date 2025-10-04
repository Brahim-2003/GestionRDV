// static/rdv/js/modal/rdv_modal.js
(function () {
  'use strict';

  const DEFAULTS = {
    modalSelector: '#annuler-rdv-modal',
    containerSelector: '#annuler-modal-form-container',
    hiddenClass: 'hidden',
    ajaxHeader: { 'X-Requested-With': 'XMLHttpRequest' },
    autoInjectMissing: true,
  };

  // HTML templates pour injection automatique
  const ANNULER_HTML = `
  <div id="annuler-rdv-modal" class="modal-overlay hidden" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="annuler-rdv-title">
      <header class="modal-header">
        <h2 id="annuler-rdv-title" class="modal-title"><i class='bx bxs-trash'></i> Annuler le rendez-vous</h2>
        <button class="modal-close" aria-label="Fermer">&times;</button>
      </header>
      <section class="modal-body">
        <div id="annuler-modal-form-container"><p>Chargement du formulaire…</p></div>
      </section>
    </div>
  </div>`;

  const REPORTER_HTML = `
  <div id="reporter-rdv-modal" class="modal-overlay hidden" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="reporter-rdv-title">
      <header class="modal-header">
        <h2 id="reporter-rdv-title" class="modal-title"><i class='bx bxs-refresh'></i> Reporter le rendez-vous</h2>
        <button class="modal-close" aria-label="Fermer">&times;</button>
      </header>
      <section class="modal-body">
        <div id="reporter-modal-form-container"><p>Chargement du formulaire…</p></div>
      </section>
    </div>
  </div>`;

  const NOTIFIER_HTML = `
  <div id="notifier-rdv-modal" class="modal-overlay hidden" aria-hidden="true">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="notifier-rdv-title">
      <header class="modal-header">
        <h2 id="notifier-rdv-title" class="modal-title"><i class='bx bxs-message-rounded-add'></i> Notifier le patient</h2>
        <button class="modal-close" aria-label="Fermer">&times;</button>
      </header>
      <section class="modal-body">
        <div id="notifier-modal-form-container"><p>Chargement du formulaire…</p></div>
      </section>
    </div>
  </div>`;                 

  const STYLE_ID = 'rdv-modal-default-styles';
  const DEFAULT_STYLES = `
  .modal-overlay { position: fixed; inset: 0; display:flex; align-items:center; justify-content:center; background: rgba(0,0,0,0.45); z-index:9999; }
  .modal-overlay.hidden { display:none; }
  .modal { background:#fff; border-radius:8px; width:min(720px, 96%); box-shadow: 0 10px 30px rgba(0,0,0,0.15); overflow:hidden; }
  .modal-header { padding:12px 16px; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid #eee; }
  .modal-title { margin:0; font-size:1.05rem; display:flex; gap:8px; align-items:center; }
  .modal-body { padding:14px 16px; max-height:70vh; overflow:auto; }
  .modal-close { background:none; border:0; font-size:1.25rem; line-height:1; cursor:pointer; }
  .errorlist { color: #b1202e; margin-top:6px; font-size:0.95rem; }
  .btn { padding:8px 12px; border-radius:6px; border:1px solid rgba(0,0,0,0.06); cursor:pointer; }
  .btn-primary { background:#007bff; color:#fff; }
  .btn-danger { background:#dc3545; color:#fff; }
  .btn-secondary { background:#f0f0f0; color:#111; }
  `;

  const RdvModal = (function () {
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

    function _injectIfMissing() {
      if (!opts.autoInjectMissing) return;
      if (!document.getElementById('annuler-rdv-modal')) {
        const frag = document.createElement('div');
        frag.innerHTML = ANNULER_HTML;
        document.body.appendChild(frag.firstElementChild);
      }
      if (!document.getElementById('reporter-rdv-modal')) {
        const frag = document.createElement('div');
        frag.innerHTML = REPORTER_HTML;
        document.body.appendChild(frag.firstElementChild);
      }
      if (!document.getElementById('notifier-rdv-modal')) {
        const frag = document.createElement('div');
        frag.innerHTML = NOTIFIER_HTML;
        document.body.appendChild(frag.firstElementChild);
      }
      _ensureStyles();
    }

    function _ensureElements() {
      modalEl = document.querySelector(opts.modalSelector);
      if (!modalEl) {
        _injectIfMissing();
        modalEl = document.querySelector(opts.modalSelector);
        if (!modalEl) return false;
      }
      containerEl = modalEl.querySelector(opts.containerSelector) || modalEl.querySelector('[data-modal-container]');
      closeBtn = modalEl.querySelector('.modal-close');
      return !!containerEl;
    }

    function init(custom = {}) {
      opts = Object.assign({}, opts, custom);

      if (!custom.containerSelector && String(opts.modalSelector).includes('reporter')) {
        opts.containerSelector = '#reporter-modal-form-container';
      }
      if (!custom.containerSelector && String(opts.modalSelector).includes('annuler')) {
        opts.containerSelector = '#annuler-modal-form-container';
      }
      if (!custom.containerSelector && String(opts.modalSelector).includes('notifier')) {
        opts.containerSelector = '#notifier-modal-form-container';
      }

      _ensureElements();

      if (!modalEl) return;

      if (closeBtn && !closeBtn.dataset.bound) {
        closeBtn.dataset.bound = '1';
        closeBtn.addEventListener('click', (e) => { e.preventDefault(); close(); });
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

  document.addEventListener('DOMContentLoaded', () => {
    try {
      RdvModal.init();
      RdvModal.init({ modalSelector: '#reporter-rdv-modal', containerSelector: '#reporter-modal-form-container' });
      RdvModal.init({ modalSelector: '#notifier-rdv-modal', containerSelector: '#notifier-modal-form-container' });
    } catch (e) { /* ignore */ }
  });

  window.RdvModal = RdvModal;
})();
