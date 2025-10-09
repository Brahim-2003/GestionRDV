// static/rdv/js/admin/users/modal.js
// Gestion centralisée des modales "créer / éditer utilisateur"
// Version finale : robuste, accessible, optimisée

(function () {
  'use strict';

  if (window.__rdv_users_modal_init) return;
  window.__rdv_users_modal_init = true;

  // ==================== UTILITAIRES ====================
  function $(sel, ctx = document) { return ctx.querySelector(sel); }
  function $$(sel, ctx = document) { return Array.from((ctx || document).querySelectorAll(sel)); }

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
  const CSRF_TOKEN = getCookie('csrftoken');

  // ==================== MODAL OPEN / CLOSE ====================
  function openModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.remove('hidden');
    modalEl.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');

    // focus trap: focus premier élément focusable
    requestAnimationFrame(() => {
      const focusable = modalEl.querySelector(
        'input:not([type="hidden"]), button:not([disabled]), select, textarea, a[href], [tabindex]:not([tabindex="-1"])'
      );
      if (focusable) focusable.focus();
      else modalEl.focus();
    });
  }

  function closeModal(modalEl) {
    if (!modalEl) return;
    modalEl.classList.add('hidden');
    modalEl.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
  }

  function getModal(id) {
    return document.getElementById(id);
  }

  // ==================== LOAD FORM VIA AJAX ====================
  async function loadFormInto(url, containerEl) {
    if (!containerEl) {
      console.error('loadFormInto: containerEl est null');
      return;
    }
    containerEl.innerHTML = '<p style="text-align:center; padding:2rem;">Chargement du formulaire…</p>';

    try {
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        credentials: 'same-origin'
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const html = await response.text();
      containerEl.innerHTML = html;

      // Enhance any forms loaded
      enhanceFormSubmits(containerEl);

    } catch (error) {
      console.error('[modal] Erreur lors du chargement du formulaire:', error);
      containerEl.innerHTML = `
        <div style="color:#dc3545; padding:1rem; text-align:center;">
          <p><strong>Impossible de charger le formulaire</strong></p>
          <p style="font-size:0.9rem;">${error.message}</p>
        </div>
      `;
    }
  }

  // ==================== FORM ENHANCEMENTS (AJAX SUBMIT) ====================
  function enhanceFormSubmits(containerEl) {
    if (!containerEl) return;
    const forms = $$('form', containerEl);

    forms.forEach(form => {
      if (form.__rdv_form_bound) return;
      form.__rdv_form_bound = true;

      form.addEventListener('submit', async function (event) {
        event.preventDefault();

        const submitButton = form.querySelector('button[type="submit"]');
        const originalButtonText = submitButton ? submitButton.innerHTML : '';

        try {
          if (submitButton) {
            submitButton.disabled = true;
            submitButton.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Enregistrement…';
          }

          const action = form.getAttribute('action') || window.location.href;
          const method = (form.getAttribute('method') || 'POST').toUpperCase();
          const formData = new FormData(form);

          const response = await fetch(action, {
            method: method,
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'X-CSRFToken': CSRF_TOKEN
            },
            body: formData,
            credentials: 'same-origin'
          });

          const contentType = response.headers.get('Content-Type') || '';

          if (contentType.includes('application/json')) {
            const data = await response.json();
            if (response.ok && (data.status === 'ok' || data.status === 'success')) {
              handleSuccessAfterSave(form, data);
            } else {
              showFormErrors(form, data.errors || data);
            }
            return;
          }

          // HTML response
          const html = await response.text();
          if (response.ok) {
            const tmp = document.createElement('div'); tmp.innerHTML = html;
            const returnedForm = tmp.querySelector('form');
            if (!returnedForm) {
              // likely success (maybe server returned JSON-stringified HTML)
              try {
                const jsonData = JSON.parse(html);
                if (jsonData.status === 'ok' || jsonData.status === 'success') {
                  handleSuccessAfterSave(form, jsonData);
                  return;
                }
              } catch (e) {
                handleSuccessAfterSave(form, { status: 'ok' });
                return;
              }
            } else {
              // form with errors
              containerEl.innerHTML = html;
              enhanceFormSubmits(containerEl);
            }
          } else {
            // error HTTP: show returned body (could be form with errors)
            containerEl.innerHTML = html;
            enhanceFormSubmits(containerEl);
          }

        } catch (error) {
          console.error('[modal] Erreur lors de la soumission:', error);
          showNotification('Erreur réseau. Veuillez réessayer.', 'error');
        } finally {
          if (submitButton) {
            submitButton.disabled = false;
            submitButton.innerHTML = originalButtonText;
          }
        }
      });
    });

    // bind close buttons found in container (if any)
    bindCloseButtons(containerEl);
  }

  function showFormErrors(form, errors) {
    $$('.rdv-field-error', form).forEach(el => el.remove());
    $$('.form-control.is-invalid', form).forEach(el => el.classList.remove('is-invalid'));

    if (!errors || typeof errors !== 'object') {
      showNotification('Erreur lors de la validation du formulaire', 'error');
      return;
    }

    Object.entries(errors).forEach(([fieldName, messages]) => {
      const msgArray = Array.isArray(messages) ? messages : [messages];
      const errorText = msgArray.join(' ');

      if (fieldName === '__all__' || fieldName === 'non_field_errors') {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'rdv-field-error alert alert-danger';
        errorDiv.style.marginBottom = '1rem';
        errorDiv.textContent = errorText;
        form.insertBefore(errorDiv, form.firstChild);
        return;
      }

      const input = form.querySelector(`[name="${fieldName}"]`);
      if (input) {
        input.classList.add('is-invalid');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'rdv-field-error invalid-feedback';
        errorDiv.style.display = 'block';
        errorDiv.textContent = errorText;
        input.insertAdjacentElement('afterend', errorDiv);
      } else {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'rdv-field-error alert alert-warning';
        errorDiv.textContent = `${fieldName}: ${errorText}`;
        form.insertBefore(errorDiv, form.firstChild);
      }
    });

    const firstError = form.querySelector('.rdv-field-error, .is-invalid');
    if (firstError) firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function handleSuccessAfterSave(formElement, data) {
    const modal = formElement.closest('.modal-overlay');
    if (modal) closeModal(modal);

    if (typeof window.fetchTable === 'function') {
      try { window.fetchTable(); }
      catch (e) { setTimeout(() => location.reload(), 500); }
    } else {
      setTimeout(() => location.reload(), 500);
    }

    const message = data.message || 'Opération réussie';
    showNotification(message, 'success');
  }

  function showNotification(message, type = 'info') {
    let container = document.getElementById('notification-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'notification-container';
      container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 10000; max-width: 400px;';
      document.body.appendChild(container);
    }

    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'error' ? 'danger' : type === 'success' ? 'success' : 'info'}`;
    notification.style.cssText = 'margin-bottom: 10px; padding: 1rem; border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.2); animation: slideIn 0.3s ease-out;';
    notification.textContent = message;
    container.appendChild(notification);

    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease-out';
      setTimeout(() => notification.remove(), 300);
    }, 4000);
  }

  function bindCloseButtons(context) {
    const modalOverlay = (context && context.closest && context.closest('.modal-overlay')) || context || document;
    $$('.modal-close, .modal-cancel', modalOverlay).forEach(btn => {
      if (btn.__rdv_close_bound) return;
      btn.__rdv_close_bound = true;
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const modal = btn.closest('.modal-overlay');
        if (modal) closeModal(modal);
      });
    });
  }

  // ==================== DÉLÉGATION GLOBALE ====================
  document.addEventListener('click', function (event) {
    const target = event.target.closest('button, a, [data-action]') || event.target;
    if (!target) return;

    // Ouvrir modale création
    if (target.matches('#open-create-user, [data-open-create-user]')) {
      event.preventDefault();
      const url = target.dataset.formUrl || target.getAttribute('href');
      if (!url) { console.error('URL du formulaire manquante'); return; }
      const modal = getModal('create-user-modal');
      const container = document.getElementById('modal-form-container');
      if (!modal || !container) { console.error('Modale de création introuvable'); return; }
      openModal(modal);
      loadFormInto(url, container);
      return;
    }

    // Éditer : on suppose que le template fournit déjà data-form-url incluant l'id
    if (target.matches('.edit-btn')) {
      event.preventDefault();

      const url = target.dataset.formUrl || target.getAttribute('href');
      if (!url) { console.error('URL du formulaire d\'édition manquante'); return; }

      const modalId = (target.dataset.target || '#edit-user-modal').replace('#', '');
      const containerSelector = target.dataset.container || '#edit-user-modal-form-container';
      const modal = getModal(modalId);
      const container = document.querySelector(containerSelector);

      if (!modal || !container) {
        console.error('Modale d\'édition introuvable:', modalId);
        return;
      }

      openModal(modal);
      loadFormInto(url, container);
      return;
    }

    // click overlay pour fermer modal si on clique sur le fond
    if (target.matches('.modal-overlay') && event.target === target) {
      closeModal(target);
      return;
    }
  });

  // ESC to close
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' || event.keyCode === 27) {
      const openModals = $$('.modal-overlay:not(.hidden)');
      openModals.forEach(modal => closeModal(modal));
    }
  });

  // initialisation
  function initModals() {
    ['create-user-modal', 'edit-user-modal'].forEach(modalId => {
      const modal = getModal(modalId);
      if (modal) {
        if (!modal.classList.contains('hidden')) modal.classList.add('hidden');
        modal.setAttribute('aria-hidden', 'true');
        bindCloseButtons(modal);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModals);
  } else initModals();

  // animations styles (only once)
  if (!document.getElementById('modal-animations')) {
    const style = document.createElement('style');
    style.id = 'modal-animations';
    style.textContent = `
      @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
      @keyframes slideOut { from { transform: translateX(0); opacity: 1; } to { transform: translateX(100%); opacity: 0; } }
      .modal-open { overflow: hidden; }
    `;
    document.head.appendChild(style);
  }

  console.log('✅ modal.js initialisé avec succès');
})();
