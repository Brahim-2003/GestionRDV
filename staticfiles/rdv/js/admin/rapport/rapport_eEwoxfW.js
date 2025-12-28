// static/rdv/js/admin/rapport/rapport.js
// Version finale corrigée pour navigation AJAX
(function () {
  'use strict';

  // Protection contre redéfinition du module
  if (window.__rdv_rapport_module_defined) {
    console.log('rapport.js: module déjà défini');
    return;
  }
  window.__rdv_rapport_module_defined = true;

  // =============================================================================
  // CLASSE DASHBOARD
  // =============================================================================

  class StatsDashboard {
    constructor() {
      this.charts = {};
      this.currentPeriod = sessionStorage.getItem('rdv_currentPeriod') || '30';
      this.isLoading = false;
      this.retryCount = 0;
      this.maxRetries = 3;
      this.updateInterval = null;

      // Event handlers bound
      this.boundPeriodHandlers = new Map();
      this.boundExportHandler = null;
      this.boundErrorHandler = null;
      this.boundOnlineHandler = null;
      this.boundOfflineHandler = null;

      this.colors = {
        primary: '#007BFF',
        success: '#28A745',
        warning: '#FFC107',
        danger: '#DC3545',
        info: '#17A2B8',
        purple: '#6F42C1',
        gray: '#6C757D',
        gradients: {
          blue: ['#007BFF', '#4A90E2'],
          green: ['#28A745', '#20c997'],
          orange: ['#FFC107', '#fd7e14'],
          red: ['#DC3545', '#e74c3c'],
          purple: ['#6F42C1', '#9f7aea'],
          teal: ['#17A2B8', '#20c997']
        }
      };

      this.chartDefaults = {
        font: { family: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif', size: 12 },
        color: '#495057',
        plugins: { legend: { labels: { usePointStyle: true, padding: 20, boxWidth: 12 } } },
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' }
      };

      if (!window.RDV_API) {
        window.RDV_API = {
          overview: '/rdv/api/overview/',
          rdv: '/rdv/api/rdv/',
          patients: '/rdv/api/patients/',
          medecins: '/rdv/api/medecins/',
          export: '/rdv/export/'
        };
      }
    }

    setupChartDefaults() {
      if (typeof Chart !== 'undefined') {
        Chart.defaults.font = this.chartDefaults.font;
        Chart.defaults.color = this.chartDefaults.color;
      }
    }

    setupEventListeners() {
      // Period buttons
      document.querySelectorAll('.period-btn').forEach(btn => {
        if (btn.dataset.periodBound === '1') return;
        btn.dataset.periodBound = '1';
        
        const handler = (e) => this.handlePeriodChange(e);
        btn.addEventListener('click', handler);
        this.boundPeriodHandlers.set(btn, handler);
      });

      // Export button
      const exportBtn = document.querySelector('.export-btn');
      if (exportBtn && !exportBtn.dataset.exportBound) {
        exportBtn.dataset.exportBound = '1';
        this.boundExportHandler = () => this.exportStats();
        exportBtn.addEventListener('click', this.boundExportHandler);
      }

      // Global events
      this.boundErrorHandler = (e) => this.handleGlobalError(e);
      this.boundOnlineHandler = () => this.handleConnectionRestore();
      this.boundOfflineHandler = () => this.handleConnectionLoss();

      window.addEventListener('error', this.boundErrorHandler);
      window.addEventListener('online', this.boundOnlineHandler);
      window.addEventListener('offline', this.boundOfflineHandler);
    }

    async init() {
      console.log('📊 Initialisation StatsDashboard');
      
      this.setupChartDefaults();
      this.setupEventListeners();
      this.destroyCharts();
      this.initCharts();
      await this.loadAllData();
      this.startPeriodicUpdate();
      this.setupIntersectionObserver();
      
      console.log('✅ StatsDashboard initialisé');
    }

    handlePeriodChange(event) {
      const btn = event.currentTarget;
      const newPeriod = btn.dataset.period;
      if (!newPeriod || newPeriod === this.currentPeriod) return;

      document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      this.currentPeriod = newPeriod;
      try { sessionStorage.setItem('rdv_currentPeriod', String(this.currentPeriod)); } catch(e){}

      btn.style.transform = 'scale(0.95)';
      setTimeout(() => btn.style.transform = 'scale(1)', 150);

      this.loadRdvData().catch(e => console.warn('loadRdvData failed', e));
    }

    destroyCharts() {
      const ids = ['rdvStatutChart', 'rdvEvolutionChart', 'specialitesChart', 'agesChart', 'medecinsChart', 'nouveauxPatientsChart'];
      
      ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        
        try {
          if (typeof Chart !== 'undefined' && typeof Chart.getChart === 'function') {
            const existing = Chart.getChart(el);
            if (existing) existing.destroy();
          }
        } catch (e) {
          console.warn('Erreur destroy chart', id, e);
        }
      });
      
      this.charts = {};
    }

    initCharts() {
      if (typeof Chart === 'undefined') {
        console.warn('Chart.js non disponible');
        return;
      }

      this.initRdvStatutChart();
      this.initRdvEvolutionChart();
      this.initSpecialitesChart();
      this.initAgesChart();
      this.initMedecinsChart();
      this.initNouveauxPatientsChart();
    }

    safeCreateChart(canvasId, config) {
      const ctx = document.getElementById(canvasId);
      if (!ctx) return null;

      try {
        if (typeof Chart.getChart === 'function') {
          const existing = Chart.getChart(ctx);
          if (existing) existing.destroy();
        }
        return new Chart(ctx, config);
      } catch (err) {
        console.error(`Erreur création chart ${canvasId}:`, err);
        return null;
      }
    }

    initRdvStatutChart() {
      this.charts.rdvStatut = this.safeCreateChart('rdvStatutChart', {
        type: 'doughnut',
        data: {
          labels: [],
          datasets: [{
            data: [],
            backgroundColor: [this.colors.primary, this.colors.success, this.colors.warning, this.colors.danger, this.colors.purple, this.colors.info],
            borderWidth: 3,
            borderColor: '#ffffff'
          }]
        },
        options: {
          ...this.chartDefaults,
          cutout: '60%',
          plugins: { legend: { position: 'bottom' } },
          animation: { animateRotate: true, duration: 1500 }
        }
      });
    }

    initRdvEvolutionChart() {
      const ctx = document.getElementById('rdvEvolutionChart');
      if (!ctx) return;

      this.charts.rdvEvolution = this.safeCreateChart('rdvEvolutionChart', {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Nombre de RDV',
            data: [],
            borderColor: this.colors.primary,
            backgroundColor: this.createGradient(ctx, this.colors.gradients.blue),
            borderWidth: 3,
            fill: true,
            tension: 0.4
          }]
        },
        options: {
          ...this.chartDefaults,
          plugins: { legend: { display: false } },
          animation: { duration: 2000 }
        }
      });
    }

    initSpecialitesChart() {
      this.charts.specialites = this.safeCreateChart('specialitesChart', {
        type: 'bar',
        data: {
          labels: [],
          datasets: [{
            label: 'Nombre de RDV',
            data: [],
            backgroundColor: this.colors.gradients.green.map(c => c + '80'),
            borderColor: this.colors.gradients.green,
            borderWidth: 2
          }]
        },
        options: {
          ...this.chartDefaults,
          plugins: { legend: { display: false } }
        }
      });
    }

    initAgesChart() {
      this.charts.ages = this.safeCreateChart('agesChart', {
        type: 'doughnut',
        data: {
          labels: [],
          datasets: [{
            data: [],
            backgroundColor: [this.colors.primary, this.colors.success, this.colors.warning, this.colors.danger, this.colors.purple],
            borderWidth: 3
          }]
        },
        options: {
          ...this.chartDefaults,
          cutout: '70%'
        }
      });
    }

    initMedecinsChart() {
      this.charts.medecins = this.safeCreateChart('medecinsChart', {
        type: 'bar',
        data: {
          labels: [],
          datasets: [{
            label: 'Nombre de RDV',
            data: [],
            backgroundColor: this.colors.gradients.purple.map(c => c + '80'),
            borderColor: this.colors.gradients.purple,
            borderWidth: 2
          }]
        },
        options: {
          ...this.chartDefaults,
          indexAxis: 'y'
        }
      });
    }

    initNouveauxPatientsChart() {
      const ctx = document.getElementById('nouveauxPatientsChart');
      if (!ctx) return;

      this.charts.nouveauxPatients = this.safeCreateChart('nouveauxPatientsChart', {
        type: 'line',
        data: {
          labels: [],
          datasets: [{
            label: 'Nouveaux Patients',
            data: [],
            borderColor: this.colors.info,
            backgroundColor: this.createGradient(ctx, this.colors.gradients.teal),
            borderWidth: 3,
            fill: true,
            tension: 0.4
          }]
        },
        options: {
          ...this.chartDefaults,
          plugins: { legend: { display: false } },
          animation: { duration: 2000 }
        }
      });
    }

    createGradient(ctxOrCanvas, colors) {
      try {
        let context = ctxOrCanvas;
        if (ctxOrCanvas && typeof ctxOrCanvas.getContext === 'function') 
          context = ctxOrCanvas.getContext('2d');
        
        if (!context || typeof context.createLinearGradient !== 'function') 
          return 'rgba(0,0,0,0)';
        
        const height = (context.canvas && context.canvas.height) || 400;
        const gradient = context.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, (colors[0] || '#000000') + '40');
        gradient.addColorStop(1, (colors[1] || '#000000') + '10');
        return gradient;
      } catch (err) {
        return 'rgba(0,0,0,0)';
      }
    }

    async loadAllData() {
      if (this.isLoading) return;
      
      this.isLoading = true;
      this.showGlobalLoading(true);
      
      try {
        await Promise.all([
          this.loadOverviewData(),
          this.loadRdvData(),
          this.loadPatientsData(),
          this.loadMedecinsData()
        ]);
        this.retryCount = 0;
      } catch (error) {
        console.error('loadAllData error:', error);
        this.handleLoadingError(error);
      } finally {
        this.isLoading = false;
        this.showGlobalLoading(false);
      }
    }

    async loadOverviewData() {
      try {
        const response = await this.fetchWithRetry(window.RDV_API.overview);
        if (!response) throw new Error('Réponse overview vide');
        
        this.updateOverviewCards(response.overview || {});
        this.updateChart('rdvStatut', response.rdv_statuts || []);
        this.updateChart('specialites', response.specialites_stats || []);
        this.updateTopMedecinsTable(response.top_medecins || []);
      } catch (error) {
        console.error('loadOverviewData error:', error);
      }
    }

    async loadRdvData() {
      try {
        const response = await this.fetchWithRetry(`${window.RDV_API.rdv}?periode=${this.currentPeriod}`);
        if (!response) throw new Error('Réponse rdv vide');
        
        this.updateChart('rdvEvolution', response.rdv_timeline || []);
      } catch (error) {
        console.error('loadRdvData error:', error);
      }
    }

    async loadPatientsData() {
      try {
        const response = await this.fetchWithRetry(window.RDV_API.patients);
        if (!response) throw new Error('Réponse patients vide');
        
        this.updateChart('ages', response.ages_data || []);
        this.updateChart('nouveauxPatients', response.inscriptions_evolution || []);
        this.updatePatientsActifsTable(response.patients_actifs || []);
      } catch (error) {
        console.error('loadPatientsData error:', error);
      }
    }

    async loadMedecinsData() {
      try {
        const response = await this.fetchWithRetry(window.RDV_API.medecins);
        if (!response) throw new Error('Réponse medecins vide');
        
        this.updateChart('medecins', response.medecins_performance || []);
      } catch (error) {
        console.error('loadMedecinsData error:', error);
      }
    }

    updateOverviewCards(data) {
      const cards = [
        { id: 'total-patients', value: data.total_patients || 0 },
        { id: 'total-medecins', value: data.total_medecins || 0 },
        { id: 'total-rdv', value: data.total_rdv || 0 },
        { id: 'rdv-aujourd-hui', value: data.rdv_aujourd_hui || 0 }
      ];
      
      cards.forEach((card, index) => {
        setTimeout(() => this.animateValue(document.getElementById(card.id), 0, card.value, 1500), index * 300);
      });
    }

    animateValue(element, start, end, duration) {
      if (!element) return;
      
      let startTime = null;
      const step = (timestamp) => {
        if (!startTime) startTime = timestamp;
        const progress = Math.min((timestamp - startTime) / duration, 1);
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(easeOutQuart * (end - start) + start);
        element.textContent = this.formatNumber(current);
        
        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          element.style.transform = 'scale(1.1)';
          setTimeout(() => element.style.transform = 'scale(1)', 200);
        }
      };
      requestAnimationFrame(step);
    }

    updateChart(chartName, data) {
      const chart = this.charts[chartName];
      if (!chart || !data) return;

      try {
        switch (chartName) {
          case 'rdvStatut': this.updateRdvStatutChart(chart, data); break;
          case 'rdvEvolution': this.updateRdvEvolutionChart(chart, data); break;
          case 'specialites': this.updateSpecialitesChart(chart, data); break;
          case 'ages': this.updateAgesChart(chart, data); break;
          case 'medecins': this.updateMedecinsChart(chart, data); break;
          case 'nouveauxPatients': this.updateNouveauxPatientsChart(chart, data); break;
        }
      } catch (e) {
        console.error('updateChart error:', e);
      }
    }

    updateRdvStatutChart(chart, data) {
      const statutTranslation = {
        'programme': 'Programmé',
        'confirme': 'Confirmé',
        'annule': 'Annulé',
        'reporte': 'Reporté',
        'termine': 'Terminé',
        'en_cours': 'En cours'
      };
      
      chart.data.labels = data.map(item => statutTranslation[item.statut] || item.statut);
      chart.data.datasets[0].data = data.map(item => item.count || 0);
      chart.update();
    }

    updateRdvEvolutionChart(chart, data) {
      chart.data.labels = data.map(item => 
        new Date(item.period).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
      );
      chart.data.datasets[0].data = data.map(item => item.count || 0);
      chart.update();
    }

    updateSpecialitesChart(chart, data) {
      const specialiteTranslation = {
        'generaliste': 'Généraliste',
        'cardiologue': 'Cardiologue',
        'dermatologue': 'Dermatologue',
        'pediatre': 'Pédiatre',
        'gynecologue': 'Gynécologue',
        'neurologue': 'Neurologue',
        'psychiatre': 'Psychiatre',
        'orthopediste': 'Orthopédiste',
        'ophtalmologue': 'Ophtalmologue',
        'orl': 'ORL'
      };
      
      const top6 = (Array.isArray(data) ? data : []).slice(0, 6);
      chart.data.labels = top6.map(item => 
        specialiteTranslation[item.specialite || item.medecin__specialite] || item.specialite || '—'
      );
      chart.data.datasets[0].data = top6.map(item => item.count || 0);
      chart.update();
    }

    updateAgesChart(chart, data) {
      chart.data.labels = (data || []).map(item => (item.age_group || '') + ' ans');
      chart.data.datasets[0].data = (data || []).map(item => item.count || 0);
      chart.update();
    }

    updateMedecinsChart(chart, data) {
      const top5 = (Array.isArray(data) ? data : []).slice(0, 5);
      chart.data.labels = top5.map(item => `Dr. ${item.user__nom || 'N/A'}`);
      chart.data.datasets[0].data = top5.map(item => item.total_rdv || 0);
      chart.update();
    }

    updateNouveauxPatientsChart(chart, data) {
      const moisFrancais = {
        '01': 'Jan', '02': 'Fév', '03': 'Mar', '04': 'Avr',
        '05': 'Mai', '06': 'Jun', '07': 'Jul', '08': 'Aoû',
        '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Déc'
      };
      
      chart.data.labels = (data || []).map(item => {
        const parts = (item.month || '').split('-');
        const annee = parts[0] || '';
        const mois = parts[1] || '01';
        return `${moisFrancais[mois] || mois} ${annee}`;
      });
      chart.data.datasets[0].data = (data || []).map(item => item.count || 0);
      chart.update();
    }

    updateTopMedecinsTable(data) {
      const tbody = document.getElementById('top-medecins-table');
      if (!tbody) return;

      const safeData = Array.isArray(data) ? data : [];
      const maxCount = safeData.length > 0 ? (safeData[0].total_rdv || 1) : 1;

      tbody.innerHTML = safeData.slice(0, 8).map((item, index) => {
        const totalRdv = item.total_rdv || 0;
        const rdvConfirmes = item.rdv_confirmes || 0;
        const rdvAnnules = item.rdv_annules || 0;
        const taux = totalRdv ? Math.round((rdvConfirmes / totalRdv) * 100) : 0;

        return `
          <tr style="animation: slideInUp ${0.5 + index * 0.1}s ease-out both">
            <td>
              <div style="display:flex;align-items:center;gap:10px;">
                <div class="rank-badge">${index + 1}</div>
                <div><strong>Dr. ${item.user__nom || ''} ${item.user__prenom || ''}</strong></div>
              </div>
            </td>
            <td><span class="specialty-badge">${item.specialite || '—'}</span></td>
            <td>
              <div class="progress-container">
                <div class="progress-bar" style="width:${(totalRdv / maxCount) * 100}%"></div>
                <span class="progress-text"><strong>${totalRdv}</strong></span>
              </div>
            </td>
            <td>
              <div class="confirmation-rate ${rdvConfirmes > rdvAnnules ? 'good' : 'warning'}">
                ${taux}% confirmés
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    updatePatientsActifsTable(data) {
      const tbody = document.getElementById('patients-actifs-table');
      if (!tbody) return;

      const safeData = Array.isArray(data) ? data : [];
      
      tbody.innerHTML = safeData.slice(0, 10).map((item, index) => {
        const prenom = item.user__prenom || '';
        const nom = item.user__nom || '';
        const avatar = (prenom.charAt(0) || '') + (nom.charAt(0) || '');
        const nombre = item.nombre_rdv || 0;

        return `
          <tr style="animation: slideInUp ${0.5 + index * 0.1}s ease-out both">
            <td>
              <div style="display:flex;align-items:center;gap:10px;">
                <div class="patient-avatar">${avatar}</div>
                <div><strong>${prenom} ${nom}</strong></div>
              </div>
            </td>
            <td>
              <div class="rdv-count">
                <i class='bx bx-calendar-check'></i>
                <strong>${nombre}</strong> RDV
              </div>
            </td>
          </tr>
        `;
      }).join('');
    }

    async exportStats() {
      const btn = document.querySelector('.export-btn');
      if (!btn) {
        window.location.href = window.RDV_API.export;
        return;
      }

      const originalContent = btn.innerHTML;
      btn.style.transform = 'scale(0.95)';
      btn.innerHTML = '<i class="bx bx-loader-alt bx-spin"></i> Export en cours...';
      btn.disabled = true;

      try {
        await new Promise(r => setTimeout(r, 500));
        window.location.href = window.RDV_API.export;
        btn.innerHTML = '<i class="bx bx-check"></i> Export lancé';
        btn.style.background = 'linear-gradient(135deg, var(--success-color), #20c997)';
        
        setTimeout(() => {
          btn.innerHTML = originalContent;
          btn.style.transform = 'scale(1)';
          btn.style.background = '';
          btn.disabled = false;
        }, 2000);
      } catch (error) {
        console.error('exportStats error:', error);
        btn.innerHTML = '<i class="bx bx-error"></i> Erreur export';
        btn.style.background = 'linear-gradient(135deg, var(--danger-color), #e74c3c)';
        
        setTimeout(() => {
          btn.innerHTML = originalContent;
          btn.style.transform = 'scale(1)';
          btn.style.background = '';
          btn.disabled = false;
        }, 2000);
      }
    }

    async fetchWithRetry(url, options = {}, retries = 3) {
      for (let i = 0; i <= retries; i++) {
        try {
          const response = await fetch(url, {
            ...options,
            headers: {
              'Content-Type': 'application/json',
              'X-Requested-With': 'XMLHttpRequest',
              ...(options.headers || {})
            },
            credentials: options.credentials || 'same-origin'
          });

          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          if (response.status === 204) return null;

          const contentType = response.headers.get('content-type') || '';
          if (contentType.indexOf('application/json') === -1) {
            const txt = await response.text();
            try { return txt ? JSON.parse(txt) : null; } 
            catch (e) { return null; }
          }

          return await response.json();
        } catch (error) {
          if (i === retries) throw error;
          await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i)));
        }
      }
    }

    showGlobalLoading(show) {
      const existing = document.querySelector('.global-loading');
      
      if (show && !existing) {
        const loading = document.createElement('div');
        loading.className = 'global-loading';
        loading.innerHTML = `
          <div style="position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(255,255,255,0.9);z-index:9999;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:20px;">
            <div class="spinner"></div>
            <div style="color:var(--gray-600);font-weight:500;">Chargement des données...</div>
          </div>
        `;
        document.body.appendChild(loading);
      } else if (!show && existing) {
        existing.remove();
      }
    }

    handleGlobalError(event) {
      console.error('Erreur globale:', event);
    }

    handleConnectionLoss() {
      this.showNotification('Connexion perdue', 'warning');
    }

    handleConnectionRestore() {
      this.showNotification('Connexion rétablie', 'success');
      if (!this.isLoading) this.loadAllData();
    }

    handleLoadingError(error) {
      this.retryCount++;
      if (this.retryCount < this.maxRetries) {
        setTimeout(() => this.loadAllData(), 5000);
      } else {
        this.showNotification('Impossible de charger les données', 'error');
      }
    }

    showNotification(message, type = 'info') {
      const notification = document.createElement('div');
      notification.className = `notification notification-${type}`;
      notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        max-width: 400px;
      `;
      notification.textContent = message;
      
      document.body.appendChild(notification);
      setTimeout(() => notification.remove(), 5000);
    }

    startPeriodicUpdate() {
      if (this.updateInterval) clearInterval(this.updateInterval);
      
      this.updateInterval = setInterval(() => {
        if (!this.isLoading && navigator.onLine && hasReportFragmentOnPage()) {
          this.loadAllData();
        }
      }, 300000); // 5 minutes
    }

    setupIntersectionObserver() {
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
          }
        });
      }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

      document.querySelectorAll('.chart-container, .table-container').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'all 0.6s ease-out';
        observer.observe(el);
      });
    }

    formatNumber(num) {
      if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
      else if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
      return num.toString();
    }

    destroy() {
      console.log('🧹 Destruction StatsDashboard');
      
      // Stop periodic updates
      if (this.updateInterval) {
        clearInterval(this.updateInterval);
        this.updateInterval = null;
      }

      // Remove event listeners
      this.boundPeriodHandlers.forEach((handler, btn) => {
        btn.removeEventListener('click', handler);
        btn.dataset.periodBound = '';
      });
      this.boundPeriodHandlers.clear();

      const exportBtn = document.querySelector('.export-btn');
      if (exportBtn && this.boundExportHandler) {
        exportBtn.removeEventListener('click', this.boundExportHandler);
        exportBtn.dataset.exportBound = '';
      }

      window.removeEventListener('error', this.boundErrorHandler);
      window.removeEventListener('online', this.boundOnlineHandler);
      window.removeEventListener('offline', this.boundOfflineHandler);

      // Destroy charts
      this.destroyCharts();

      // Remove loading overlay
      const loading = document.querySelector('.global-loading');
      if (loading) loading.remove();

      console.log('✅ StatsDashboard détruit');
    }
  }

  // =============================================================================
  // GESTION SINGLETON
  // =============================================================================

  let dashboardInstance = null;

  function hasReportFragmentOnPage() {
    return !!(
      document.getElementById('rdvStatutChart') ||
      document.querySelector('.charts-grid') ||
      document.querySelector('.report-dashboard-root')
    );
  }

  function initReportDashboard() {
    console.log('🔄 initReportDashboard appelé');

    // Vérifier si les éléments du rapport sont présents
    if (!hasReportFragmentOnPage()) {
      console.log('⚠️ Éléments rapport non trouvés - initialisation annulée');
      return;
    }

    // Vérifier que Chart.js est disponible
    if (typeof Chart === 'undefined') {
      console.error('❌ Chart.js non disponible');
      return;
    }

    console.log('✅ Initialisation du dashboard de rapport');

    // Détruire l'instance précédente si elle existe
    if (dashboardInstance) {
      try {
        dashboardInstance.destroy();
      } catch (e) {
        console.warn('Erreur lors de la destruction de l\'ancienne instance:', e);
      }
      dashboardInstance = null;
    }

    // Créer une nouvelle instance
    try {
      dashboardInstance = new StatsDashboard();
      dashboardInstance.init();
      window.reportDashboard = dashboardInstance;
      console.log('✅ Dashboard de rapport initialisé avec succès');
    } catch (error) {
      console.error('❌ Erreur lors de l\'initialisation du dashboard:', error);
      dashboardInstance = null;
      window.reportDashboard = null;
    }
  }

  function destroyReportDashboard() {
    console.log('🧹 destroyReportDashboard - nettoyage en cours');

    if (dashboardInstance) {
      try {
        dashboardInstance.destroy();
      } catch (e) {
        console.warn('Erreur lors de la destruction du dashboard:', e);
      }
      dashboardInstance = null;
    }

    if (window.reportDashboard) {
      window.reportDashboard = null;
    }

    console.log('✅ Dashboard de rapport détruit');
  }

  // =============================================================================
  // EXPOSITION GLOBALE
  // =============================================================================

  // Fonction principale appelée par runAllInits() de base.js
  window.initReportDashboard = initReportDashboard;

  // Fonction de nettoyage pour le cycle de vie AJAX
  window.destroyReportDashboard = destroyReportDashboard;

  // Fonction de réinitialisation forcée
  window.reinitReportDashboard = function() {
    console.log('🔄 Réinitialisation forcée du dashboard');
    destroyReportDashboard();
    initReportDashboard();
  };

  // Expose la classe pour usage externe si nécessaire
  window.StatsDashboard = StatsDashboard;

  // =============================================================================
  // AUTO-INITIALISATION AU PREMIER CHARGEMENT
  // =============================================================================

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      console.log('DOMContentLoaded - première initialisation rapport');
      if (hasReportFragmentOnPage()) {
        initReportDashboard();
      }
    });
  } else {
    // DOM déjà chargé, initialiser si éléments présents
    if (hasReportFragmentOnPage()) {
      console.log('DOM déjà prêt - initialisation rapport');
      setTimeout(() => initReportDashboard(), 0);
    }
  }

  // =============================================================================
  // ÉVÉNEMENT DE DÉCHARGEMENT
  // =============================================================================

  document.addEventListener('fragment:unloaded', function() {
    console.log('🔌 Fragment déchargé - nettoyage rapport');
    destroyReportDashboard();
  });

  console.log('✅ rapport.js chargé et prêt (exposé window.initReportDashboard)');

})();