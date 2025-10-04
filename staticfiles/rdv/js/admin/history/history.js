// static/rdv/js/patient/history.js
// Gestion de l'historique des rendez-vous - Compatible navigation AJAX

(function() {
  'use strict';

  if (window.__history_module_defined) {
    console.log('history.js: module déjà défini');
    return;
  }
  window.__history_module_defined = true;

  // =============================================================================
  // VARIABLES GLOBALES DU MODULE
  // =============================================================================

  let urls = { list: null, detail: null };
  let searchTimeout = null;
  let boundHandlers = {
    actionTabs: new Map(),
    paginationLinks: new Map(),
    detailLinks: new Map(),
    formSubmit: null,
    resetBtn: null,
    resetEmptyBtn: null,
    searchInput: null,
    popstate: null
  };

  // =============================================================================
  // FONCTIONS UTILITAIRES
  // =============================================================================

  function hasHistoryElements() {
    return !!document.getElementById('history-root');
  }

  function getCurrentPage() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('page') || '1';
  }

  // =============================================================================
  // CHARGEMENT AJAX
  // =============================================================================

  function loadHistoryContent(url) {
    const historyRoot = document.getElementById('history-root');
    if (!historyRoot) return;

    showLoadingState();

    fetch(url, {
      method: 'GET',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => {
      if (!response.ok) throw new Error('Erreur réseau');
      return response.text();
    })
    .then(html => {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      
      const newContent = tempDiv.querySelector('#history-root');
      if (newContent) {
        historyRoot.innerHTML = newContent.innerHTML;
        window.history.pushState({}, '', url);
        
        // Réinitialiser les event listeners
        cleanup();
        initEventListeners();
      }
    })
    .catch(error => {
      console.error('Erreur chargement historique:', error);
      showErrorState();
    });
  }

  function showLoadingState() {
    const historyList = document.querySelector('.history-list');
    if (historyList) {
      historyList.innerHTML = `
        <div class="loading-state" style="text-align: center; padding: 3rem;">
          <i class='bx bx-loader-alt bx-spin' style="font-size: 3rem; color: #667eea;"></i>
          <p style="margin-top: 1rem; color: #888;">Chargement...</p>
        </div>
      `;
    }
  }

  function showErrorState() {
    const historyList = document.querySelector('.history-list');
    if (historyList) {
      historyList.innerHTML = `
        <div class="error-state" style="text-align: center; padding: 3rem; background: white; border-radius: 12px;">
          <i class='bx bx-error-circle' style="font-size: 3rem; color: #ef4444;"></i>
          <h3 style="margin-top: 1rem; color: #555;">Erreur de chargement</h3>
          <p style="color: #888; margin-bottom: 1.5rem;">Une erreur est survenue.</p>
          <button onclick="location.reload()" class="btn btn-primary">
            <i class='bx bx-refresh'></i> Réessayer
          </button>
        </div>
      `;
    }
  }

  // =============================================================================
  // GESTION DES ONGLETS
  // =============================================================================

  function initActionTabs() {
    const actionTabs = document.querySelectorAll('.action-tab');
    
    actionTabs.forEach(tab => {
      if (tab.dataset.tabBound === '1') return;
      tab.dataset.tabBound = '1';

      const handler = function() {
        const action = this.dataset.action;
        
        actionTabs.forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        
        const currentUrl = new URL(window.location.href);
        
        if (action === 'all') {
          currentUrl.searchParams.delete('action');
        } else {
          currentUrl.searchParams.set('action', action);
        }
        
        currentUrl.searchParams.set('page', '1');
        loadHistoryContent(currentUrl.toString());
      };

      tab.addEventListener('click', handler);
      boundHandlers.actionTabs.set(tab, handler);
    });
  }

  // =============================================================================
  // GESTION DES FILTRES
  // =============================================================================

  function initFiltersForm() {
    const filtersForm = document.getElementById('history-filters');
    if (!filtersForm || filtersForm.dataset.formBound === '1') return;
    
    filtersForm.dataset.formBound = '1';

    boundHandlers.formSubmit = function(e) {
      e.preventDefault();
      
      const formData = new FormData(filtersForm);
      const params = new URLSearchParams(formData);
      
      const activeTab = document.querySelector('.action-tab.active');
      if (activeTab && activeTab.dataset.action !== 'all') {
        params.set('action', activeTab.dataset.action);
      }
      
      params.set('page', '1');
      const url = `${urls.list}?${params.toString()}`;
      
      loadHistoryContent(url);
    };

    filtersForm.addEventListener('submit', boundHandlers.formSubmit);
  }

  function initResetButtons() {
    const resetBtn = document.getElementById('reset-filters');
    const resetEmptyBtn = document.getElementById('reset-empty');

    const resetFilters = function() {
      const filtersForm = document.getElementById('history-filters');
      if (filtersForm) filtersForm.reset();
      
      document.querySelectorAll('.action-tab').forEach(t => t.classList.remove('active'));
      const allTab = document.querySelector('.action-tab[data-action="all"]');
      if (allTab) allTab.classList.add('active');
      
      loadHistoryContent(urls.list);
    };

    if (resetBtn && !resetBtn.dataset.resetBound) {
      resetBtn.dataset.resetBound = '1';
      boundHandlers.resetBtn = resetFilters;
      resetBtn.addEventListener('click', boundHandlers.resetBtn);
    }

    if (resetEmptyBtn && !resetEmptyBtn.dataset.resetBound) {
      resetEmptyBtn.dataset.resetBound = '1';
      boundHandlers.resetEmptyBtn = resetFilters;
      resetEmptyBtn.addEventListener('click', boundHandlers.resetEmptyBtn);
    }
  }

  // =============================================================================
  // RECHERCHE TEMPS RÉEL
  // =============================================================================

  function initSearchInput() {
    const searchInput = document.querySelector('.search-input');
    if (!searchInput || searchInput.dataset.searchBound === '1') return;

    searchInput.dataset.searchBound = '1';

    boundHandlers.searchInput = function() {
      clearTimeout(searchTimeout);
      
      searchTimeout = setTimeout(() => {
        const filtersForm = document.getElementById('history-filters');
        if (filtersForm) {
          const submitEvent = new Event('submit', { 
            bubbles: true, 
            cancelable: true 
          });
          filtersForm.dispatchEvent(submitEvent);
        }
      }, 500);
    };

    searchInput.addEventListener('input', boundHandlers.searchInput);
  }

  // =============================================================================
  // PAGINATION
  // =============================================================================

  function initPaginationLinks() {
    const paginationLinks = document.querySelectorAll('.pagination-btn');
    
    paginationLinks.forEach(link => {
      if (link.dataset.paginationBound === '1') return;
      link.dataset.paginationBound = '1';

      const handler = function(e) {
        e.preventDefault();
        const url = this.getAttribute('href');
        
        window.scrollTo({ top: 0, behavior: 'smooth' });
        loadHistoryContent(url);
      };

      link.addEventListener('click', handler);
      boundHandlers.paginationLinks.set(link, handler);
    });
  }

  // =============================================================================
  // LIENS DÉTAIL
  // =============================================================================

  function initDetailLinks() {
    const detailLinks = document.querySelectorAll('.view-detail');
    
    detailLinks.forEach(link => {
      if (link.dataset.detailBound === '1') return;
      link.dataset.detailBound = '1';

      const handler = function(e) {
        // Comportement par défaut : navigation normale
      };

      link.addEventListener('click', handler);
      boundHandlers.detailLinks.set(link, handler);
    });
  }

  // =============================================================================
  // ANIMATIONS
  // =============================================================================

  function animateHistoryItems() {
    const items = document.querySelectorAll('.history-item');
    
    items.forEach((item, index) => {
      item.style.opacity = '0';
      item.style.transform = 'translateY(20px)';
      
      setTimeout(() => {
        item.style.transition = 'all 0.4s ease';
        item.style.opacity = '1';
        item.style.transform = 'translateY(0)';
      }, index * 50);
    });
  }

  // =============================================================================
  // INITIALISATION COMPLÈTE
  // =============================================================================

  function initEventListeners() {
    const historyRoot = document.getElementById('history-root');
    if (!historyRoot) return;

    // Récupérer les URLs
    urls.list = historyRoot.dataset.urlList;
    urls.detail = historyRoot.dataset.urlDetail;

    initActionTabs();
    initFiltersForm();
    initResetButtons();
    initSearchInput();
    initPaginationLinks();
    initDetailLinks();
    animateHistoryItems();

    console.log('Event listeners historique initialisés');
  }

  // =============================================================================
  // NETTOYAGE
  // =============================================================================

  function cleanup() {
    // Action tabs
    boundHandlers.actionTabs.forEach((handler, tab) => {
      tab.removeEventListener('click', handler);
      tab.dataset.tabBound = '';
    });
    boundHandlers.actionTabs.clear();

    // Pagination links
    boundHandlers.paginationLinks.forEach((handler, link) => {
      link.removeEventListener('click', handler);
      link.dataset.paginationBound = '';
    });
    boundHandlers.paginationLinks.clear();

    // Detail links
    boundHandlers.detailLinks.forEach((handler, link) => {
      link.removeEventListener('click', handler);
      link.dataset.detailBound = '';
    });
    boundHandlers.detailLinks.clear();

    // Form
    const filtersForm = document.getElementById('history-filters');
    if (filtersForm && boundHandlers.formSubmit) {
      filtersForm.removeEventListener('submit', boundHandlers.formSubmit);
      filtersForm.dataset.formBound = '';
    }

    // Reset buttons
    const resetBtn = document.getElementById('reset-filters');
    if (resetBtn && boundHandlers.resetBtn) {
      resetBtn.removeEventListener('click', boundHandlers.resetBtn);
      resetBtn.dataset.resetBound = '';
    }

    const resetEmptyBtn = document.getElementById('reset-empty');
    if (resetEmptyBtn && boundHandlers.resetEmptyBtn) {
      resetEmptyBtn.removeEventListener('click', boundHandlers.resetEmptyBtn);
      resetEmptyBtn.dataset.resetBound = '';
    }

    // Search input
    const searchInput = document.querySelector('.search-input');
    if (searchInput && boundHandlers.searchInput) {
      searchInput.removeEventListener('input', boundHandlers.searchInput);
      searchInput.dataset.searchBound = '';
    }

    // Clear timeout
    if (searchTimeout) {
      clearTimeout(searchTimeout);
      searchTimeout = null;
    }
  }

  // =============================================================================
  // FONCTION PRINCIPALE D'INITIALISATION
  // =============================================================================

  function initHistoryModule() {
    console.log('🔄 initHistoryModule appelé');

    if (!hasHistoryElements()) {
      console.log('⚠️ Éléments historique non trouvés');
      return;
    }

    console.log('✅ Initialisation module historique');

    cleanup();
    initEventListeners();

    // Popstate handler
    if (!boundHandlers.popstate) {
      boundHandlers.popstate = () => location.reload();
      window.addEventListener('popstate', boundHandlers.popstate);
    }

    console.log('✅ Module historique initialisé');
  }

  function destroyHistoryModule() {
    console.log('🧹 Nettoyage module historique');

    cleanup();

    if (boundHandlers.popstate) {
      window.removeEventListener('popstate', boundHandlers.popstate);
      boundHandlers.popstate = null;
    }

    console.log('✅ Module historique nettoyé');
  }

  // =============================================================================
  // EXPOSITION GLOBALE
  // =============================================================================

  window.initHistoryModule = initHistoryModule;
  window.destroyHistoryModule = destroyHistoryModule;
  window.reinitHistoryModule = function() {
    destroyHistoryModule();
    initHistoryModule();
  };

  // =============================================================================
  // AUTO-INITIALISATION
  // =============================================================================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      if (hasHistoryElements()) initHistoryModule();
    });
  } else {
    if (hasHistoryElements()) {
      setTimeout(() => initHistoryModule(), 0);
    }
  }

  // Événement déchargement
  document.addEventListener('fragment:unloaded', destroyHistoryModule);

  console.log('✅ history.js chargé (exposé window.initHistoryModule)');

})();