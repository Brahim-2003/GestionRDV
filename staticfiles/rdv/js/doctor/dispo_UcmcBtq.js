// static/rdv/js/doctor/dispo.js
// Version finale corrigée : gestion complète des disponibilités
// ✅ Compatible avec navigation AJAX via base.js

(function () {
  'use strict';
  
  console.log('📧 dispo.js: Chargement du module');

  // =============================================================================
  // UTILITAIRES
  // =============================================================================
  
  const utils = {
    getCookie(name) {
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
    },

    debounce(func, wait = 300) {
      let timeout;
      return function executedFunction(...args) {
        const later = () => {
          clearTimeout(timeout);
          func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
      };
    },

    showLoading(element, show = true) {
      if (!element) return;
      const loader = element.querySelector('.loading-indicator, #table-loading, #weekly-loading');
      const content = element.querySelector('.table-wrapper, .calendar-grid');
      
      if (loader) {
        loader.classList.toggle('hidden', !show);
      }
      if (content) {
        content.style.opacity = show ? '0.5' : '1';
      }
    },

    showError(element, message = 'Une erreur est survenue', show = true) {
      if (!element) return;
      const errorEl = element.querySelector('.error-message, #table-error');
      const errorText = element.querySelector('#error-text');
      
      if (errorEl) {
        errorEl.classList.toggle('hidden', !show);
        if (errorText && message) {
          errorText.textContent = message;
        }
      }
    },

    safeDispatchEvent(eventName, detail = {}) {
      try {
        document.dispatchEvent(new CustomEvent(eventName, { detail }));
      } catch (e) {
        console.warn(`Erreur dispatch event ${eventName}:`, e);
      }
    },

    animateElement(element, animationClass, duration = 300) {
      if (!element) return Promise.resolve();
      
      return new Promise(resolve => {
        element.classList.add(animationClass);
        setTimeout(() => {
          element.classList.remove(animationClass);
          resolve();
        }, duration);
      });
    }
  };

  // =============================================================================
  // GESTIONNAIRE D'ONGLETS
  // =============================================================================
  
  class TabManager {
    constructor() {
      this.activeTab = 'hebdo';
      this.boundClickHandler = null;
      this.init();
    }

    init() {
      this.bindEvents();
      this.setInitialTab();
    }

    bindEvents() {
      if (document.body.dataset.tabsBound === '1') return;
      document.body.dataset.tabsBound = '1';

      this.boundClickHandler = (e) => {
        const tabButton = e.target.closest('.tab-button');
        if (tabButton && tabButton.dataset.tab) {
          e.preventDefault();
          this.switchTab(tabButton.dataset.tab);
        }
      };

      document.addEventListener('click', this.boundClickHandler);
    }

    setInitialTab() {
      const urlParams = new URLSearchParams(window.location.search);
      const tabFromUrl = urlParams.get('tab');
      if (tabFromUrl && ['hebdo', 'ponctuel'].includes(tabFromUrl)) {
        this.activeTab = tabFromUrl;
      }
      this.updateUI();
    }

    switchTab(tabName) {
      if (this.activeTab === tabName) return;
      
      console.log(`📄 Changement d'onglet: ${this.activeTab} → ${tabName}`);
      this.activeTab = tabName;
      this.updateUI();
      this.updateURL();
      
      if (tabName === 'ponctuel') {
        this.loadPonctuelContent();
      } else if (tabName === 'hebdo') {
        this.refreshWeeklyCalendar();
      }
    }

    updateUI() {
      document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === this.activeTab);
      });

      document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${this.activeTab}`);
      });
    }

    updateURL() {
      const url = new URL(window.location);
      if (this.activeTab !== 'hebdo') {
        url.searchParams.set('tab', this.activeTab);
      } else {
        url.searchParams.delete('tab');
      }
      window.history.replaceState(null, '', url);
    }

    loadPonctuelContent() {
      if (window.ponctuelTableManager) {
        window.ponctuelTableManager.fetchTable({ page: 1 });
      }
    }

    refreshWeeklyCalendar() {
      if (window.weeklyDispoManager) {
        window.weeklyDispoManager.refreshWeeklyCalendar().catch(console.warn);
      }
    }

    destroy() {
      if (this.boundClickHandler) {
        document.removeEventListener('click', this.boundClickHandler);
        this.boundClickHandler = null;
      }
      document.body.dataset.tabsBound = '';
    }
  }

  // =============================================================================
  // GESTIONNAIRE AJAX FORMS
  // =============================================================================
  
  async function ajaxSubmitForm(form, container, onSuccess) {
    const url = form.action;
    const method = (form.method || 'POST').toUpperCase();
    const data = new FormData(form);

    const headers = { 
      'X-Requested-With': 'XMLHttpRequest',
      'X-CSRFToken': utils.getCookie('csrftoken')
    };

    try {
      const res = await fetch(url, {
        method,
        body: data,
        headers,
        credentials: 'same-origin'
      });

      const contentType = res.headers.get('content-type') || '';

      if (contentType.includes('application/json')) {
        const json = await res.json();
        if (res.ok && (json.status === 'ok' || json.success === true)) {
          if (typeof onSuccess === 'function') onSuccess(json);
          return json;
        } else {
          throw { type: 'json', payload: json, response: res };
        }
      } else {
        const text = await res.text();
        if (container) {
          container.innerHTML = text;
          if (typeof window.bindModalForm === 'function') {
            window.bindModalForm(container);
          }
        }
        if (!res.ok) {
          throw { type: 'html', payload: text, response: res };
        }
        return text;
      }
    } catch (err) {
      console.error('ajaxSubmitForm error:', err);
      throw err;
    }
  }

  // =============================================================================
  // GESTIONNAIRE TABLE PONCTUEL
  // =============================================================================
  
  class PonctuelTableManager {
    constructor() {
      this.container = document.getElementById('ponctuel-content');
      this.tableContainer = null;
      this.filters = {};
      this.currentPage = 1;
      this.isLoading = false;
      this.boundClickHandler = null;
      this.boundJourHandler = null;
      this.boundDateHandler = null;
      this.boundClearHandler = null;
      this.boundRetryHandler = null;
      
      if (this.container) {
        this.init();
      }
    }

    init() {
      this.tableContainer = this.container.querySelector('#dispo-table-container');
      if (!this.tableContainer) return;

      this.bindEvents();
      this.initFilters();
      
      if (!this.tableContainer.querySelector('tbody tr:not(.empty-row)')) {
        this.fetchTable({ page: 1 });
      }
    }

    bindEvents() {
      if (this.container.dataset.eventsBound === '1') return;
      this.container.dataset.eventsBound = '1';

      this.boundClickHandler = this.handleClick.bind(this);
      this.container.addEventListener('click', this.boundClickHandler);
      
      const jourSelect = document.getElementById('jour-select');
      const dateInput = document.getElementById('date-input');
      const clearBtn = document.getElementById('clear-filters');

      if (jourSelect && jourSelect.dataset.bound !== '1') {
        jourSelect.dataset.bound = '1';
        this.boundJourHandler = utils.debounce(() => {
          this.filters.jour = jourSelect.value;
          this.fetchTable({ page: 1 });
        }, 200);
        jourSelect.addEventListener('change', this.boundJourHandler);
      }

      if (dateInput && dateInput.dataset.bound !== '1') {
        dateInput.dataset.bound = '1';
        this.boundDateHandler = utils.debounce(() => {
          this.filters.date = dateInput.value;
          this.fetchTable({ page: 1 });
        }, 200);
        dateInput.addEventListener('change', this.boundDateHandler);
      }

      if (clearBtn && clearBtn.dataset.bound !== '1') {
        clearBtn.dataset.bound = '1';
        this.boundClearHandler = () => this.clearFilters();
        clearBtn.addEventListener('click', this.boundClearHandler);
      }

      const retryBtn = this.container.querySelector('#retry-button');
      if (retryBtn && retryBtn.dataset.bound !== '1') {
        retryBtn.dataset.bound = '1';
        this.boundRetryHandler = () => this.fetchTable({ page: this.currentPage });
        retryBtn.addEventListener('click', this.boundRetryHandler);
      }
    }

    handleClick(e) {
      const target = e.target.closest('button, a');
      if (!target) return;

      if (target.classList.contains('page-link')) {
        e.preventDefault();
        const page = parseInt(target.dataset.page);
        if (!isNaN(page)) {
          this.fetchTable({ page });
        }
        return;
      }

      const dispoId = target.dataset.dispoId || target.closest('[data-dispo-id]')?.dataset.dispoId;
      if (!dispoId) return;

      if (target.classList.contains('toggle-btn')) {
        this.handleToggle(target, dispoId);
      } else if (target.classList.contains('action-btn-edit')) {
        this.handleEdit(target, dispoId);
      } else if (target.classList.contains('action-btn-delete')) {
        this.handleDelete(target, dispoId);
      }
    }

    async handleToggle(button, dispoId) {
      if (button.disabled) return;
      
      const row = button.closest('tr');
      const isActive = button.dataset.active === 'true';
      
      button.disabled = true;
      
      try {
        const res = await fetch(`/rdv/disponibilite/${dispoId}/toggle/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': utils.getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ is_active: !isActive })
        });

        if (res.ok) {
          const data = await res.json();
          this.updateRowStatus(row, button, data.is_active);
          utils.safeDispatchEvent('dispo:toggled', data);
        } else {
          throw new Error('Erreur toggle');
        }
      } catch (err) {
        console.error('Toggle error:', err);
        alert('Erreur lors de la mise à jour du créneau');
      } finally {
        button.disabled = false;
      }
    }

    updateRowStatus(row, toggleBtn, isActive) {
      if (!row || !toggleBtn) return;

      toggleBtn.dataset.active = isActive ? 'true' : 'false';
      const icon = toggleBtn.querySelector('i');
      if (icon) {
        icon.className = isActive ? 'bx bx-toggle-right' : 'bx bx-toggle-left';
      }
      toggleBtn.title = isActive ? 'Désactiver' : 'Activer';

      const statusBadge = row.querySelector('.status-badge');
      if (statusBadge) {
        statusBadge.className = `status-badge ${isActive ? 'status-active' : 'status-inactive'}`;
        statusBadge.innerHTML = `<i class='bx ${isActive ? 'bxs-check-circle' : 'bx-x-circle'}'></i> ${isActive ? 'Active' : 'Inactive'}`;
      }

      utils.animateElement(row, 'updated-row', 500);
    }

    handleEdit(button, dispoId) {
      const editUrl = button.dataset.editUrl || button.getAttribute('href');
      if (!editUrl) return;

      const modal = document.getElementById('edit-dispo-modal');
      const container = modal?.querySelector('#edit-modal-form-container');
      
      if (!modal || !container) {
        window.location = editUrl;
        return;
      }

      modal.classList.remove('hidden');
      this.loadFormFragment(editUrl, container);
    }

    async handleDelete(button, dispoId) {
      if (button.disabled) return;
      if (!confirm('Êtes-vous sûr de vouloir supprimer ce créneau ?')) return;

      const row = button.closest('tr');
      const deleteUrl = button.dataset.deleteUrl || button.getAttribute('href');
      
      button.disabled = true;
      
      try {
        const res = await fetch(deleteUrl, {
          method: 'POST',
          headers: { 
            'X-CSRFToken': utils.getCookie('csrftoken'), 
            'X-Requested-With': 'XMLHttpRequest' 
          }
        });
        
        if (res.ok) {
          if (row) {
            await utils.animateElement(row, 'removing', 300);
            row.remove();
          }
          utils.safeDispatchEvent('dispo:deleted', { id: dispoId });
        } else {
          throw new Error('Delete failed');
        }
      } catch (err) {
        console.error('Delete error:', err);
        alert('Erreur lors de la suppression');
        button.disabled = false;
      }
    }

    async loadFormFragment(url, container) {
      if (!container) return;
      
      container.innerHTML = '<p>Chargement…</p>';
      
      try {
        const res = await fetch(url, { 
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const text = await res.text();
        container.innerHTML = text;
        
        if (typeof window.bindModalForm === 'function') {
          window.bindModalForm(container);
        }
      } catch (err) {
        console.error('loadFormFragment error:', err);
        container.innerHTML = '<p>Impossible de charger le formulaire.</p>';
      }
    }

    initFilters() {
      const jourSelect = document.getElementById('jour-select');
      const dateInput = document.getElementById('date-input');
      
      if (jourSelect) this.filters.jour = jourSelect.value || '';
      if (dateInput) this.filters.date = dateInput.value || '';
    }

    clearFilters() {
      this.filters = {};
      
      const jourSelect = document.getElementById('jour-select');
      const dateInput = document.getElementById('date-input');
      
      if (jourSelect) jourSelect.value = '';
      if (dateInput) dateInput.value = '';
      
      this.fetchTable({ page: 1 });
    }

    async fetchTable(params = {}) {
      if (this.isLoading || !this.tableContainer) return;
      
      this.isLoading = true;
      const baseUrl = this.tableContainer.dataset.url || window.location.href;
      
      try {
        utils.showLoading(this.tableContainer, true);
        utils.showError(this.tableContainer, '', false);
        
        const url = new URL(baseUrl, window.location.origin);
        url.searchParams.set('table-only', '1');
        url.searchParams.set('type', 'ponctuel');
        
        const allParams = { ...this.filters, ...params };
        Object.entries(allParams).forEach(([key, value]) => {
          if (value || value === 0) {
            url.searchParams.set(key, value);
          } else {
            url.searchParams.delete(key);
          }
        });

        const res = await fetch(url.toString(), {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }

        const html = await res.text();
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        const newTableContainer = tempDiv.querySelector('#dispo-table-container');
        
        if (newTableContainer) {
          this.tableContainer.innerHTML = newTableContainer.innerHTML;
          this.currentPage = params.page || this.currentPage;
        }

      } catch (err) {
        console.error('fetchTable error:', err);
        utils.showError(this.tableContainer, 'Erreur lors du chargement des données', true);
      } finally {
        utils.showLoading(this.tableContainer, false);
        this.isLoading = false;
      }
    }

    destroy() {
      if (this.boundClickHandler) {
        this.container.removeEventListener('click', this.boundClickHandler);
      }
      
      const jourSelect = document.getElementById('jour-select');
      if (jourSelect && this.boundJourHandler) {
        jourSelect.removeEventListener('change', this.boundJourHandler);
        jourSelect.dataset.bound = '';
      }
      
      const dateInput = document.getElementById('date-input');
      if (dateInput && this.boundDateHandler) {
        dateInput.removeEventListener('change', this.boundDateHandler);
        dateInput.dataset.bound = '';
      }
      
      const clearBtn = document.getElementById('clear-filters');
      if (clearBtn && this.boundClearHandler) {
        clearBtn.removeEventListener('click', this.boundClearHandler);
        clearBtn.dataset.bound = '';
      }
      
      const retryBtn = this.container?.querySelector('#retry-button');
      if (retryBtn && this.boundRetryHandler) {
        retryBtn.removeEventListener('click', this.boundRetryHandler);
        retryBtn.dataset.bound = '';
      }
      
      if (this.container) {
        this.container.dataset.eventsBound = '';
      }
    }
  }

  // =============================================================================
  // GESTIONNAIRE WEEKLY CALENDAR
  // =============================================================================
  
  class WeeklyDispoManager {
    constructor() {
      this.calendar = document.getElementById('weekly-calendar');
      this.createModal = document.getElementById('create-dispo-modal');
      this.editModal = document.getElementById('edit-dispo-modal');
      this.boundClickHandler = null;
      
      if (!this.calendar) return;
      this.init();
    }

    init() {
      this.attachEventListeners();
    }

    attachEventListeners() {
      if (this.calendar.dataset.bound === '1') return;
      this.calendar.dataset.bound = '1';

      this.boundClickHandler = (e) => {
        const target = e.target.closest('button, a');
        if (!target) return;

        const dispoId = target.dataset.dispoId || target.closest('[data-dispo-id]')?.dataset.dispoId;

        if (target.classList.contains('toggle-btn')) {
          this.handleToggle(target, dispoId);
        } else if (target.classList.contains('edit-btn') || target.classList.contains('action-btn-edit')) {
          this.handleEdit(target, dispoId);
        } else if (target.classList.contains('delete-btn') || target.classList.contains('action-btn-delete')) {
          this.handleDelete(target, dispoId);
        } else if (target.classList.contains('add-slot-btn')) {
          this.handleAddSlot(target);
        }
      };

      this.calendar.addEventListener('click', this.boundClickHandler);

      document.addEventListener('dispo:saved', () => {
        this.refreshWeeklyCalendar().catch(console.warn);
      });
    }

    async handleToggle(button, dispoId) {
      if (!dispoId || button.disabled) return;
      
      const timeSlot = button.closest('.time-slot');
      const isActive = button.dataset.active === 'true';

      const loadingEl = timeSlot?.querySelector('.slot-loading');
      if (loadingEl) loadingEl.classList.remove('hidden');
      
      button.disabled = true;

      try {
        const res = await fetch(`/rdv/disponibilite/${dispoId}/toggle/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': utils.getCookie('csrftoken'),
            'X-Requested-With': 'XMLHttpRequest'
          },
          body: JSON.stringify({ is_active: !isActive })
        });

        if (res.ok) {
          const data = await res.json();
          this.updateSlotStatus(timeSlot, button, data.is_active);
          utils.safeDispatchEvent('dispo:toggled', data);
        } else {
          throw new Error('Erreur toggle');
        }
      } catch (err) {
        console.error('Toggle error:', err);
        alert('Erreur lors de la mise à jour du créneau');
      } finally {
        button.disabled = false;
        if (loadingEl) loadingEl.classList.add('hidden');
      }
    }

    updateSlotStatus(slot, toggleBtn, isActive) {
      if (!slot || !toggleBtn) return;

      slot.classList.toggle('active', isActive);
      slot.classList.toggle('inactive', !isActive);
      slot.dataset.active = isActive ? 'true' : 'false';

      toggleBtn.dataset.active = isActive ? 'true' : 'false';
      const toggleIcon = toggleBtn.querySelector('i');
      if (toggleIcon) {
        toggleIcon.className = isActive ? 'bx bx-toggle-right' : 'bx bx-toggle-left';
      }
      toggleBtn.title = isActive ? 'Désactiver' : 'Activer';

      const statusIndicator = slot.querySelector('.status-indicator');
      if (statusIndicator) {
        statusIndicator.className = `status-indicator ${isActive ? 'status-active' : 'status-inactive'}`;
        const statusIcon = statusIndicator.querySelector('i');
        if (statusIcon) {
          statusIcon.className = isActive ? 'bx bx-check-circle' : 'bx bx-x-circle';
        }
      }

      this.animateSlotChange(slot);
    }

    animateSlotChange(slot) {
      if (!slot) return;
      utils.animateElement(slot, 'updated-slot', 400);
    }

    handleEdit(button, dispoId) {
      const editUrl = button.dataset.editUrl || button.getAttribute('href');
      if (!editUrl) return;

      const modal = this.editModal;
      const container = modal?.querySelector('#edit-modal-form-container');
      
      if (!modal || !container) {
        window.location = editUrl;
        return;
      }

      modal.classList.remove('hidden');
      this.loadFormFragment(editUrl, container);
    }

    async handleDelete(button, dispoId) {
      if (!dispoId || button.disabled) return;
      if (!confirm('Êtes-vous sûr de vouloir supprimer ce créneau ?')) return;

      const timeSlot = button.closest('.time-slot');
      const deleteUrl = button.dataset.deleteUrl || button.getAttribute('href');
      
      const loadingEl = timeSlot?.querySelector('.slot-loading');
      if (loadingEl) loadingEl.classList.remove('hidden');
      
      button.disabled = true;

      try {
        const res = await fetch(deleteUrl, {
          method: 'POST',
          headers: { 
            'X-CSRFToken': utils.getCookie('csrftoken'), 
            'X-Requested-With': 'XMLHttpRequest' 
          }
        });
        
        if (res.ok) {
          if (timeSlot) {
            await utils.animateElement(timeSlot, 'removing', 300);
            timeSlot.remove();
          }
          utils.safeDispatchEvent('dispo:deleted', { id: dispoId });
        } else {
          throw new Error('Delete failed');
        }
      } catch (err) {
        console.error('Delete error:', err);
        alert('Erreur lors de la suppression');
        button.disabled = false;
      } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
      }
    }

    async handleAddSlot(button) {
      const dayKey = button.dataset.day;
      const formUrl = button.dataset.formUrl || button.getAttribute('href');
      
      if (!formUrl) return;

      const modal = this.createModal;
      const container = modal?.querySelector('#modal-form-container');
      
      if (!modal || !container) {
        window.location = formUrl;
        return;
      }

      modal.classList.remove('hidden');
      await this.loadFormFragment(formUrl, container);
    }

    async loadFormFragment(url, container) {
      if (!container) return;
      
      container.innerHTML = '<div class="loading-container" style="text-align: center; padding: 20px;"><i class="bx bx-loader-alt bx-spin" style="font-size: 24px;"></i><p>Chargement…</p></div>';
      
      try {
        const res = await fetch(url, { 
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const text = await res.text();
        container.innerHTML = text;
        
        if (typeof window.bindModalForm === 'function') {
          window.bindModalForm(container);
        }
      } catch (err) {
        console.error('loadFormFragment error:', err);
        container.innerHTML = '<div class="error-container" style="text-align: center; padding: 20px; color: #dc2626;"><i class="bx bx-error-circle" style="font-size: 24px;"></i><p>Impossible de charger le formulaire</p></div>';
      }
    }

    async refreshWeeklyCalendar() {
      if (!this.calendar) return;

      const container = document.getElementById('weekly-calendar-container') || this.calendar.parentElement;
      
      try {
        utils.showLoading(container, true);
        
        const response = await fetch('/rdv/disponibilites/weekly/', { 
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        
        const html = await response.text();
        
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        const newCalendar = tempDiv.querySelector('#weekly-calendar');
        
        if (newCalendar && this.calendar) {
          this.calendar.innerHTML = newCalendar.innerHTML;
          this.calendar.dataset.bound = '';
          this.attachEventListeners();
        }
        
      } catch (err) {
        console.error('refreshWeeklyCalendar error:', err);
        utils.showError(container, 'Erreur lors de la mise à jour du calendrier', true);
      } finally {
        utils.showLoading(container, false);
      }
    }

    destroy() {
      if (this.boundClickHandler && this.calendar) {
        this.calendar.removeEventListener('click', this.boundClickHandler);
        this.calendar.dataset.bound = '';
      }
    }
  }

  // =============================================================================
  // GESTIONNAIRE DE POLLING
  // =============================================================================
  
  class PollingManager {
    constructor() {
      this.isActive = false;
      this.interval = null;
      this.pollDelay = 15000;
      this.lastCount = null;
      this.container = document.getElementById('dispo-table-container');
      this.boundVisibilityHandler = null;
      this.boundUnloadHandler = null;
      
      if (this.container) {
        this.init();
      }
    }

    init() {
      if (this.container.dataset.pollBound === '1') return;
      this.container.dataset.pollBound = '1';

      this.boundVisibilityHandler = () => {
        if (document.hidden) {
          this.stop();
        } else {
          this.start();
        }
      };

      this.boundUnloadHandler = () => {
        this.stop();
      };

      document.addEventListener('visibilitychange', this.boundVisibilityHandler);
      window.addEventListener('beforeunload', this.boundUnloadHandler);

      this.start();
    }

    start() {
      if (this.isActive) return;
      
      this.isActive = true;
      this.interval = setInterval(() => {
        this.poll().catch(console.warn);
      }, this.pollDelay);

      console.log('Polling démarré');
    }

    stop() {
      if (!this.isActive) return;
      
      this.isActive = false;
      if (this.interval) {
        clearInterval(this.interval);
        this.interval = null;
      }

      console.log('Polling arrêté');
    }

    async poll() {
      if (!this.container) return;

      try {
        const ajaxUrl = this.container.dataset.url || window.location.href;
        const url = new URL(ajaxUrl, window.location.origin);
        url.searchParams.set('json', '1');
        
        if (this.lastCount !== null) {
          url.searchParams.set('last_count', this.lastCount);
        }

        const res = await fetch(url.toString(), { 
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        
        if (!res.ok) return;
        
        const data = await res.json();
        
        if (data && data.changed) {
          this.lastCount = data.last_count;
          console.log('Changement détecté, mise à jour...');
          
          if (window.tabManager && window.tabManager.activeTab === 'ponctuel') {
            if (window.ponctuelTableManager) {
              window.ponctuelTableManager.fetchTable({ page: window.ponctuelTableManager.currentPage });
            }
          }
          
          if (window.tabManager && window.tabManager.activeTab === 'hebdo') {
            if (window.weeklyDispoManager) {
              window.weeklyDispoManager.refreshWeeklyCalendar().catch(console.warn);
            }
          }
        }
      } catch (err) {
        console.debug('Poll error (silent):', err.message);
      }
    }

    destroy() {
      this.stop();
      
      if (this.boundVisibilityHandler) {
        document.removeEventListener('visibilitychange', this.boundVisibilityHandler);
      }
      
      if (this.boundUnloadHandler) {
        window.removeEventListener('beforeunload', this.boundUnloadHandler);
      }
      
      if (this.container) {
        this.container.dataset.pollBound = '';
      }
    }
  }

  // =============================================================================
  // NETTOYAGE ET INITIALISATION
  // =============================================================================
  
  function cleanupDispoManagement() {
    console.log('🧹 Nettoyage des instances dispo existantes');
    
    // Détruire les instances existantes
    if (window.pollingManager) {
      try {
        window.pollingManager.destroy();
        window.pollingManager = null;
      } catch (e) { console.warn('Erreur stop polling:', e); }
    }
    
    if (window.tabManager) {
      try {
        window.tabManager.destroy();
        window.tabManager = null;
      } catch (e) { console.warn('Erreur destroy tabManager:', e); }
    }
    
    if (window.ponctuelTableManager) {
      try {
        window.ponctuelTableManager.destroy();
        window.ponctuelTableManager = null;
      } catch (e) { console.warn('Erreur destroy ponctuelTableManager:', e); }
    }
    
    if (window.weeklyDispoManager) {
      try {
        window.weeklyDispoManager.destroy();
        window.weeklyDispoManager = null;
      } catch (e) { console.warn('Erreur destroy weeklyDispoManager:', e); }
    }
    
    // Réinitialiser les flags DOM
    const body = document.body;
    if (body) body.dataset.tabsBound = '';
    
    const ponctuelContent = document.getElementById('ponctuel-content');
    if (ponctuelContent) ponctuelContent.dataset.eventsBound = '';
    
    const calendar = document.getElementById('weekly-calendar');
    if (calendar) calendar.dataset.bound = '';
    
    const container = document.getElementById('dispo-table-container');
    if (container) container.dataset.pollBound = '';
    
    console.log('✅ Nettoyage terminé');
  }

  function initializeDispoManagement() {
    console.log('🔄 Initialisation du gestionnaire de disponibilités');

    // Vérifier que les éléments existent
    const hasDispoElements = document.getElementById('ponctuel-content') || 
                             document.getElementById('weekly-calendar') ||
                             document.querySelector('.tab-button[data-tab="hebdo"]');
    
    if (!hasDispoElements) {
      console.log('⚠️ Éléments dispo non trouvés, initialisation annulée');
      return;
    }

    // Nettoyer les anciennes instances
    cleanupDispoManagement();

    // Initialiser flatpickr si disponible
    if (typeof window.flatpickr === 'function') {
      try {
        const dateInputs = document.querySelectorAll('.date-input, input[type="date"]');
        if (dateInputs.length) {
          window.flatpickr(dateInputs, { 
            dateFormat: "Y-m-d",
            allowInput: true,
            locale: 'fr'
          });
        }

        const timeInputs = document.querySelectorAll('.time-input, input[type="time"]');
        if (timeInputs.length) {
          window.flatpickr(timeInputs, { 
            enableTime: true,
            noCalendar: true,
            dateFormat: "H:i",
            allowInput: true,
            time_24hr: true
          });
        }
      } catch (e) { 
        console.warn('Flatpickr init failed:', e);
      }
    }

    // Bind des formulaires AJAX existants
    document.querySelectorAll('form[data-ajax="1"]').forEach(form => {
      const container = form.closest('[data-ajax-container]') || form.parentElement;
      if (typeof window.bindModalForm === 'function') {
        try { 
          window.bindModalForm(container || form); 
        } catch (e) {
          console.warn('bindModalForm failed:', e);
        }
      }
    });

    // Initialiser les gestionnaires (dans l'ordre de dépendance)
    try {
      window.tabManager = new TabManager();
      window.ponctuelTableManager = new PonctuelTableManager();
      window.weeklyDispoManager = new WeeklyDispoManager();
      window.pollingManager = new PollingManager();
      
      console.log('✅ Gestionnaire de disponibilités initialisé avec succès');
    } catch (e) {
      console.error('❌ Erreur lors de l\'initialisation des gestionnaires:', e);
    }
  }

  // =============================================================================
  // EXPOSITION GLOBALE
  // =============================================================================
  
  // Utilitaires globaux
  window.ajaxSubmitForm = window.ajaxSubmitForm || ajaxSubmitForm;
  window.getCookie = window.getCookie || utils.getCookie;
  
  // Wrapper pour compatibilité
  window.bindDispoForm = window.bindDispoForm || function (container) {
    if (typeof window.bindModalForm === 'function') {
      try { 
        window.bindModalForm(container); 
      } catch (e) { 
        console.warn('bindModalForm wrapper failed:', e);
      }
    }
  };

  // Fonctions publiques pour actions manuelles
  window.fetchDispoTable = function() {
    if (window.ponctuelTableManager) {
      window.ponctuelTableManager.fetchTable({ page: 1 });
    }
  };

  window.refreshWeeklyCalendar = function() {
    if (window.weeklyDispoManager) {
      return window.weeklyDispoManager.refreshWeeklyCalendar();
    }
    return Promise.resolve();
  };

  // Fonction principale d'initialisation (appelée par runAllInits de base.js)
  window.initDispoManagement = initializeDispoManagement;
  
  // Fonction de réinitialisation complète (alias pour compatibilité)
  window.reinitDispoManagement = function() {
    console.log('🔄 Réinitialisation forcée du gestionnaire de disponibilités');
    cleanupDispoManagement();
    initializeDispoManagement();
  };

  // Fonction de nettoyage exposée pour le cycle de vie AJAX
  window.cleanupDispoManagement = cleanupDispoManagement;

  // =============================================================================
  // ÉVÉNEMENTS GLOBAUX
  // =============================================================================
  
  // Initialisation au premier chargement de la page
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      console.log('DOMContentLoaded - première initialisation dispo');
      initializeDispoManagement();
    });
  } else {
    // DOM déjà chargé, init immédiate si éléments présents
    if (document.getElementById('ponctuel-content') || document.getElementById('weekly-calendar')) {
      initializeDispoManagement();
    }
  }

  // Événement: Disponibilité sauvegardée
  document.addEventListener('dispo:saved', function(event) {
    console.log('✅ Disponibilité sauvegardée');
    
    // Fermer les modaux
    document.querySelectorAll('#create-dispo-modal, #edit-dispo-modal').forEach(modal => {
      modal.classList.add('hidden');
    });
    
    // Rafraîchir l'onglet actif
    setTimeout(() => {
      if (window.tabManager) {
        if (window.tabManager.activeTab === 'ponctuel' && window.ponctuelTableManager) {
          window.ponctuelTableManager.fetchTable({ page: 1 });
        } else if (window.tabManager.activeTab === 'hebdo' && window.weeklyDispoManager) {
          window.weeklyDispoManager.refreshWeeklyCalendar().catch(console.warn);
        }
      }
    }, 100);
  });

  // Événement: Disponibilité supprimée
  document.addEventListener('dispo:deleted', function(event) {
    console.log('🗑️ Disponibilité supprimée:', event.detail);
    
    // Rafraîchir l'onglet actif
    setTimeout(() => {
      if (window.tabManager) {
        if (window.tabManager.activeTab === 'hebdo' && window.weeklyDispoManager) {
          window.weeklyDispoManager.refreshWeeklyCalendar().catch(console.warn);
        }
        if (window.tabManager.activeTab === 'ponctuel' && window.ponctuelTableManager) {
          window.ponctuelTableManager.fetchTable({ page: 1 });
        }
      }
    }, 100);
  });

  // Événement: Toggle de disponibilité
  document.addEventListener('dispo:toggled', function(event) {
    console.log('🔄 Disponibilité toggle:', event.detail);
  });

  // Événement: Fragment déchargé (pour navigation AJAX)
  document.addEventListener('fragment:unloaded', function() {
    console.log('🔌 Fragment déchargé - nettoyage dispo');
    cleanupDispoManagement();
  });

  console.log('✅ dispo.js chargé et prêt (exposé window.initDispoManagement)');

})();