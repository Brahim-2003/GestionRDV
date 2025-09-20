// static/rdv/js/doctor/dispo_modal.js
// Gestion centralisée des modals Create / Edit pour disponibilités
// Idempotent, délégué, tolerant aux injections AJAX et aux double-charges.

(function(){
  if (window.__dispo_modal_installed) return;
  window.__dispo_modal_installed = true;
  console.log("dispo_modal.js initialisé");

  const q = s => document.querySelector(s);
  const qa = s => Array.from(document.querySelectorAll(s));

  // helper: récupérer cookie (si besoin)
  const getCookie = name => {
    if (!document.cookie) return null;
    let value = null;
    document.cookie.split(";").forEach(c => {
      c = c.trim();
      if (c.startsWith(name + "=")) value = decodeURIComponent(c.slice(name.length + 1));
    });
    return value;
  };

  // Utilisé pour debug/inspection si tu veux
  function safeLog(...args){ try { console.log(...args); } catch(e){} }

  // Bind/unbind helpers pour ne pas accrocher plusieurs fois
  function onceDataset(el, key){
    if (!el) return false;
    if (el.dataset[key] === "1") return false;
    el.dataset[key] = "1";
    return true;
  }

  // Injection HTML dans un container et initialisation (flatpickr + bind form)
  async function loadFragmentInto(url, container){
    if (!container) return;
    container.innerHTML = '<p>Chargement…</p>';
    try {
      const res = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const text = await res.text();

      // Si la réponse contient une page complète, on cherche un fragment #ajax-content
      let fragment = text;
      if (text.includes('<html') || text.includes('<body') || text.includes('id="ajax-content"')) {
        const tmp = document.createElement('div');
        tmp.innerHTML = text;
        const ext = tmp.querySelector('#ajax-content') || tmp.querySelector('body');
        fragment = ext ? ext.innerHTML : text;
      }

      container.innerHTML = fragment;

      // debug: afficher ce qui a été injecté si on a un souci sur champs manquants
      // safeLog('fragment injected length:', container.innerHTML.length);

      // init flatpickr si disponible (respecter values)
      if (window.flatpickr) {
        try {
          const dateInputs = container.querySelectorAll('input[type="date"], input.flat-date');
          if (dateInputs.length) flatpickr(dateInputs, { dateFormat: "Y-m-d", allowInput: true });
          const timeInputs = container.querySelectorAll('input[type="time"], input.flat-time');
          if (timeInputs.length) flatpickr(timeInputs, { enableTime: true, noCalendar: true, dateFormat: "H:i", allowInput: true });
        } catch (e) { console.warn("flatpickr init failed", e); }
      }

      // Après injection, lier le formulaire présent (si data-ajax="1")
      bindModalForm(container);
    } catch (err) {
      console.error("loadFragmentInto error", err);
      container.innerHTML = '<p>Impossible de charger le formulaire.</p>';
    }
  }

  // Bind d'un formulaire injecté dans un modal container
  function bindModalForm(container){
    if (!container) return;
    const form = container.querySelector('form[data-ajax="1"]');
    if (!form) return;

    // Eviter double binding
    if (form.dataset.bound === "1") return;
    form.dataset.bound = "1";

    // Supprime anciennes erreurs affichées si réouverture
    const removeOldErrors = () => {
      const old = form.querySelector(".form-errors");
      if (old) old.remove();
    };

    form.addEventListener('submit', function(e){
      e.preventDefault();
      removeOldErrors();

      // Utiliser ajaxSubmitForm si elle existe (dans dispo.js)
      const submitHandler = window.ajaxSubmitForm;
      if (typeof submitHandler === 'function') {
        submitHandler(form, container, json => {
          // onSuccess
          // ferme modals s'il y en a
          (q('#create-dispo-modal') || { classList: { add(){} } }).classList.add('hidden');
          (q('#edit-dispo-modal')   || { classList: { add(){} } }).classList.add('hidden');

          // dispatch event global pour rafraîchir la table
          try { document.dispatchEvent(new CustomEvent('dispo:saved', { detail: json })); } catch(e){}

          // si la fonction fetchDispoTable existe, l'appeler
          if (typeof window.fetchDispoTable === 'function') window.fetchDispoTable();
        });
        return;
      }

      // fallback minimal si ajaxSubmitForm non présent : petit POST fetch
      (async () => {
        try {
          const url = form.action;
          const data = new FormData(form);
          const res = await fetch(url, {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest' },
            body: data,
            credentials: 'same-origin'
          });
          const ct = res.headers.get('content-type')||'';
          if (ct.includes('application/json')) {
            const json = await res.json();
            if (res.ok && (json.status === 'ok' || json.success === true)) {
              // succès
              try { document.dispatchEvent(new CustomEvent('dispo:saved', { detail: json })); } catch(e){}
              (q('#create-dispo-modal') || { classList: { add(){} } }).classList.add('hidden');
              (q('#edit-dispo-modal')   || { classList: { add(){} } }).classList.add('hidden');
              if (typeof window.fetchDispoTable === 'function') window.fetchDispoTable();
              return;
            }
            // erreurs JSON
            const errors = json.errors || json;
            showInlineErrors(form, errors);
            return;
          }

          // si HTML renvoyé (fragment), on remplace le container
          const text = await res.text();
          if (text.includes('<form')) {
            container.innerHTML = text;
            bindModalForm(container);
            return;
          }
          showInlineErrors(form, 'Erreur serveur');
        } catch (err) {
          console.error('submit fallback error', err);
          showInlineErrors(form, 'Erreur réseau — impossible de soumettre.');
        }
      })();
    });
  }

  // Affiche erreurs simples dans le form (fallback si ajaxSubmitForm non présent)
  function showInlineErrors(formEl, errors){
    if (!formEl) return;
    const prev = formEl.querySelector('.form-errors');
    if (prev) prev.remove();
    const box = document.createElement('div');
    box.className = 'form-errors';
    box.style.color = '#b91c1c';
    box.style.margin = '0 0 .6rem 0';
    box.style.fontSize = '.95rem';

    if (errors && typeof errors === 'object' && !Array.isArray(errors)) {
      const ul = document.createElement('ul');
      ul.style.margin = '0';
      Object.entries(errors).forEach(([k,v]) => {
        const li = document.createElement('li');
        const label = (k === '__all__' || k === 'non_field_errors') ? '' : `${k} : `;
        li.innerHTML = `<strong>${label}</strong>${Array.isArray(v) ? v.join(', ') : v}`;
        ul.appendChild(li);
      });
      box.appendChild(ul);
    } else if (Array.isArray(errors)) {
      box.innerHTML = `<ul style="margin:0"><li>${errors.join('</li><li>')}</li></ul>`;
    } else {
      box.textContent = String(errors);
    }
    formEl.insertBefore(box, formEl.firstChild);
  }

  // ------------------------
  // Délégué global click handler
  // ------------------------
  // On ajoute un seul listener document-level (idempotent)
  if (!window.__dispo_modal_click_bound) {
    window.__dispo_modal_click_bound = true;
    document.addEventListener('click', function(e){
      // 1) Open create modal
      const openCreate = e.target.closest('#open-create-dispo');
      if (openCreate) {
        e.preventDefault();
        const modal = q('#create-dispo-modal');
        const container = q('#modal-form-container');
        if (!modal || !container) { console.warn('create modal container missing'); return; }
        modal.classList.remove('hidden');
        const url = openCreate.dataset.formUrl || openCreate.getAttribute('data-form-url') || openCreate.getAttribute('href');
        if (!url) { container.innerHTML = '<p>URL formulaire introuvable.</p>'; return; }
        loadFragmentInto(url, container);
        return;
      }

      // 2) Open edit modal (any click on .action-btn-edit or its icon/link)
      const editBtn = e.target.closest('.action-btn-edit');
      if (editBtn) {
        e.preventDefault();
        // determine url: check data-edit-url, data-slot-id, href
        const url = editBtn.dataset.editUrl || editBtn.dataset.slotId || editBtn.getAttribute('href') || editBtn.dataset.url;
        const modal = q('#edit-dispo-modal');
        const container = q('#edit-modal-form-container');
        if (!modal || !container) {
          // fallback: open in create modal if edit modal missing (prevent double-inject)
          const fallbackModal = q('#create-dispo-modal');
          const fallbackContainer = q('#modal-form-container');
          if (!fallbackModal || !fallbackContainer) { window.location = url || editBtn.href; return; }
          fallbackModal.classList.remove('hidden');
          loadFragmentInto(url, fallbackContainer);
          return;
        }
        // mark busy to avoid double-clicks opening twice
        if (editBtn.dataset.busy === '1') return;
        editBtn.dataset.busy = '1';
        modal.classList.remove('hidden');
        loadFragmentInto(url, container).finally(() => { delete editBtn.dataset.busy; });
        return;
      }

      // 3) Close any modal via close buttons or overlay click
      if (e.target.closest('.modal-close') || e.target.closest('.modal-cancel')) {
        const modal = e.target.closest('.modal-overlay') || e.target.closest('.modal');
        if (modal) {
          // find overlay ancestor
          const overlay = modal.classList.contains('modal-overlay') ? modal : modal.closest('.modal-overlay');
          if (overlay) overlay.classList.add('hidden');
        } else {
          // hide standard modals
          q('#create-dispo-modal')?.classList.add('hidden');
          q('#edit-dispo-modal')?.classList.add('hidden');
        }
        return;
      }

    });
  }

  // ------------------------
  // Réception d'événements globaux
  // ------------------------
  // Lorsqu'une dispo est sauvegardée (dispatché par ajaxSubmitForm), on ferme modals et rafraîchit table
  document.addEventListener('dispo:saved', function(ev){
    q('#create-dispo-modal')?.classList.add('hidden');
    q('#edit-dispo-modal')?.classList.add('hidden');
    if (typeof window.fetchDispoTable === 'function') window.fetchDispoTable();
  });

  // Expose pour debug
  window.loadDispoFragmentInto = loadFragmentInto;
  window.bindModalForm = bindModalForm;
})();
