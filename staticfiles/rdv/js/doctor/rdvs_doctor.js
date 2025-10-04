// static/rdv/js/doctor/rdvs_doctor.js 
// Version finale : recherche par nom patient + filtre status + date + pagination + polling
// + corrections handlers modal submit (annuler / reporter)

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

    // small toast helper reused by confirm, cancel & report
    function showTransientToast(message, ms = 2200) {
      if (typeof window.showToast === 'function') {
        window.showToast(message);
        return;
      }
      const msg = document.createElement('div');
      msg.textContent = message;
      msg.style.position = 'fixed';
      msg.style.bottom = '20px';
      msg.style.right = '20px';
      msg.style.background = 'rgba(0,0,0,0.75)';
      msg.style.color = '#fff';
      msg.style.padding = '10px 14px';
      msg.style.borderRadius = '6px';
      msg.style.zIndex = 9999;
      document.body.appendChild(msg);
      setTimeout(()=> msg.remove(), ms);
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

    // Helper mapping labels (fallback if API doesn't provide statut_label)
    const STATUT_LABELS = {
      'programme': 'Programmé',
      'confirme': 'Confirmé',
      'en_cours': 'En cours',
      'termine': 'Terminé',
      'annule': 'Annulé',
      'reporte': 'Reporté'
    };

    function toBadgeClass(key) {
      return 'badge-' + (key || 'programme');
    }

    // utility to replace badge-* classes
    function replaceBadgeClass(el, newClass) {
      if (!el) return;
      Array.from(el.classList).forEach(c => { if (c.startsWith('badge-')) el.classList.remove(c); });
      if (newClass) el.classList.add(newClass);
    }

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

      // -----------------------------
      // CONFIRM BUTTONS: binding intégré ici (idempotent)
      // boutons attendus : <button class="action-btn-confirm js-confirm-rdv" data-rdv-id="..." data-statut="...">
      // -----------------------------
      // CONFIRM BUTTONS — binding idempotent et robuste
      container.querySelectorAll('.js-confirm-rdv').forEach(btn => {
        // éviter double binding
        if (btn.dataset.boundConfirm === '1') return;
        btn.dataset.boundConfirm = '1';

        // état initial : si already confirmed, désactiver et appliquer style
        try {
          const initialStatut = (btn.dataset.statut || '').trim();
          if (initialStatut === 'confirme') {
            btn.disabled = true;
            btn.setAttribute('aria-disabled', 'true');
            btn.classList.add('confirmed');
          }
        } catch (e) { /* ignore */ }

        btn.addEventListener('click', function (ev) {
          ev.preventDefault();
          if (btn.disabled) return;
          const rdvId = btn.dataset.rdvId;
          if (!rdvId) return console.error('rdv id manquant sur le bouton confirmer');

          // confirmation utilisateur (optionnel)
          const ok = confirm("Confirmer ce rendez-vous ?");
          if (!ok) return;

          // Désactiver et afficher spinner
          btn.disabled = true;
          btn.setAttribute('aria-busy', 'true');
          const origHtml = btn.innerHTML;
          btn.innerHTML = "<i class='bx bx-loader-circle bx-spin' aria-hidden='true'></i>";

          fetch(`/rdv/confirmer/${rdvId}/`, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
              'X-CSRFToken': getCookie('csrftoken'),
              'Accept': 'application/json',
              'X-Requested-With': 'XMLHttpRequest'
            },
          })
          .then(response => {
            // gérer explicitement 403 pour feedback clair
            if (response.status === 403) throw new Error('Accès refusé (403)');
            if (!response.ok) throw new Error('Erreur réseau');
            return response.json();
          })
          .then(data => {
            if (data && data.success) {
              // Mettre à jour data-statut sur le bouton pour futur checks
              try {
                btn.dataset.statut = data.statut || 'confirme';
              } catch (e) { /* ignore */ }

              // Mise à jour du badge statut dans la ligne
              const tr = btn.closest('tr');
              if (tr) {
                const statutEl = tr.querySelector('.stat');
                if (statutEl) {
                  const label = data.statut_label || STATUT_LABELS[data.statut] || data.statut;
                  statutEl.textContent = label;

                  // retirer anciennes classes badge-*
                  Array.from(statutEl.classList).forEach(c => {
                    if (c.startsWith('badge-')) statutEl.classList.remove(c);
                  });
                  // ajouter la nouvelle classe puis animer
                  statutEl.classList.add(toBadgeClass(data.statut));
                  statutEl.classList.remove('updated');
                  // force reflow pour relancer l'animation CSS
                  void statutEl.offsetWidth;
                  statutEl.classList.add('updated');
                }
              }

              // Transformer le bouton en état confirmé (✔) et le laisser désactivé
              btn.classList.add('confirmed');
              btn.disabled = true;
              btn.removeAttribute('aria-busy');
              btn.setAttribute('aria-disabled', 'true');
              btn.title = "Confirmé";
              btn.setAttribute('aria-label', 'Rendez-vous confirmé');

              // feedback utilisateur (toast minimal)
              showTransientToast('Rendez-vous confirmé.');

              // Forcer un refresh du tableau via la fonction exposée (si disponible)
              if (typeof window.fetchRdvsTable === 'function') {
                setTimeout(() => { window.fetchRdvsTable({}); }, 400);
              }

            } else {
              const msg = (data && (data.error || data.message)) ? (data.error || data.message) : 'Impossible de confirmer le rendez-vous.';
              alert(msg);
              // réactiver si erreur
              btn.disabled = false;
              btn.removeAttribute('aria-busy');
              btn.innerHTML = origHtml;
            }
          })
          .catch(err => {
            console.error('Confirmer RDV erreur:', err);
            // message plus lisible pour accès refusé
            if (err && String(err).toLowerCase().includes('403')) {
              alert('Accès refusé. Vous n\'êtes pas autorisé à confirmer ce rendez-vous.');
            } else {
              alert('Erreur lors de la confirmation. Vérifie la connexion ou réessayez.');
            }
            btn.disabled = false;
            btn.removeAttribute('aria-busy');
            btn.innerHTML = origHtml;
          });
        });
      });



      // -----------------------------
      // ANNULER BUTTONS: binding (modal + AJAX submit)
      // Attendus: <button class="action-btn-cancel js-cancel-rdv" data-rdv-id="..." data-statut="..." ...>
      // -----------------------------
      // modal elements (single global modal expected)
      const modal = document.getElementById('annuler-rdv-modal');
      const modalContainer = modal ? modal.querySelector('#annuler-modal-form-container') : null;
      const modalCloseBtn = modal ? modal.querySelector('.modal-close') : null;


      // attach close handlers once (if modal present)
      if (modal && modalCloseBtn && modal.dataset.boundClose !== '1') {
        modal.dataset.boundClose = '1';
        modalCloseBtn.addEventListener('click', (e) => { e.preventDefault(); modal.classList.add('hidden'); modal.setAttribute('aria-hidden','true'); if (modalContainer) modalContainer.innerHTML = '<p>Chargement du formulaire…</p>'; });
        modal.addEventListener('click', (e) => { if (e.target === modal) { modal.classList.add('hidden'); modal.setAttribute('aria-hidden','true'); if (modalContainer) modalContainer.innerHTML = '<p>Chargement du formulaire…</p>'; } });
      }

      // bind cancel buttons inside the table
      container.querySelectorAll('.js-cancel-rdv').forEach(btn => {
        if (btn.dataset.boundCancel === '1') return;
        btn.dataset.boundCancel = '1';

        // initial state: disable if already cancelled
        try {
          const initial = (btn.dataset.statut || '').trim();
          if (initial === 'annule') {
            btn.disabled = true;
            btn.setAttribute('aria-disabled', 'true');
          }
        } catch (e) { /* ignore */ }

        btn.addEventListener('click', async (ev) => {
          ev.preventDefault();
          if (btn.disabled) return;
          const rdvId = btn.dataset.rdvId;
          if (!rdvId) return console.error('rdv id manquant sur le bouton annuler');

          // ensure modal exists
          if (!modal || !modalContainer) {
            alert('Modal d\'annulation introuvable (vérifie que le fragment modal est inclus).');
            return;
          }

          // load fragment (GET /rdv/annuler/<id>/)
          const url = `/rdv/annuler/${rdvId}/`;
          try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' });
            if (!res.ok) throw new Error('Impossible de charger le formulaire');
            const html = await res.text();
            modalContainer.innerHTML = html;
            // open modal
            modal.classList.remove('hidden');
            modal.setAttribute('aria-hidden','false');

            // bind injected form inside modal
            const injectedForm = modalContainer.querySelector('form') || modalContainer.querySelector('#annuler-rdv-form');
            if (!injectedForm) {
              console.error('Formulaire d\'annulation introuvable après injection');
              return;
            }

            // bind inner cancel buttons (if present)
            injectedForm.querySelectorAll('.modal-cancel').forEach(el => {
              el.addEventListener('click', (e) => { e.preventDefault(); modal.classList.add('hidden'); modal.setAttribute('aria-hidden','true'); if (modalContainer) modalContainer.innerHTML = '<p>Chargement du formulaire…</p>'; });
            });

            // submit handler - bind once per injected form (dataset flag)
            if (!injectedForm.dataset.ajaxBoundCancel) {
              injectedForm.dataset.ajaxBoundCancel = '1';

              injectedForm.addEventListener('submit', async function handleCancelSubmit(e) {
                e.preventDefault();
                e.stopPropagation();

                const submitBtn = injectedForm.querySelector('button[type="submit"], #annuler-rdv-submit');
                const origText = submitBtn ? submitBtn.textContent : null;
                if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Annulation en cours...'; }

                const raisonField = injectedForm.querySelector('textarea[name="raison"]');
                const raison = raisonField ? raisonField.value.trim() : '';

                let data = null;
                let txt = null;
                try {
                  const postRes = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                      'X-CSRFToken': getCookie('csrftoken'),
                      'Content-Type': 'application/json',
                      'Accept': 'application/json',
                      'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ raison })
                  });

                  txt = await postRes.text().catch(()=>null);
                  try { data = txt ? JSON.parse(txt) : null; } catch(e) { data = null; }

                  if (!postRes.ok) {
                    if (data && data.errors) {
                      Object.keys(data.errors).forEach(field => {
                        const fieldEl = injectedForm.querySelector(`[name="${field}"]`);
                        if (fieldEl) {
                          let elErr = fieldEl.nextElementSibling;
                          if (!elErr || !elErr.classList.contains('errorlist')) {
                            elErr = document.createElement('div'); elErr.className = 'errorlist';
                            fieldEl.parentNode.insertBefore(elErr, fieldEl.nextSibling);
                          }
                          elErr.innerHTML = data.errors[field].join('<br/>');
                        }
                      });
                    } else {
                      alert(data && (data.error || data.message) ? (data.error || data.message) : 'Impossible d\'annuler le rendez-vous.');
                    }
                    return;
                  }

                  if (data && data.success) {
                    const trBtn = container.querySelector(`button.js-confirm-rdv[data-rdv-id="${rdvId}"]`);
                    let tr = trBtn ? trBtn.closest('tr') : container.querySelector(`tr[data-rdv-id="${rdvId}"]`) || null;
                    if (tr) {
                      const statutEl = tr.querySelector('.stat');
                      if (statutEl) {
                        statutEl.textContent = data.statut_label || STATUT_LABELS['annule'];
                        replaceBadgeClass(statutEl, toBadgeClass('annule'));
                        statutEl.classList.remove('updated');
                        void statutEl.offsetWidth;
                        statutEl.classList.add('updated');
                      }
                      tr.querySelectorAll('.action-btn-confirm, .action-btn-report, .action-btn-cancel').forEach(el => {
                        try { el.disabled = true; el.setAttribute('aria-disabled', 'true'); } catch (e) {}
                      });
                    }

                    showTransientToast('Rendez-vous annulé.');
                    modal.classList.add('hidden');
                    modal.setAttribute('aria-hidden','true');
                    modalContainer.innerHTML = '<p>Chargement du formulaire…</p>';
                    if (typeof window.fetchRdvsTable === 'function') {
                      setTimeout(()=> window.fetchRdvsTable({}), 300);
                    }
                  } else {
                    alert((data && (data.error || data.message)) || 'Impossible d\'annuler le rendez-vous.');
                  }

                } catch (err) {
                  console.error('Annuler RDV erreur:', err);
                  if (String(err).toLowerCase().includes('403')) alert('Accès refusé. Vous n\'êtes pas autorisé à annuler ce rendez-vous.');
                  else alert('Erreur lors de l\'annulation. Réessayez.');
                } finally {
                  if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText || 'Confirmer l\'annulation'; }
                }
              });
            }

          } catch (err) {
            console.error('Impossible de charger le formulaire d\'annulation', err);
            alert('Impossible de charger le formulaire. Réessayez.');
          }
        });
      }); // end cancel buttons forEach

      // -----------------------------
      // REPORTER BUTTONS: binding (modal + AJAX submit)
      // Attendus: <button class="action-btn-report js-report-rdv" data-rdv-id="..." data-statut="...">
      // -----------------------------
      const repModal = document.getElementById('reporter-rdv-modal');
      const repContainer = repModal ? repModal.querySelector('#reporter-modal-form-container') : null;
      const repCloseBtn = repModal ? repModal.querySelector('.modal-close') : null;

      // attach close handlers once (if modal present)
      if (repModal && repCloseBtn && repModal.dataset.boundClose !== '1') {
        repModal.dataset.boundClose = '1';
        repCloseBtn.addEventListener('click', (e) => { e.preventDefault(); repModal.classList.add('hidden'); repModal.setAttribute('aria-hidden','true'); if (repContainer) repContainer.innerHTML = '<p>Chargement du formulaire…</p>'; });
        repModal.addEventListener('click', (e) => { if (e.target === repModal) { repModal.classList.add('hidden'); repModal.setAttribute('aria-hidden','true'); if (repContainer) repContainer.innerHTML = '<p>Chargement du formulaire…</p>'; } });
      }

      // bind report buttons inside the table
      container.querySelectorAll('.js-report-rdv').forEach(btn => {
        if (btn.dataset.boundReport === '1') return;
        btn.dataset.boundReport = '1';

        // initial state: disable if already reporté
        try {
          const initial = (btn.dataset.statut || '').trim();
          if (initial === 'reporte') {
            btn.disabled = true;
            btn.setAttribute('aria-disabled', 'true');
          }
        } catch (e) { /* ignore */ }

        btn.addEventListener('click', async (ev) => {
          ev.preventDefault();
          if (btn.disabled) return;
          const rdvId = btn.dataset.rdvId;
          if (!rdvId) return console.error('rdv id manquant sur le bouton reporter');

          // ensure reporter modal exists
          if (!repModal || !repContainer) {
            alert('Modal de report introuvable (vérifie que le fragment modal est inclus).');
            return;
          }

          const url = `/rdv/reporter/${rdvId}/`;
          try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' });
            if (!res.ok) throw new Error('Impossible de charger le formulaire de report');
            const html = await res.text();
            repContainer.innerHTML = html;
            // open modal
            repModal.classList.remove('hidden');
            repModal.setAttribute('aria-hidden','false');

            // find injected form
            const injectedForm = repContainer.querySelector('form') || repContainer.querySelector('#reporter-rdv-form');
            if (!injectedForm) {
              console.error('Formulaire de report introuvable après injection');
              return;
            }

            // bind inner cancel buttons (if present)
            injectedForm.querySelectorAll('.modal-cancel').forEach(el => {
              el.addEventListener('click', (e) => { e.preventDefault(); repModal.classList.add('hidden'); repModal.setAttribute('aria-hidden','true'); if (repContainer) repContainer.innerHTML = '<p>Chargement du formulaire…</p>'; });
            });

            // submit handler - bind once per injected form (dataset flag)
            if (!injectedForm.dataset.ajaxBoundReport) {
              injectedForm.dataset.ajaxBoundReport = '1';

              injectedForm.addEventListener('submit', async function handleReportSubmit(e) {
                e.preventDefault();
                e.stopPropagation();

                const submitBtn = injectedForm.querySelector('button[type="submit"], #reporter-rdv-submit');
                const origText = submitBtn ? submitBtn.textContent : null;
                if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Report en cours...'; }

                // read fields
                const dateField = injectedForm.querySelector('input[name="nouvelle_date"]');
                const timeField = injectedForm.querySelector('input[name="nouvelle_heure"]');
                const raisonField = injectedForm.querySelector('textarea[name="raison"]');

                const dateVal = dateField ? dateField.value : '';
                const timeVal = timeField ? timeField.value : '';
                const raison = raisonField ? raisonField.value.trim() : '';

                if (!dateVal || !timeVal) {
                  alert('Date et heure requises');
                  if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText || 'Reporter le rendez-vous'; }
                  return;
                }

                let data = null;
                let txt = null;
                try {
                  const postRes = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                      'X-CSRFToken': getCookie('csrftoken'),
                      'Content-Type': 'application/json',
                      'Accept': 'application/json',
                      'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ nouvelle_date: dateVal, nouvelle_heure: timeVal, raison })
                  });

                  txt = await postRes.text().catch(()=>null);
                  try { data = txt ? JSON.parse(txt) : null; } catch(err) { data = null; }

                  // handle errors (400/403/500 etc.)
                  if (!postRes.ok) {
                    // Specific case: conflict
                    if (data && data.conflict) {
                      const c = data.conflict;
                      const message = `Conflit détecté avec RDV #${c.rdv_id} (${c.patient}) de ${new Date(c.start).toLocaleString()} à ${new Date(c.end).toLocaleString()}.`;
                      alert(message);
                    } else if (data && data.error && String(data.error).toLowerCase().includes('annul')) {
                      // example server message: impossible de reporter un rendez-vous annulé
                      alert(data.error);
                      // keep modal open but do not allow normal submit
                    } else if (data && data.errors) {
                      Object.keys(data.errors).forEach(field => {
                        const fieldEl = injectedForm.querySelector(`[name="${field}"]`);
                        if (fieldEl) {
                          let errEl = fieldEl.nextElementSibling;
                          if (!errEl || !errEl.classList.contains('errorlist')) {
                            errEl = document.createElement('div'); errEl.className = 'errorlist';
                            fieldEl.parentNode.insertBefore(errEl, fieldEl.nextSibling);
                          }
                          errEl.innerHTML = data.errors[field].join('<br/>');
                        }
                      });
                    } else {
                      alert((data && (data.error || data.message)) || 'Impossible de reporter le rendez-vous.');
                    }
                    return;
                  }

                  // success
                  if (data && data.success) {
                    // update the row UI
                    const trBtn = container.querySelector(`button.js-confirm-rdv[data-rdv-id="${rdvId}"]`);
                    let tr = trBtn ? trBtn.closest('tr') : container.querySelector(`tr[data-rdv-id="${rdvId}"]`);
                    if (tr) {
                      const statutEl = tr.querySelector('.stat');
                      if (statutEl) {
                        statutEl.textContent = data.statut_label || STATUT_LABELS['reporte'];
                        replaceBadgeClass(statutEl, toBadgeClass(data.statut || 'reporte'));
                        statutEl.classList.remove('updated');
                        void statutEl.offsetWidth;
                        statutEl.classList.add('updated');
                      }
                      // disable report button in row
                      tr.querySelectorAll('.action-btn-report, .js-report-rdv').forEach(el => {
                        try { el.disabled = true; el.setAttribute('aria-disabled', 'true'); } catch (e) {}
                      });
                    }

                    showTransientToast(data.report_initiator === 'medecin' ? 'Rendez-vous déplacé et confirmé.' : 'Rendez-vous reporté.');

                    // close modal and clear
                    repModal.classList.add('hidden');
                    repModal.setAttribute('aria-hidden','true');
                    repContainer.innerHTML = '<p>Chargement du formulaire…</p>';

                    // refresh table for full consistency
                    if (typeof window.fetchRdvsTable === 'function') {
                      setTimeout(()=> window.fetchRdvsTable({}), 300);
                    }
                  } else {
                    alert((data && (data.error || data.message)) || 'Erreur inconnue lors du report.');
                  }

                } catch (err) {
                  console.error('Reporter RDV erreur:', err);
                  if (String(err).toLowerCase().includes('403')) alert('Accès refusé. Vous n\'êtes pas autorisé à reporter ce rendez-vous.');
                  else alert('Erreur lors du report. Réessayez.');
                } finally {
                  if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText || 'Reporter le rendez-vous'; }
                }
              });
            }

          } catch (err) {
            console.error('Impossible de charger le formulaire de report', err);
            alert('Impossible de charger le formulaire. Réessayez.');
          }
        });
      }); // end report buttons forEach

      // -----------------------------
      // fin reporter buttons
      // -----------------------------


      // Bind notifier buttons
      const notifyModal = document.getElementById('notifier-rdv-modal');
      const notifyContainer = document.querySelector('#notifier-modal-form-container');
    
 
      container.querySelectorAll('.js-notifier-rdv').forEach(btn => {
        if (btn.dataset.boundNotifier === '1') return;
        btn.dataset.boundNotifier = '1';

        btn.addEventListener('click', async (ev) => {
          ev.preventDefault();
          const rdvId = btn.dataset.rdvId;
          if (!rdvId) return;

          const notifyModal = document.getElementById('notifier-rdv-modal');
          const notifyContainer = notifyModal ? notifyModal.querySelector('#notifier-modal-form-container') : null;
          if (!notifyModal || !notifyContainer) {
            alert('Modal de notification introuvable.');
            return;
          }

          // Charger le fragment formulaire depuis la vue GET
          const url = `/rdv/notifier/${rdvId}/`;
          try {
            const res = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' }, credentials: 'same-origin' });
            if (!res.ok) throw new Error('Impossible de charger le formulaire de notification.');
            const html = await res.text();
            notifyContainer.innerHTML = html;

            // ouvrir modal
            notifyModal.classList.remove('hidden');
            notifyModal.setAttribute('aria-hidden', 'false');

            // trouver le form injecté
            const injectedForm = notifyContainer.querySelector('form') || notifyContainer.querySelector('#notifier-rdv-form');
            if (!injectedForm) {
              console.error('Formulaire notifier introuvable après injection');
              return;
            }

            // bind cancel bouton
            injectedForm.querySelectorAll('.modal-cancel').forEach(el => {
              el.addEventListener('click', (e) => {
                e.preventDefault();
                notifyModal.classList.add('hidden');
                notifyModal.setAttribute('aria-hidden', 'true');
                notifyContainer.innerHTML = '<p>Chargement du formulaire…</p>';
              });
            });

            // bind submit
            if (!injectedForm.dataset.ajaxBoundNotify) {
              injectedForm.dataset.ajaxBoundNotify = '1';

              injectedForm.addEventListener('submit', async function handleNotifySubmit(e) {
                e.preventDefault();

                const submitBtn = injectedForm.querySelector('button[type="submit"]');
                const origText = submitBtn ? submitBtn.textContent : null;
                if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Envoi…'; }

                const subject = injectedForm.querySelector('[name="subject"]').value.trim();
                const message = injectedForm.querySelector('[name="message"]').value.trim();

                try {
                  const postRes = await fetch(url, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                      'X-CSRFToken': getCookie('csrftoken'),
                      'Content-Type': 'application/json',
                      'Accept': 'application/json',
                      'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ subject, message })
                  });

                  const data = await postRes.json();
                  if (!postRes.ok || !data.success) {
                    alert(data.error || 'Erreur lors de l’envoi de la notification.');
                    return;
                  }

                  showTransientToast('Notification envoyée au patient.');
                  notifyModal.classList.add('hidden');
                  notifyModal.setAttribute('aria-hidden', 'true');
                  notifyContainer.innerHTML = '<p>Chargement du formulaire…</p>';

                } catch (err) {
                  console.error('Erreur envoi notification:', err);
                  alert('Erreur serveur lors de l’envoi de la notification.');
                } finally {
                  if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = origText || 'Envoyer'; }
                }
              });
            }

          } catch (err) {
            console.error('Impossible de charger le formulaire de notification', err);
            alert('Impossible de charger le formulaire. Réessayez.');
          }
        });
      });



    } // end bindTableEvents

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
