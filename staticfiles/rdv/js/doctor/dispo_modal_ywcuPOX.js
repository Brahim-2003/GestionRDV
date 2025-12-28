// static/rdv/js/doctor/dispo_modal.js
// Gestion centralisée des modals Create / Edit pour disponibilités
// Version robuste avec gestion d'erreurs améliorée, cleanup automatique et meilleure UX

(function () {
  'use strict';
  
  if (window.__dispo_modal_installed) return;
  window.__dispo_modal_installed = true;
  
  console.log("dispo_modal.js: Initialisation");

  // =============================================================================
  // UTILITAIRES
  // =============================================================================
  
  const utils = {
    // Sélecteur sécurisé
    q: (selector) => document.querySelector(selector),
    qa: (selector) => Array.from(document.querySelectorAll(selector)),
    
    // Cookie helper
    getCookie(name) {
      if (!document.cookie) return null;
      let value = null;
      document.cookie.split(";").forEach(cookie => {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          value = decodeURIComponent(cookie.slice(name.length + 1));
        }
      });
      return value;
    },

    // Logging sécurisé
    safeLog(...args) {
      try { 
        console.log(...args); 
      } catch (e) { 
        /* ignore */ 
      }
    },

    // Vérification d'élément déjà traité
    onceDataset(element, key) {
      if (!element) return false;
      if (element.dataset[key] === "1") return false;
      element.dataset[key] = "1";
      return true;
    },

    // Affichage des erreurs inline
    showInlineErrors(formEl, errors) {
      if (!formEl) return;
      
      // Supprimer les anciennes erreurs
      const previousErrors = formEl.querySelector('.form-errors');
      if (previousErrors) previousErrors.remove();
      
      if (!errors) return;

      const errorBox = document.createElement('div');
      errorBox.className = 'form-errors alert alert-error';
      errorBox.setAttribute('role', 'alert');
      
      // Styles inline pour assurer l'affichage
      Object.assign(errorBox.style, {
        color: '#b91c1c',
        backgroundColor: '#fef2f2',
        border: '1px solid #fecaca',
        padding: '12px 16px',
        borderRadius: '6px',
        margin: '0 0 16px 0',
        fontSize: '14px'
      });

      if (errors && typeof errors === 'object' && !Array.isArray(errors)) {
        // Erreurs par champs
        const errorList = document.createElement('ul');
        errorList.style.margin = '0';
        errorList.style.paddingLeft = '20px';
        
        Object.entries(errors).forEach(([field, messages]) => {
          const listItem = document.createElement('li');
          const fieldLabel = (field === '__all__' || field === 'non_field_errors') ? '' : `${field}: `;
          const messageText = Array.isArray(messages) ? messages.join(', ') : messages;
          listItem.innerHTML = `<strong>${fieldLabel}</strong>${messageText}`;
          errorList.appendChild(listItem);
        });
        
        errorBox.appendChild(errorList);
      } else if (Array.isArray(errors)) {
        // Liste d'erreurs
        const errorList = document.createElement('ul');
        errorList.style.margin = '0';
        errorList.style.paddingLeft = '20px';
        
        errors.forEach(error => {
          const listItem = document.createElement('li');
          listItem.textContent = String(error);
          errorList.appendChild(listItem);
        });
        
        errorBox.appendChild(errorList);
      } else {
        // Message simple
        errorBox.textContent = String(errors);
      }

      // Insérer au début du formulaire
      formEl.insertBefore(errorBox, formEl.firstChild);
      
      // Auto-scroll vers l'erreur si nécessaire
      errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    },

    // Animation de soumission
    setSubmitLoading(form, loading = true) {
      if (!form) return;
      
      const submitBtn = form.querySelector('button[type="submit"]');
      if (!submitBtn) return;

      if (loading) {
        submitBtn.disabled = true;
        submitBtn.dataset.originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Enregistrement...';
      } else {
        submitBtn.disabled = false;
        if (submitBtn.dataset.originalText) {
          submitBtn.innerHTML = submitBtn.dataset.originalText;
          delete submitBtn.dataset.originalText;
        }
      }
    }
  };

  // =============================================================================
  // GESTIONNAIRE DE CHARGEMENT DE FRAGMENTS
  // =============================================================================
  
  async function loadFragmentInto(url, container) {
    if (!container) {
      console.warn('loadFragmentInto: container manquant');
      return;
    }
    
    // Indicateur de chargement
    container.innerHTML = `
      <div class="loading-container" style="text-align: center; padding: 20px; color: #3b82f6;">
        <i class='bx bx-loader-alt bx-spin' style="font-size: 24px; margin-bottom: 8px;"></i>
        <p>Chargement du formulaire...</p>
      </div>
    `;

    try {
      const response = await fetch(url, { 
        headers: { "X-Requested-With": "XMLHttpRequest" }
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const text = await response.text();

      // Traitement du contenu reçu
      let fragment = text;
      
      // Si c'est une page complète, extraire le contenu pertinent
      if (text.includes('<html') || text.includes('<body') || text.includes('id="ajax-content"')) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = text;
        
        // Chercher le contenu dans l'ordre de préférence
        const contentSelectors = ['#ajax-content', '.modal-body', 'form', 'body'];
        let extractedContent = null;
        
        for (const selector of contentSelectors) {
          extractedContent = tempDiv.querySelector(selector);
          if (extractedContent) break;
        }
        
        fragment = extractedContent ? extractedContent.innerHTML : text;
      }

      // Injecter le contenu
      container.innerHTML = fragment;

      // Initialiser les composants dans le fragment
      await initializeFragmentContent(container);

    } catch (error) {
      console.error("loadFragmentInto error:", error);
      container.innerHTML = `
        <div class="error-container" style="text-align: center; padding: 20px; color: #dc2626; background: #fef2f2; border-radius: 8px;">
          <i class='bx bx-error-circle' style="font-size: 24px; margin-bottom: 8px;"></i>
          <p><strong>Impossible de charger le formulaire</strong></p>
          <p style="font-size: 14px; margin: 8px 0;">${error.message}</p>
          <button onclick="window.location.reload()" class="btn-secondary btn-sm" style="margin-top: 8px;">
            <i class='bx bx-refresh'></i> Recharger la page
          </button>
        </div>
      `;
    }
  }

  // =============================================================================
  // INITIALISATION DU CONTENU DE FRAGMENT
  // =============================================================================
  
  async function initializeFragmentContent(container) {
    if (!container) return;

    // Initialiser flatpickr pour les champs de date/heure
    if (window.flatpickr) {
      try {
        // Champs de date
        const dateInputs = container.querySelectorAll('input[type="date"], input.flat-date, .date-input');
        if (dateInputs.length) {
          flatpickr(dateInputs, { 
            dateFormat: "Y-m-d", 
            allowInput: true,
            locale: 'fr'
          });
        }

        // Champs d'heure
        const timeInputs = container.querySelectorAll('input[type="time"], input.flat-time, .time-input');
        if (timeInputs.length) {
          flatpickr(timeInputs, { 
            enableTime: true, 
            noCalendar: true, 
            dateFormat: "H:i", 
            allowInput: true,
            time_24hr: true
          });
        }
      } catch (error) { 
        console.warn("flatpickr init failed:", error); 
      }
    }

    // Bind le formulaire principal
    bindModalForm(container);
  }

  // =============================================================================
  // GESTIONNAIRE DE FORMULAIRE MODAL
  // =============================================================================
  
  function bindModalForm(container) {
    if (!container) {
      console.warn('bindModalForm: container manquant');
      return;
    }

    const form = container.querySelector('form[data-ajax="1"]');
    if (!form) {
      utils.safeLog('Aucun formulaire AJAX trouvé dans le container');
      return;
    }

    // Éviter les doubles bindings
    if (form.dataset.bound === "1") {
      utils.safeLog('Formulaire déjà bindé');
      return;
    }
    form.dataset.bound = "1";

    utils.safeLog('Binding formulaire modal:', form.id || 'sans-id');

    // Gestionnaire de soumission
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      event.stopPropagation();

      utils.safeLog('Soumission formulaire modal');

      // Nettoyer les anciennes erreurs
      utils.showInlineErrors(form, null);
      utils.setSubmitLoading(form, true);

      try {
        await handleFormSubmission(form, container);
      } catch (error) {
        console.error('Erreur soumission formulaire:', error);
        handleSubmissionError(form, error);
      } finally {
        utils.setSubmitLoading(form, false);
      }
    });

    // Gestionnaire pour les boutons d'annulation
    const cancelButtons = container.querySelectorAll('.modal-cancel, .btn-cancel');
    cancelButtons.forEach(btn => {
      if (utils.onceDataset(btn, 'cancelBound')) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          closeAllModals();
        });
      }
    });
  }

  // =============================================================================
  // GESTION DE SOUMISSION DE FORMULAIRE
  // =============================================================================
  
  async function handleFormSubmission(form, container) {
    const url = form.action;
    const method = (form.method || 'POST').toUpperCase();
    const formData = new FormData(form);

    const headers = {
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': utils.getCookie('csrftoken')
    };

    // Utiliser la fonction globale ajaxSubmitForm si disponible
    if (typeof window.ajaxSubmitForm === 'function') {
      return await window.ajaxSubmitForm(form, container, handleSuccessResponse);
    }

    // Fallback: implémentation locale
    const response = await fetch(url, {
      method,
      body: formData,
      headers,
      credentials: 'same-origin'
    });

    const contentType = response.headers.get('content-type') || '';

    if (contentType.includes('application/json')) {
      const jsonData = await response.json();
      
      if (response.ok && (jsonData.status === 'ok' || jsonData.success === true)) {
        handleSuccessResponse(jsonData);
        return jsonData;
      } else {
        throw {
          type: 'validation',
          errors: jsonData.errors || jsonData,
          response
        };
      }
    } else {
      // Réponse HTML
      const htmlData = await response.text();
      
      if (response.ok) {
        // Succès avec HTML (rare)
        if (htmlData.includes('<form')) {
          // Nouveau formulaire avec erreurs probablement
          container.innerHTML = htmlData;
          await initializeFragmentContent(container);
        } else {
          // Succès, fermer le modal
          handleSuccessResponse({});
        }
        return htmlData;
      } else {
        throw {
          type: 'html',
          message: `Erreur serveur ${response.status}`,
          response
        };
      }
    }
  }

  // =============================================================================
  // GESTION DES RÉPONSES
  // =============================================================================
  
  function handleSuccessResponse(data) {
    utils.safeLog('Formulaire soumis avec succès:', data);
    
    // Fermer tous les modals
    closeAllModals();
    
    // Dispatch événement de succès
    utils.safeDispatchEvent('dispo:saved', data);
    
    // Notification de succès (optionnelle)
    showSuccessNotification('Disponibilité sauvegardée avec succès');
  }

  function handleSubmissionError(form, error) {
    utils.safeLog('Erreur soumission:', error);

    if (error.type === 'validation' && error.errors) {
      // Erreurs de validation
      utils.showInlineErrors(form, error.errors);
    } else if (error.type === 'json' && error.payload) {
      // Erreurs JSON du serveur
      utils.showInlineErrors(form, error.payload.errors || error.payload);
    } else {
      // Erreurs génériques
      const message = error.message || 'Erreur réseau - impossible de soumettre le formulaire';
      utils.showInlineErrors(form, message);
    }
  }

  // =============================================================================
  // GESTION DES MODALS
  // =============================================================================
  
  function closeAllModals() {
    const modals = ['#create-dispo-modal', '#edit-dispo-modal'];
    modals.forEach(selector => {
      const modal = utils.q(selector);
      if (modal) {
        modal.classList.add('hidden');
        // Nettoyer le contenu pour éviter les fuites mémoire
        const container = modal.querySelector('#modal-form-container, #edit-modal-form-container');
        if (container) {
          setTimeout(() => {
            container.innerHTML = '<p>Chargement...</p>';
          }, 300); // Délai pour l'animation de fermeture
        }
      }
    });
  }

  function openCreateModal(formUrl) {
    const modal = utils.q('#create-dispo-modal');
    const container = utils.q('#modal-form-container');
    
    if (!modal || !container) {
      console.warn('Modal de création non trouvée');
      if (formUrl) window.location = formUrl;
      return;
    }

    modal.classList.remove('hidden');
    
    if (formUrl) {
      loadFragmentInto(formUrl, container);
    } else {
      container.innerHTML = '<p>URL du formulaire manquante.</p>';
    }
  }

  function openEditModal(editUrl) {
    const modal = utils.q('#edit-dispo-modal');
    const container = utils.q('#edit-modal-form-container');
    
    if (!modal || !container) {
      console.warn('Modal d\'édition non trouvée, fallback vers modal de création');
      // Fallback vers le modal de création
      const fallbackModal = utils.q('#create-dispo-modal');
      const fallbackContainer = utils.q('#modal-form-container');
      
      if (fallbackModal && fallbackContainer) {
        fallbackModal.classList.remove('hidden');
        if (editUrl) loadFragmentInto(editUrl, fallbackContainer);
        return;
      }
      
      if (editUrl) window.location = editUrl;
      return;
    }

    modal.classList.remove('hidden');
    
    if (editUrl) {
      loadFragmentInto(editUrl, container);
    } else {
      container.innerHTML = '<p>URL d\'édition manquante.</p>';
    }
  }

  // =============================================================================
  // GESTIONNAIRE D'ÉVÉNEMENTS GLOBAUX
  // =============================================================================
  
  function setupGlobalEventListeners() {
    if (window.__dispo_modal_events_bound) return;
    window.__dispo_modal_events_bound = true;

    // Délégation d'événements globale
    document.addEventListener('click', function (event) {
      const target = event.target.closest('button, a');
      if (!target) return;

      // Ouverture modal de création
      if (target.id === 'open-create-dispo' || target.classList.contains('open-create-dispo')) {
        event.preventDefault();
        const formUrl = target.dataset.formUrl || target.getAttribute('href');
        openCreateModal(formUrl);
        return;
      }

      // Ouverture modal d'édition
      if (target.classList.contains('action-btn-edit') || 
          target.classList.contains('edit-btn') || 
          target.classList.contains('slot-edit-btn')) {
        event.preventDefault();
        
        if (target.dataset.busy === '1') return;
        target.dataset.busy = '1';
        
        const editUrl = target.dataset.editUrl || target.dataset.url || target.getAttribute('href');
        openEditModal(editUrl);
        
        setTimeout(() => delete target.dataset.busy, 500);
        return;
      }

      // Fermeture des modals
      if (target.classList.contains('modal-close') || 
          target.classList.contains('modal-cancel') ||
          target.classList.contains('btn-cancel')) {
        event.preventDefault();
        closeAllModals();
        return;
      }

      // Fermeture par clic sur l'overlay
      if (target.classList.contains('modal-overlay')) {
        closeAllModals();
        return;
      }
    });

    // Fermeture par échap
    document.addEventListener('keydown', function(event) {
      if (event.key === 'Escape') {
        const openModal = utils.q('.modal-overlay:not(.hidden)');
        if (openModal) {
          closeAllModals();
        }
      }
    });

    // Écouter les événements de sauvegarde pour fermer les modals
    document.addEventListener('dispo:saved', function() {
      closeAllModals();
    });
  }

  // =============================================================================
  // UTILITAIRES D'AFFICHAGE
  // =============================================================================
  
  function showSuccessNotification(message) {
    // Créer une notification temporaire
    const notification = document.createElement('div');
    notification.className = 'success-notification';
    
    Object.assign(notification.style, {
      position: 'fixed',
      top: '20px',
      right: '20px',
      backgroundColor: '#10b981',
      color: 'white',
      padding: '12px 20px',
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(16, 185, 129, 0.3)',
      zIndex: '9999',
      fontSize: '14px',
      fontWeight: '500',
      transform: 'translateX(100%)',
      transition: 'transform 0.3s ease'
    });
    
    notification.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px;">
        <i class="bx bxs-check-circle"></i>
        <span>${message}</span>
      </div>
    `;
    
    document.body.appendChild(notification);
    
    // Animation d'entrée
    setTimeout(() => {
      notification.style.transform = 'translateX(0)';
    }, 10);
    
    // Suppression automatique
    setTimeout(() => {
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, 3000);
  }

  function safeDispatchEvent(eventName, detail = {}) {
    try {
      const event = new CustomEvent(eventName, { 
        detail, 
        bubbles: true, 
        cancelable: true 
      });
      document.dispatchEvent(event);
      utils.safeLog(`Event dispatched: ${eventName}`, detail);
    } catch (error) {
      console.warn(`Erreur dispatch event ${eventName}:`, error);
    }
  }

  // Ajouter à utils
  utils.safeDispatchEvent = safeDispatchEvent;

  // =============================================================================
  // INITIALISATION ET EXPOSITION GLOBALE
  // =============================================================================
  
  function initializeModal() {
    utils.safeLog('Initialisation du gestionnaire de modals');
    
    setupGlobalEventListeners();
    
    // Bind les formulaires déjà présents
    document.querySelectorAll('form[data-ajax="1"]').forEach(form => {
      const container = form.closest('[data-ajax-container]') || form.parentElement;
      bindModalForm(container);
    });
    
    utils.safeLog('Gestionnaire de modals initialisé');
  }

  // Exposition des fonctions globales
  window.loadDispoFragmentInto = window.loadDispoFragmentInto || loadFragmentInto;
  window.bindModalForm = window.bindModalForm || bindModalForm;
  
  // Alias pour compatibilité
  window.bindDispoForm = window.bindDispoForm || bindModalForm;

  // Fonctions d'ouverture de modals pour usage externe
  window.openCreateDispoModal = openCreateModal;
  window.openEditDispoModal = openEditModal;
  window.closeDispoModals = closeAllModals;

  // =============================================================================
  // AUTO-INITIALISATION
  // =============================================================================
  
  // Initialisation automatique
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeModal);
  } else {
    // DOM déjà chargé
    setTimeout(initializeModal, 0);
  }

  // =============================================================================
  // GESTION DES ERREURS GLOBALES
  // =============================================================================
  
  // Gestionnaire d'erreurs pour les promesses non catchées
  window.addEventListener('unhandledrejection', function(event) {
    if (event.reason && event.reason.message && event.reason.message.includes('dispo')) {
      console.error('Erreur non gérée dans dispo_modal:', event.reason);
      // Empêcher l'affichage par défaut dans la console
      event.preventDefault();
    }
  });

  console.log('dispo_modal.js: Prêt et opérationnel');

})();