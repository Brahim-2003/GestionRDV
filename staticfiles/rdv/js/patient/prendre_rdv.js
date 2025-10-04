// prendre_rdv.js - Version finale corrigée pour navigation AJAX
// Système de prise de rendez-vous médicaux
// ✅ Compatible avec base.js et runAllInits()

// Protection contre double définition du module
if (!window.__prendre_rdv_module_defined) {
    window.__prendre_rdv_module_defined = true;

    (function() {
        'use strict';

        // =============================================================================
        // UTILITAIRES
        // =============================================================================

        function getCookie(name) {
            let cookieValue = null;
            if (document.cookie && document.cookie !== '') {
                const cookies = document.cookie.split(';');
                for (let i = 0; i < cookies.length; i++) {
                    const cookie = cookies[i].trim();
                    if (cookie.substring(0, name.length + 1) === (name + '=')) {
                        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                        break;
                    }
                }
            }
            return cookieValue;
        }

        const Utils = {
            escapeHtml(str) {
                if (typeof str !== 'string') return str;
                const div = document.createElement('div');
                div.textContent = str;
                return div.innerHTML;
            },
            getCSRFToken() {
                const cookie = document.cookie.match(/csrftoken=([^;]+)/);
                return cookie ? cookie[1] : '';
            },
            formatDateISO(date) {
                if (!(date instanceof Date) || isNaN(date)) return '';
                const y = date.getFullYear();
                const m = String(date.getMonth() + 1).padStart(2, '0');
                const d = String(date.getDate()).padStart(2, '0');
                return `${y}-${m}-${d}`;
            },
            formatDateFR(date) {
                if (!(date instanceof Date) || isNaN(date)) return '';
                return date.toLocaleDateString('fr-FR', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                });
            },
            parseTime(timeStr) {
                if (!timeStr) return null;
                const [hours, minutes] = timeStr.split(':').map(Number);
                if (isNaN(hours) || isNaN(minutes)) return null;
                return { hours, minutes };
            },
            combineDateAndTime(date, timeStr) {
                const time = this.parseTime(timeStr);
                if (!time) return null;
                const combined = new Date(date);
                combined.setHours(time.hours, time.minutes, 0, 0);
                return combined;
            },
            debounce(func, wait) {
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
            showNotification(message, type = 'info') {
                const notification = document.createElement('div');
                notification.className = `notification notification-${type}`;
                notification.textContent = message;
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 12px 20px;
                    background: ${type === 'error' ? '#dc3545' : type === 'success' ? '#28a745' : '#17a2b8'};
                    color: white;
                    border-radius: 4px;
                    z-index: 10000;
                    animation: slideIn 0.3s ease-out;
                `;
                document.body.appendChild(notification);
                setTimeout(() => {
                    notification.style.animation = 'slideOut 0.3s ease-out';
                    setTimeout(() => notification.remove(), 300);
                }, 4000);
            }
        };

        // =============================================================================
        // STATE
        // =============================================================================

        const APP_STATE = {
            currentStep: 1,
            selectedSpecialty: null,
            specialtyName: '',
            doctorsData: {},
            selectedDoctor: null,
            selectedDate: null,
            selectedTime: null,
            selectedSlot: null,
            currentMonth: new Date(),
            slotsByDate: {},
            isLoading: false
        };

        const API_ENDPOINTS = {
            searchDoctors: '/rdv/api/search/medecins/',
            getSlots: '/rdv/api/creneaux/medecins/',
            bookAppointment: '/rdv/api/reserver/rdv/',
            toggleFavorite: '/rdv/api/toggle/favori/'
        };

        // =============================================================================
        // API
        // =============================================================================

        const API = {
            async request(url, options = {}) {
                const defaultOptions = {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': Utils.getCSRFToken(),
                        ...options.headers
                    }
                };

                try {
                    const response = await fetch(url, { ...defaultOptions, ...options });

                    if (!response.ok) {
                        const errorData = await response.json().catch(() => ({}));
                        throw new Error(errorData.error || errorData.message || `HTTP ${response.status}`);
                    }

                    return await response.json();
                } catch (error) {
                    console.error('API Request failed:', error);
                    throw error;
                }
            },

            async searchDoctors(specialty, filters = {}) {
                const url = new URL(API_ENDPOINTS.searchDoctors, window.location.origin);
                if (specialty) url.searchParams.append('specialite', specialty);
                if (filters.search) url.searchParams.append('q', filters.search);
                if (filters.disponibleSemaine) url.searchParams.append('dispo_semaine', '1');
                const response = await this.request(url);
                return Array.isArray(response) ? response : (response.medecins || []);
            },

            async getDoctorSlots(doctorId, dateDebut, dateFin) {
                const url = new URL(`${API_ENDPOINTS.getSlots}${doctorId}/`, window.location.origin);
                url.searchParams.append('date_debut', dateDebut.toISOString());
                url.searchParams.append('date_fin', dateFin.toISOString());
                const response = await this.request(url);
                return Array.isArray(response) ? response : (response.creneaux || []);
            },

            async bookAppointment(doctorId, datetime, motif = '') {
                const url = new URL(API_ENDPOINTS.bookAppointment, window.location.origin);
                return await this.request(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ medecin_id: doctorId, datetime: datetime, motif: motif })
                });
            }
        };

        // =============================================================================
        // SPECIALTY SELECTOR
        // =============================================================================

        const SpecialtySelector = {
            boundCardHandlers: new Map(),
            boundContinueHandler: null,
            boundSearchHandler: null,
            boundFilterHandlers: new Map(),

            init() {
                this.cleanup();
                this.attachEventListeners();
                this.initSearch();
                this.initFilters();
            },

            cleanup() {
                this.boundCardHandlers.forEach((handler, card) => {
                    card.removeEventListener('click', handler);
                });
                this.boundCardHandlers.clear();

                if (this.boundContinueHandler) {
                    const continueBtn = document.getElementById('step1-continue');
                    if (continueBtn) continueBtn.removeEventListener('click', this.boundContinueHandler);
                    this.boundContinueHandler = null;
                }

                this.boundFilterHandlers.forEach((handler, chip) => {
                    chip.removeEventListener('click', handler);
                });
                this.boundFilterHandlers.clear();

                if (this.boundSearchHandler) {
                    const searchInput = document.getElementById('specialty-search');
                    if (searchInput) searchInput.removeEventListener('input', this.boundSearchHandler);
                    this.boundSearchHandler = null;
                }
            },

            attachEventListeners() {
                document.querySelectorAll('.speciality-card').forEach(card => {
                    const handler = (e) => this.selectSpecialty(e.currentTarget);
                    card.addEventListener('click', handler);
                    this.boundCardHandlers.set(card, handler);
                });

                const continueBtn = document.getElementById('step1-continue');
                if (continueBtn) {
                    this.boundContinueHandler = () => Navigation.nextStep();
                    continueBtn.addEventListener('click', this.boundContinueHandler);
                }
            },

            selectSpecialty(card) {
                document.querySelectorAll('.speciality-card').forEach(c => {
                    c.classList.remove('selected');
                });
                card.classList.add('selected');

                APP_STATE.selectedSpecialty = card.dataset.speciality;
                APP_STATE.specialtyName = card.querySelector('.speciality-name')?.textContent || APP_STATE.selectedSpecialty;

                const continueBtn = document.getElementById('step1-continue');
                if (continueBtn) continueBtn.disabled = false;
            },

            initSearch() {
                const searchInput = document.getElementById('specialty-search');
                if (!searchInput) return;
                this.boundSearchHandler = Utils.debounce((e) => {
                    const searchTerm = e.target.value.toLowerCase();
                    document.querySelectorAll('.speciality-card').forEach(card => {
                        const name = card.querySelector('.speciality-name')?.textContent.toLowerCase() || '';
                        card.style.display = name.includes(searchTerm) ? '' : 'none';
                    });
                }, 300);
                searchInput.addEventListener('input', this.boundSearchHandler);
            },

            initFilters() {
                document.querySelectorAll('.filter-chip').forEach(chip => {
                    const handler = (e) => { e.currentTarget.classList.toggle('active'); };
                    chip.addEventListener('click', handler);
                    this.boundFilterHandlers.set(chip, handler);
                });
            },

            destroy() { 
                this.cleanup(); 
            }
        };

        // =============================================================================
        // DOCTOR LIST
        // =============================================================================

        const DoctorList = {
            boundChooseHandlers: new Map(),
            boundCardHandlers: new Map(),

            async load() {
                const listContainer = document.getElementById('doctor-list');
                if (!listContainer) return;

                listContainer.innerHTML = `
                    <div style="text-align: center; padding: 40px;">
                        <div class="spinner-border" role="status">
                            <span class="sr-only">Chargement des médecins...</span>
                        </div>
                        <p style="margin-top: 10px;">Chargement des médecins...</p>
                    </div>
                `;

                try {
                    const doctors = await API.searchDoctors(APP_STATE.selectedSpecialty);
                    this.render(doctors);
                } catch (error) {
                    console.error('Erreur lors du chargement des médecins:', error);
                    listContainer.innerHTML = `
                        <div style="text-align: center; padding: 40px; color: #dc3545;">
                            <i class="bx bx-error-circle" style="font-size: 48px;"></i>
                            <p>Erreur lors du chargement des médecins.</p>
                            <button class="btn btn-secondary" onclick="window.DoctorList.load()">Réessayer</button>
                        </div>
                    `;
                    Utils.showNotification('Erreur lors du chargement des médecins', 'error');
                }
            },

            render(doctors) {
                const listContainer = document.getElementById('doctor-list');
                if (!listContainer) return;

                this.cleanup();
                APP_STATE.doctorsData = {};
                listContainer.innerHTML = '';

                if (doctors.length === 0) {
                    listContainer.innerHTML = `
                        <div style="text-align: center; padding: 40px; color: #6c757d;">
                            <i class="bx bx-user-x" style="font-size: 48px;"></i>
                            <p>Aucun médecin disponible pour cette spécialité.</p>
                            <button class="btn btn-secondary" onclick="window.Navigation.previousStep()">Retour</button>
                        </div>
                    `;
                    return;
                }

                doctors.forEach(doctor => {
                    APP_STATE.doctorsData[doctor.id] = doctor;
                    const card = this.createDoctorCard(doctor);
                    listContainer.appendChild(card);
                });

                const continueBtn = document.getElementById('step2-continue');
                if (continueBtn) continueBtn.disabled = true;
            },

            cleanup() {
                this.boundChooseHandlers.forEach((handler, btn) => { 
                    btn.removeEventListener('click', handler); 
                });
                this.boundChooseHandlers.clear();
                this.boundCardHandlers.forEach((handler, card) => { 
                    card.removeEventListener('click', handler); 
                });
                this.boundCardHandlers.clear();
            },

            createDoctorCard(doctor) {
                const card = document.createElement('div');
                card.className = 'doctor-card';
                card.dataset.doctorId = doctor.id;

                const photoHtml = doctor.photo_url
                    ? `<img src="${Utils.escapeHtml(doctor.photo_url)}" alt="Photo" onerror="this.parentElement.innerHTML='<div class=\\'photo-placeholder\\'>${Utils.escapeHtml((doctor.nom || 'D')[0])}</div>'">`
                    : `<div class="photo-placeholder">${Utils.escapeHtml((doctor.nom || 'D')[0])}</div>`;

                const prochaineDispo = doctor.prochaine_dispo
                    ? new Date(doctor.prochaine_dispo).toLocaleDateString('fr-FR')
                    : 'Non renseigné';

                card.innerHTML = `
                    <div class="doctor-photo">${photoHtml}</div>
                    <div class="doctor-info">
                        <div class="doctor-name">${Utils.escapeHtml(doctor.nom || 'Non renseigné')}</div>
                        <div class="doctor-specialty">${Utils.escapeHtml(doctor.specialite_label || '')}</div>
                        <div class="doctor-meta">
                            <div class="meta-item">
                                <i class="bx bx-building"></i>
                                <span>${Utils.escapeHtml(doctor.cabinet || 'Cabinet non renseigné')}</span>
                            </div>
                            ${doctor.tarif ? `
                            <div class="meta-item">
                                <i class="bx bx-euro"></i>
                                <span>${Utils.escapeHtml(doctor.tarif)} €</span>
                            </div>` : ''}
                            ${doctor.langues ? `
                            <div class="meta-item">
                                <i class="bx bx-globe"></i>
                                <span>${Utils.escapeHtml(doctor.langues)}</span>
                            </div>` : ''}
                            <div class="meta-item">
                                <i class="bx bx-calendar"></i>
                                <span>Prochaine dispo: ${Utils.escapeHtml(prochaineDispo)}</span>
                            </div>
                        </div>
                    </div>
                    <div class="doctor-actions">
                        <button type="button" class="btn btn-primary choose-doctor-btn">Choisir</button>
                    </div>
                `;

                const chooseBtn = card.querySelector('.choose-doctor-btn');
                const chooseBtnHandler = (e) => { e.stopPropagation(); this.selectDoctor(doctor.id); };
                chooseBtn.addEventListener('click', chooseBtnHandler);
                this.boundChooseHandlers.set(chooseBtn, chooseBtnHandler);

                const cardHandler = () => this.selectDoctor(doctor.id);
                card.addEventListener('click', cardHandler);
                this.boundCardHandlers.set(card, cardHandler);

                return card;
            },

            selectDoctor(doctorId) {
                const doctor = APP_STATE.doctorsData[doctorId];
                if (!doctor) return;

                document.querySelectorAll('.doctor-card').forEach(card => card.classList.remove('selected'));
                const selectedCard = document.querySelector(`.doctor-card[data-doctor-id="${doctorId}"]`);
                if (selectedCard) selectedCard.classList.add('selected');

                APP_STATE.selectedDoctor = doctor;
                const continueBtn = document.getElementById('step2-continue');
                if (continueBtn) continueBtn.disabled = false;
            },

            destroy() { 
                this.cleanup(); 
            }
        };

        // =============================================================================
        // CALENDAR
        // =============================================================================

        const Calendar = {
            boundDayHandlers: new Map(),
            boundPrevHandler: null,
            boundNextHandler: null,

            render() {
                const grid = document.getElementById('calendar-grid');
                const title = document.getElementById('calendar-title');
                if (!grid || !title) return;

                this.cleanup();
                grid.querySelectorAll('.calendar-day, .calendar-empty').forEach(el => el.remove());

                const monthNames = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
                const year = APP_STATE.currentMonth.getFullYear();
                const month = APP_STATE.currentMonth.getMonth();
                title.textContent = `${monthNames[month]} ${year}`;

                const firstDay = new Date(year, month, 1);
                const lastDay = new Date(year, month + 1, 0);
                const startDay = (firstDay.getDay() + 6) % 7;

                for (let i = 0; i < startDay; i++) {
                    const emptyDiv = document.createElement('div');
                    emptyDiv.className = 'calendar-empty';
                    grid.appendChild(emptyDiv);
                }

                const today = new Date();
                today.setHours(0, 0, 0, 0);

                for (let day = 1; day <= lastDay.getDate(); day++) {
                    const date = new Date(year, month, day);
                    const dayDiv = this.createDayElement(date, day, today);
                    grid.appendChild(dayDiv);
                }
            },

            cleanup() {
                this.boundDayHandlers.forEach((handler, dayDiv) => {
                    dayDiv.removeEventListener('click', handler);
                });
                this.boundDayHandlers.clear();
            },

            createDayElement(date, dayNumber, today) {
                const dayDiv = document.createElement('div');
                dayDiv.className = 'calendar-day';

                if (date < today) {
                    dayDiv.classList.add('disabled', 'past');
                }
                if (date.toDateString() === today.toDateString()) {
                    dayDiv.classList.add('today');
                }

                const dayNumberSpan = document.createElement('span');
                dayNumberSpan.className = 'day-number';
                dayNumberSpan.textContent = dayNumber;
                dayDiv.appendChild(dayNumberSpan);

                const isoDate = Utils.formatDateISO(date);
                const slots = APP_STATE.slotsByDate[isoDate] || [];

                if (slots.length > 0 && date >= today) {
                    dayDiv.classList.add('has-slots');
                    const slotsIndicator = document.createElement('div');
                    slotsIndicator.className = 'slots-indicator';
                    slotsIndicator.textContent = `${slots.length}`;
                    dayDiv.appendChild(slotsIndicator);
                }

                if (date >= today) {
                    const handler = () => this.selectDate(date, dayDiv);
                    dayDiv.addEventListener('click', handler);
                    this.boundDayHandlers.set(dayDiv, handler);
                }

                return dayDiv;
            },

            selectDate(date, dayElement) {
                document.querySelectorAll('.calendar-day').forEach(day => day.classList.remove('selected'));
                dayElement.classList.add('selected');
                APP_STATE.selectedDate = date;
                TimeSlots.render(Utils.formatDateISO(date));
            },

            async loadMonthSlots() {
                if (!APP_STATE.selectedDoctor) return;
                const year = APP_STATE.currentMonth.getFullYear();
                const month = APP_STATE.currentMonth.getMonth();
                const startDate = new Date(year, month, 1);
                const endDate = new Date(year, month + 1, 0);

                try {
                    const slots = await API.getDoctorSlots(APP_STATE.selectedDoctor.id, startDate, endDate);
                    APP_STATE.slotsByDate = {};
                    slots.forEach(slot => {
                        if (!slot.date) return;
                        if (!APP_STATE.slotsByDate[slot.date]) APP_STATE.slotsByDate[slot.date] = [];
                        APP_STATE.slotsByDate[slot.date].push(slot);
                    });
                    Object.keys(APP_STATE.slotsByDate).forEach(date => {
                        APP_STATE.slotsByDate[date].sort((a, b) => (a.heure || '00:00').localeCompare(b.heure || '00:00'));
                    });
                    this.render();
                } catch (error) {
                    console.error('Erreur lors du chargement des créneaux:', error);
                    Utils.showNotification('Erreur lors du chargement des disponibilités', 'error');
                }
            },

            previousMonth() {
                APP_STATE.currentMonth.setMonth(APP_STATE.currentMonth.getMonth() - 1);
                this.render();
                this.loadMonthSlots();
            },

            nextMonth() {
                APP_STATE.currentMonth.setMonth(APP_STATE.currentMonth.getMonth() + 1);
                this.render();
                this.loadMonthSlots();
            },

            destroy() { 
                this.cleanup(); 
            }
        };

        // =============================================================================
        // TIME SLOTS
        // =============================================================================

        const TimeSlots = {
            boundSlotHandlers: new Map(),

            render(isoDate) {
                const section = document.getElementById('time-slots-section');
                const container = document.getElementById('time-slots');
                const continueBtn = document.getElementById('step3-continue');
                if (!section || !container) return;

                this.cleanup();
                APP_STATE.selectedTime = null;
                APP_STATE.selectedSlot = null;
                if (continueBtn) continueBtn.disabled = true;
                section.style.display = 'block';
                container.innerHTML = '';

                const slots = APP_STATE.slotsByDate[isoDate] || [];
                if (slots.length === 0) {
                    container.innerHTML = `
                        <div style="text-align: center; padding: 20px; color: #6c757d;">
                            <i class="bx bx-calendar-x" style="font-size: 32px;"></i>
                            <p>Aucun créneau disponible pour cette date.</p>
                        </div>
                    `;
                    return;
                }

                const periods = { 
                    morning: { label: 'Matin', slots: [] }, 
                    afternoon: { label: 'Après-midi', slots: [] }, 
                    evening: { label: 'Soir', slots: [] } 
                };
                
                slots.forEach(slot => {
                    const time = Utils.parseTime(slot.heure);
                    if (!time) return;
                    if (time.hours < 12) periods.morning.slots.push(slot);
                    else if (time.hours < 18) periods.afternoon.slots.push(slot);
                    else periods.evening.slots.push(slot);
                });

                Object.values(periods).forEach(period => {
                    if (period.slots.length === 0) return;
                    const periodDiv = document.createElement('div');
                    periodDiv.className = 'time-period';
                    periodDiv.innerHTML = `<h4 class="period-label">${period.label}</h4>`;
                    const slotsDiv = document.createElement('div');
                    slotsDiv.className = 'time-slots-grid';
                    period.slots.forEach(slot => slotsDiv.appendChild(this.createSlotButton(slot)));
                    periodDiv.appendChild(slotsDiv);
                    container.appendChild(periodDiv);
                });
            },

            cleanup() {
                this.boundSlotHandlers.forEach((handler, btn) => btn.removeEventListener('click', handler));
                this.boundSlotHandlers.clear();
            },

            createSlotButton(slot) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'time-slot-btn';
                button.textContent = slot.heure || '--:--';

                const handler = () => {
                    document.querySelectorAll('.time-slot-btn').forEach(btn => btn.classList.remove('selected'));
                    button.classList.add('selected');
                    APP_STATE.selectedTime = slot.heure;
                    APP_STATE.selectedSlot = slot;
                    const continueBtn = document.getElementById('step3-continue');
                    if (continueBtn) continueBtn.disabled = false;
                };

                button.addEventListener('click', handler);
                this.boundSlotHandlers.set(button, handler);
                return button;
            },

            destroy() { 
                this.cleanup(); 
            }
        };

        // =============================================================================
        // BOOKING
        // =============================================================================

        const Booking = {
            confirmAppointment() {
                if (!APP_STATE.selectedDate || !APP_STATE.selectedTime || !APP_STATE.selectedDoctor) {
                    Utils.showNotification('Veuillez sélectionner une date et un créneau', 'error');
                    return;
                }
                this.openModal();
            },
            
            openModal() {
                const modal = document.getElementById('confirmation-modal');
                if (!modal) return;
                document.getElementById('summary-doctor').textContent = APP_STATE.selectedDoctor?.nom || '-';
                document.getElementById('summary-specialty').textContent = APP_STATE.selectedDoctor?.specialite_label || APP_STATE.specialtyName || '-';
                document.getElementById('summary-date').textContent = Utils.formatDateFR(APP_STATE.selectedDate) || '-';
                document.getElementById('summary-time').textContent = APP_STATE.selectedTime || '-';
                document.getElementById('summary-cabinet').textContent = APP_STATE.selectedDoctor?.cabinet || 'Non renseigné';
                const motifField = document.getElementById('motif');
                if (motifField) motifField.value = '';
                modal.classList.remove('hidden');
            },
            
            closeModal() {
                const modal = document.getElementById('confirmation-modal');
                if (modal) modal.classList.add('hidden');
            },
            
            async submitAppointment() {
                const submitBtn = document.getElementById('submit-btn');
                const submitText = document.getElementById('submit-text');
                const submitLoading = document.getElementById('submit-loading');

                if (!APP_STATE.selectedDoctor || !APP_STATE.selectedDate || !APP_STATE.selectedTime) {
                    Utils.showNotification('Données de réservation incomplètes', 'error');
                    return;
                }

                if (submitBtn) submitBtn.disabled = true;
                if (submitText) submitText.style.display = 'none';
                if (submitLoading) submitLoading.style.display = 'inline-block';

                try {
                    const datetime = Utils.combineDateAndTime(APP_STATE.selectedDate, APP_STATE.selectedTime);
                    if (!datetime) throw new Error('Impossible de construire la date et heure');
                    
                    const localISO = datetime.getFullYear() + "-" +
                        String(datetime.getMonth() + 1).padStart(2, "0") + "-" +
                        String(datetime.getDate()).padStart(2, "0") + "T" +
                        String(datetime.getHours()).padStart(2, "0") + ":" +
                        String(datetime.getMinutes()).padStart(2, "0") + ":00";

                    const motif = document.getElementById('motif')?.value || '';

                    const response = await fetch("/rdv/api/reserver/rdv/", {
                        method: "POST",
                        headers: { 
                            "Content-Type": "application/json", 
                            "X-CSRFToken": getCookie("csrftoken") 
                        },
                        body: JSON.stringify({ 
                            medecin_id: APP_STATE.selectedDoctor.id, 
                            datetime: localISO, 
                            motif: motif 
                        })
                    }).then(res => res.json());

                    if (response.success) {
                        Utils.showNotification(response.message || "Rendez-vous confirmé avec succès!", "success");
                        this.closeModal();
                        setTimeout(() => { 
                            window.location.href = "/rdv/liste_rdv_patient/"; 
                        }, 1500);
                    } else {
                        throw new Error(response.error || response.message || "Erreur lors de la réservation");
                    }
                } catch (error) {
                    console.error("Erreur lors de la réservation:", error);
                    Utils.showNotification(error.message || "Erreur lors de la réservation", "error");
                } finally {
                    if (submitBtn) submitBtn.disabled = false;
                    if (submitText) submitText.style.display = "inline";
                    if (submitLoading) submitLoading.style.display = "none";
                }
            }
        };

        // =============================================================================
        // NAVIGATION
        // =============================================================================

        const Navigation = {
            init() {
                window.previousStep = () => this.previousStep();
                window.nextStep = () => this.nextStep();
                window.previousMonth = () => Calendar.previousMonth();
                window.nextMonth = () => Calendar.nextMonth();
                window.confirmAppointment = () => Booking.confirmAppointment();
                window.closeModal = () => Booking.closeModal();
                window.submitAppointment = () => Booking.submitAppointment();
            },

            showStep(step) {
                if (step < 1 || step > 3) return;
                document.querySelectorAll('.content-section').forEach(section => section.classList.remove('active'));
                const activeSection = document.getElementById(`step-${step}`);
                if (activeSection) activeSection.classList.add('active');
                document.querySelectorAll('.step').forEach(stepEl => stepEl.classList.remove('active'));
                for (let i = 1; i <= step; i++) {
                    const stepEl = document.querySelector(`.step[data-step="${i}"]`);
                    if (stepEl) stepEl.classList.add('active');
                }
                APP_STATE.currentStep = step;
                if (step === 3) { 
                    Calendar.render(); 
                    Calendar.loadMonthSlots(); 
                }
            },

            async nextStep() {
                const currentStep = APP_STATE.currentStep;
                if (currentStep === 1) {
                    if (!APP_STATE.selectedSpecialty) { 
                        Utils.showNotification('Veuillez sélectionner une spécialité', 'error'); 
                        return; 
                    }
                    await DoctorList.load();
                    this.showStep(2);
                } else if (currentStep === 2) {
                    if (!APP_STATE.selectedDoctor) { 
                        Utils.showNotification('Veuillez sélectionner un médecin', 'error'); 
                        return; 
                    }
                    this.showStep(3);
                }
            },

            previousStep() {
                const currentStep = APP_STATE.currentStep;
                if (currentStep > 1) this.showStep(currentStep - 1);
            },

            reset() {
                APP_STATE.currentStep = 1; 
                APP_STATE.selectedSpecialty = null; 
                APP_STATE.specialtyName = '';
                APP_STATE.doctorsData = {}; 
                APP_STATE.selectedDoctor = null; 
                APP_STATE.selectedDate = null;
                APP_STATE.selectedTime = null; 
                APP_STATE.selectedSlot = null; 
                APP_STATE.slotsByDate = {};
                this.showStep(1);
            }
        };

        // =============================================================================
        // STYLES
        // =============================================================================

        function initStylesIfNeeded() {
            if (document.querySelector('#rdv-animations-style')) return;
            
            const style = document.createElement('style');
            style.id = 'rdv-animations-style';
            style.textContent = `
                @keyframes slideIn { 
                    from { transform: translateX(100%); opacity: 0; } 
                    to { transform: translateX(0); opacity: 1; } 
                }
                @keyframes slideOut { 
                    from { transform: translateX(0); opacity: 1; } 
                    to { transform: translateX(100%); opacity: 0; } 
                }
                .spinner-border { 
                    display: inline-block; 
                    width: 2rem; 
                    height: 2rem; 
                    border: .25em solid currentColor; 
                    border-right-color: transparent; 
                    border-radius: 50%; 
                    animation: spinner-border .75s linear infinite; 
                }
                @keyframes spinner-border { 
                    to { transform: rotate(360deg); } 
                }
                .calendar-day.disabled { 
                    opacity: 0.5; 
                    cursor: not-allowed; 
                    pointer-events: none; 
                }
                .calendar-day.today { 
                    background-color: #f0f8ff; 
                    font-weight: bold; 
                }
                .calendar-day.selected { 
                    background-color: #007bff; 
                    color: white; 
                }
                .doctor-card.selected { 
                    border: 2px solid #007bff; 
                    box-shadow: 0 0 0 3px rgba(0,123,255,0.25); 
                }
                .time-slot-btn.selected { 
                    background-color: #007bff; 
                    color: white; 
                }
                .slots-indicator { 
                    position: absolute; 
                    top: 2px; 
                    right: 2px; 
                    background: #28a745; 
                    color: white; 
                    border-radius: 50%; 
                    width: 20px; 
                    height: 20px; 
                    display: flex; 
                    align-items: center; 
                    justify-content: center; 
                    font-size: 10px; 
                    font-weight: bold; 
                }
                .time-period { 
                    margin-bottom: 20px; 
                } 
                .period-label { 
                    font-size: 14px; 
                    font-weight: 600; 
                    color: #6c757d; 
                    margin-bottom: 10px; 
                    text-transform: uppercase; 
                    letter-spacing: 0.5px; 
                } 
                .time-slots-grid { 
                    display: grid; 
                    grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); 
                    gap: 10px; 
                } 
                .loading { 
                    display: inline-block; 
                    width: 16px; 
                    height: 16px; 
                    border: 2px solid #ffffff; 
                    border-radius: 50%; 
                    border-top-color: transparent; 
                    animation: spin 0.6s linear infinite; 
                } 
                @keyframes spin { 
                    to { transform: rotate(360deg); } 
                }
            `;
            document.head.appendChild(style);
        }

        // =============================================================================
        // DETECTION DOM
        // =============================================================================

        function hasRdvElementsInDom() {
            return !!(
                document.getElementById('step-1') || 
                document.getElementById('doctor-list') || 
                document.querySelector('.speciality-card')
            );
        }

        // =============================================================================
        // INITIALISATION
        // =============================================================================

        function initPrendreRdv() {
            console.log('🔄 initPrendreRdv appelé');

            // Vérifier si les éléments RDV sont présents dans le DOM
            if (!hasRdvElementsInDom()) {
                console.log('⚠️ Éléments RDV non trouvés - initialisation annulée');
                return;
            }

            console.log('✅ Initialisation du module prendre_rdv');

            // Injecter les styles si nécessaire
            initStylesIfNeeded();

            // Réinitialiser l'état
            APP_STATE.currentStep = 1;
            APP_STATE.selectedSpecialty = null;
            APP_STATE.specialtyName = '';
            APP_STATE.doctorsData = {};
            APP_STATE.selectedDoctor = null;
            APP_STATE.selectedDate = null;
            APP_STATE.selectedTime = null;
            APP_STATE.selectedSlot = null;
            APP_STATE.currentMonth = new Date();
            APP_STATE.slotsByDate = {};
            APP_STATE.isLoading = false;

            // Nettoyer les anciennes instances
            try {
                SpecialtySelector.destroy();
                DoctorList.destroy();
                Calendar.destroy();
                TimeSlots.destroy();
            } catch (e) { 
                console.warn('Nettoyage ancien module:', e); 
            }

            // Initialiser les controllers
            Navigation.init();
            SpecialtySelector.init();

            // Exposer globalement les modules
            window.DoctorList = DoctorList;
            window.Navigation = Navigation;
            window.Booking = Booking;
            window.Calendar = Calendar;

            console.log('✅ Module prendre_rdv initialisé avec succès');
        }

        // =============================================================================
        // NETTOYAGE
        // =============================================================================

        function destroyPrendreRdv() {
            console.log('🧹 destroyPrendreRdv - nettoyage en cours');

            try {
                SpecialtySelector.destroy();
                DoctorList.destroy();
                Calendar.destroy();
                TimeSlots.destroy();
            } catch (e) { 
                console.warn('Erreur destroy modules:', e); 
            }

            // Supprimer les helpers globaux
            const helpers = [
                'previousStep', 'nextStep', 'previousMonth', 'nextMonth',
                'confirmAppointment', 'closeModal', 'submitAppointment',
                'DoctorList', 'Navigation', 'Booking', 'Calendar'
            ];
            
            helpers.forEach(name => {
                try { delete window[name]; } catch(e) {}
            });

            console.log('✅ Nettoyage terminé');
        }

        // =============================================================================
        // EXPOSITION GLOBALE
        // =============================================================================

        // Fonction principale appelée par runAllInits() de base.js
        window.initPrendreRdv = initPrendreRdv;
        
        // Fonction de nettoyage pour le cycle de vie AJAX
        window.destroyPrendreRdv = destroyPrendreRdv;
        
        // Fonction de réinitialisation forcée
        window.reinitPrendreRdv = function() {
            console.log('🔄 Réinitialisation forcée de prendre_rdv');
            destroyPrendreRdv();
            initPrendreRdv();
        };

        // =============================================================================
        // AUTO-INITIALISATION AU PREMIER CHARGEMENT
        // =============================================================================

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOMContentLoaded - première initialisation prendre_rdv');
                if (hasRdvElementsInDom()) {
                    initPrendreRdv();
                }
            });
        } else {
            // DOM déjà chargé, initialiser si éléments présents
            if (hasRdvElementsInDom()) {
                console.log('DOM déjà prêt - initialisation prendre_rdv');
                setTimeout(() => initPrendreRdv(), 0);
            }
        }

        // =============================================================================
        // ÉVÉNEMENT DE DÉCHARGEMENT
        // =============================================================================

        document.addEventListener('fragment:unloaded', function() {
            console.log('🔌 Fragment déchargé - nettoyage prendre_rdv');
            destroyPrendreRdv();
        });

        console.log('✅ prendre_rdv.js chargé et prêt (exposé window.initPrendreRdv)');

    })();
}

console.log('📦 Module prendre_rdv.js enregistré');