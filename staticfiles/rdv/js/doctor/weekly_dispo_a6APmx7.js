/**
 * Gestion complète des disponibilités hebdomadaires
 * Inclut : activation/désactivation, ajout, modification, suppression
 */

class WeeklyDispoManager {
    constructor() {
        this.calendar = document.getElementById('weekly-calendar');
        this.createModal = document.getElementById('create-dispo-modal');
        this.editModal = document.getElementById('edit-dispo-modal');
        this.init();
    }

    init() {
        if (!this.calendar) return;
        
        this.attachEventListeners();
        this.initializeTooltips();
    }

    attachEventListeners() {
        // Délégation d'événements pour toutes les actions
        this.calendar.addEventListener('click', (e) => {
            const target = e.target.closest('button');
            if (!target) return;

            if (target.classList.contains('toggle-btn')) {
                this.handleToggle(target);
            } else if (target.classList.contains('edit-btn')) {
                this.handleEdit(target);
            } else if (target.classList.contains('delete-btn')) {
                this.handleDelete(target);
            } else if (target.classList.contains('add-slot-btn')) {
                this.handleAddSlot(target);
            }
        });

        // Gestion des soumissions de formulaires dans les modaux
        this.setupModalFormHandlers();
    }

    /**
     * Activation/Désactivation d'un créneau
     */
    async handleToggle(button) {
        const dispoId = button.dataset.dispoId;
        const timeSlot = button.closest('.time-slot');
        const isActive = timeSlot.classList.contains('active');
        
        // Désactiver le bouton pendant l'opération
        button.disabled = true;
        
        try {
            const response = await fetch(`/rdv/disponibilite/${dispoId}/toggle/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ is_active: !isActive })
            });

            if (response.ok) {
                const data = await response.json();
                this.updateSlotStatus(timeSlot, button, data.is_active);
                this.showNotification(
                    data.is_active ? 'Créneau activé' : 'Créneau désactivé',
                    'success'
                );
            } else {
                throw new Error('Erreur lors de la mise à jour');
            }
        } catch (error) {
            console.error('Erreur:', error);
            this.showNotification('Erreur lors de la mise à jour du créneau', 'error');
        } finally {
            button.disabled = false;
        }
    }

    /**
     * Mise à jour visuelle du statut d'un créneau
     */
    updateSlotStatus(slot, toggleBtn, isActive) {
        // Mise à jour des classes
        slot.classList.toggle('active', isActive);
        slot.classList.toggle('inactive', !isActive);
        slot.dataset.active = isActive ? 'true' : 'false';
        
        // Mise à jour de l'icône du bouton toggle
        const icon = toggleBtn.querySelector('i');
        if (icon) {
            icon.className = isActive ? 'bx bx-toggle-right' : 'bx bx-toggle-left';
        }
        toggleBtn.title = isActive ? 'Désactiver' : 'Activer';
        
        // Animation visuelle
        this.animateSlotChange(slot);
    }

    /**
     * Animation lors du changement de statut
     */
    animateSlotChange(slot) {
        slot.style.transition = 'all 0.3s ease';
        slot.style.transform = 'scale(1.02)';
        
        setTimeout(() => {
            slot.style.transform = 'scale(1)';
        }, 300);
    }

    /**
     * Modification d'un créneau
     */
    async handleEdit(button) {
        const dispoId = button.dataset.dispoId;
        const editUrl = button.dataset.editUrl;
        
        if (!editUrl || !this.editModal) return;
        
        // Ouvrir le modal d'édition
        this.editModal.classList.remove('hidden');
        const formContainer = this.editModal.querySelector('#edit-modal-form-container');
        
        // Afficher un loader
        formContainer.innerHTML = '<div class="loader">Chargement...</div>';
        
        try {
            const response = await fetch(editUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const html = await response.text();
                formContainer.innerHTML = html;
                
                // Attacher le gestionnaire de soumission du formulaire
                const form = formContainer.querySelector('form');
                if (form) {
                    this.attachFormHandler(form, 'edit');
                }
            } else {
                throw new Error('Erreur lors du chargement du formulaire');
            }
        } catch (error) {
            console.error('Erreur:', error);
            formContainer.innerHTML = '<p class="error">Erreur lors du chargement du formulaire</p>';
        }
    }

    /**
     * Suppression d'un créneau
     */
    async handleDelete(button) {
        const dispoId = button.dataset.dispoId;
        const deleteUrl = button.dataset.deleteUrl;
        const timeSlot = button.closest('.time-slot');
        
        // Confirmation de suppression
        if (!confirm('Êtes-vous sûr de vouloir supprimer ce créneau ?')) {
            return;
        }
        
        // Désactiver le bouton pendant l'opération
        button.disabled = true;
        
        try {
            const response = await fetch(deleteUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': this.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (response.ok) {
                // Animation de suppression
                timeSlot.style.animation = 'slideOut 0.3s ease-out';
                
                setTimeout(() => {
                    timeSlot.remove();
                    this.checkEmptyState(button.closest('.day-column'));
                }, 300);
                
                this.showNotification('Créneau supprimé avec succès', 'success');
            } else {
                throw new Error('Erreur lors de la suppression');
            }
        } catch (error) {
            console.error('Erreur:', error);
            this.showNotification('Erreur lors de la suppression du créneau', 'error');
            button.disabled = false;
        }
    }

    /**
     * Ajout d'un nouveau créneau
     */
    async handleAddSlot(button) {
        const dayKey = button.dataset.day;
        const formUrl = button.dataset.formUrl;
        
        if (!formUrl || !this.createModal) return;
        
        // Ouvrir le modal de création
        this.createModal.classList.remove('hidden');
        const formContainer = this.createModal.querySelector('#modal-form-container');
        
        // Afficher un loader
        formContainer.innerHTML = '<div class="loader">Chargement...</div>';
        
        try {
            const response = await fetch(formUrl, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const html = await response.text();
                formContainer.innerHTML = html;
                
                // Pré-remplir le jour de la semaine
                const jourField = formContainer.querySelector('[name="jour"]');
                if (jourField) {
                    jourField.value = dayKey;
                }
                
                // Sélectionner automatiquement "hebdomadaire" comme type
                const typeField = formContainer.querySelector('[name="type_disponibilite"]');
                if (typeField) {
                    typeField.value = 'hebdomadaire';
                    this.toggleDateField(typeField);
                }
                
                // Attacher le gestionnaire de soumission du formulaire
                const form = formContainer.querySelector('form');
                if (form) {
                    this.attachFormHandler(form, 'create', dayKey);
                }
            } else {
                throw new Error('Erreur lors du chargement du formulaire');
            }
        } catch (error) {
            console.error('Erreur:', error);
            formContainer.innerHTML = '<p class="error">Erreur lors du chargement du formulaire</p>';
        }
    }

    /**
     * Configuration des gestionnaires de formulaires dans les modaux
     */
    setupModalFormHandlers() {
        // Fermeture des modaux
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const modal = e.target.closest('.modal-overlay');
                if (modal) {
                    modal.classList.add('hidden');
                }
            });
        });

        // Fermeture en cliquant en dehors du modal
        document.querySelectorAll('.modal-overlay').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    modal.classList.add('hidden');
                }
            });
        });
    }

    /**
     * Attacher le gestionnaire de soumission au formulaire
     */
    attachFormHandler(form, action, dayKey = null) {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const submitBtn = form.querySelector('[type="submit"]');
            const originalText = submitBtn ? submitBtn.textContent : '';
            
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Enregistrement...';
            }
            
            try {
                const formData = new FormData(form);
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                if (response.ok) {
                    const data = await response.json();
                    
                    if (data.success) {
                        // Fermer le modal
                        const modal = form.closest('.modal-overlay');
                        if (modal) {
                            modal.classList.add('hidden');
                        }
                        
                        // Mettre à jour l'interface
                        if (action === 'create' && dayKey) {
                            this.addNewSlotToDay(dayKey, data.dispo);
                        } else if (action === 'edit') {
                            this.updateExistingSlot(data.dispo);
                        }
                        
                        this.showNotification(
                            action === 'create' ? 'Créneau ajouté avec succès' : 'Créneau modifié avec succès',
                            'success'
                        );
                    } else {
                        // Afficher les erreurs de validation
                        this.displayFormErrors(form, data.errors);
                    }
                } else {
                    throw new Error('Erreur lors de la sauvegarde');
                }
            } catch (error) {
                console.error('Erreur:', error);
                this.showNotification('Erreur lors de la sauvegarde', 'error');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = originalText;
                }
            }
        });
    }

    /**
     * Ajouter un nouveau créneau dans l'interface
     */
    addNewSlotToDay(dayKey, dispoData) {
        const dayColumn = this.calendar.querySelector(`.day-column[data-day="${dayKey}"]`);
        if (!dayColumn) return;
        
        const slotsContainer = dayColumn.querySelector('.slots-container');
        
        // Retirer l'état vide s'il existe
        const emptyState = slotsContainer.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        // Créer le nouvel élément de créneau
        const newSlot = this.createSlotElement(dispoData);
        
        // Ajouter le créneau au conteneur avec animation
        newSlot.style.animation = 'slideIn 0.3s ease-out';
        slotsContainer.appendChild(newSlot);
        
        // Trier les créneaux par heure
        this.sortSlots(slotsContainer);
    }

    /**
     * Créer un élément DOM pour un créneau
     */
    createSlotElement(dispoData) {
        const div = document.createElement('div');
        div.className = `time-slot ${dispoData.is_active ? 'active' : 'inactive'}`;
        div.dataset.dispoId = dispoData.id;
        div.dataset.active = dispoData.is_active ? 'true' : 'false';
        
        div.innerHTML = `
            <span class="time-range">${dispoData.heure_debut} - ${dispoData.heure_fin}</span>
            <div class="slot-actions">
                <button class="toggle-btn" 
                        data-dispo-id="${dispoData.id}"
                        title="${dispoData.is_active ? 'Désactiver' : 'Activer'}">
                    <i class="bx bx-toggle-${dispoData.is_active ? 'right' : 'left'}"></i>
                </button>
                <button class="edit-btn" 
                        data-dispo-id="${dispoData.id}"
                        data-edit-url="/rdv/disponibilite/${dispoData.id}/edit/"
                        title="Modifier">
                    <i class="bx bxs-edit"></i>
                </button>
                <button class="delete-btn" 
                        data-dispo-id="${dispoData.id}"
                        data-delete-url="/rdv/disponibilite/${dispoData.id}/delete/"
                        title="Supprimer">
                    <i class="bx bxs-trash-alt"></i>
                </button>
            </div>
        `;
        
        return div;
    }

    /**
     * Mettre à jour un créneau existant
     */
    updateExistingSlot(dispoData) {
        const slot = this.calendar.querySelector(`.time-slot[data-dispo-id="${dispoData.id}"]`);
        if (!slot) return;
        
        // Mettre à jour le texte de l'heure
        const timeRange = slot.querySelector('.time-range');
        if (timeRange) {
            timeRange.textContent = `${dispoData.heure_debut} - ${dispoData.heure_fin}`;
        }
        
        // Mettre à jour le statut si nécessaire
        this.updateSlotStatus(slot, slot.querySelector('.toggle-btn'), dispoData.is_active);
        
        // Animation de mise à jour
        this.animateSlotChange(slot);
    }

    /**
     * Trier les créneaux par heure de début
     */
    sortSlots(container) {
        const slots = Array.from(container.querySelectorAll('.time-slot'));
        
        slots.sort((a, b) => {
            const timeA = a.querySelector('.time-range').textContent.split(' - ')[0];
            const timeB = b.querySelector('.time-range').textContent.split(' - ')[0];
            return timeA.localeCompare(timeB);
        });
        
        // Réorganiser les éléments dans le DOM
        slots.forEach(slot => container.appendChild(slot));
    }

    /**
     * Vérifier et afficher l'état vide si nécessaire
     */
    checkEmptyState(dayColumn) {
        const slotsContainer = dayColumn.querySelector('.slots-container');
        const slots = slotsContainer.querySelectorAll('.time-slot');
        
        if (slots.length === 0) {
            const emptyState = document.createElement('div');
            emptyState.className = 'empty-state';
            emptyState.innerHTML = `
                <i class="bx bx-calendar-x"></i>
                <span>Aucun créneau configuré</span>
            `;
            slotsContainer.appendChild(emptyState);
        }
    }

    /**
     * Afficher les erreurs de validation du formulaire
     */
    displayFormErrors(form, errors) {
        // Nettoyer les erreurs précédentes
        form.querySelectorAll('.error-message').forEach(el => el.remove());
        form.querySelectorAll('.field-error').forEach(el => el.classList.remove('field-error'));
        
        // Afficher les nouvelles erreurs
        for (const [field, messages] of Object.entries(errors)) {
            const fieldElement = form.querySelector(`[name="${field}"]`);
            if (fieldElement) {
                fieldElement.classList.add('field-error');
                
                const errorDiv = document.createElement('div');
                errorDiv.className = 'error-message';
                errorDiv.textContent = messages.join(' ');
                
                fieldElement.parentElement.appendChild(errorDiv);
            }
        }
    }

    /**
     * Basculer l'affichage du champ de date selon le type
     */
    toggleDateField(typeField) {
        const form = typeField.closest('form');
        const dateField = form.querySelector('[name="date_specific"]');
        const dateContainer = dateField ? dateField.closest('.form-group') : null;
        
        if (dateContainer) {
            if (typeField.value === 'hebdomadaire') {
                dateContainer.style.display = 'none';
                if (dateField) dateField.required = false;
            } else {
                dateContainer.style.display = 'block';
                if (dateField) dateField.required = true;
            }
        }
    }

    /**
     * Afficher une notification
     */
    showNotification(message, type = 'info') {
        // Créer ou réutiliser le conteneur de notifications
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
            `;
            document.body.appendChild(container);
        }
        
        // Créer la notification
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            animation: slideInRight 0.3s ease-out;
            display: flex;
            align-items: center;
            gap: 10px;
            min-width: 300px;
        `;
        
        // Icône selon le type
        const icon = type === 'success' ? 'bx-check-circle' : 
                     type === 'error' ? 'bx-x-circle' : 'bx-info-circle';
        
        notification.innerHTML = `
            <i class="bx ${icon}" style="font-size: 20px;"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(notification);
        
        // Retirer automatiquement après 5 secondes
        setTimeout(() => {
            notification.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => {
                notification.remove();
                // Retirer le conteneur s'il est vide
                if (container.children.length === 0) {
                    container.remove();
                }
            }, 300);
        }, 5000);
    }

    /**
     * Récupérer le token CSRF
     */
    getCSRFToken() {
        const cookieValue = document.cookie
            .split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
        
        if (!cookieValue) {
            const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
            return tokenInput ? tokenInput.value : '';
        }
        
        return cookieValue;
    }

    /**
     * Initialiser les tooltips
     */
    initializeTooltips() {
        // Initialisation des tooltips si une bibliothèque est utilisée
        if (typeof tippy !== 'undefined') {
            tippy('[title]', {
                theme: 'light',
                animation: 'scale',
                duration: [200, 150]
            });
        }
    }

    /**
     * Actualiser le calendrier hebdomadaire
     */
    async refreshWeeklyCalendar() {
        try {
            const response = await fetch('/rdv/disponibilites/weekly/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            if (response.ok) {
                const html = await response.text();
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = html;
                
                const newCalendar = tempDiv.querySelector('#weekly-calendar');
                if (newCalendar && this.calendar) {
                    this.calendar.innerHTML = newCalendar.innerHTML;
                    this.attachEventListeners();
                    this.initializeTooltips();
                }
            }
        } catch (error) {
            console.error('Erreur lors du rafraîchissement:', error);
        }
    }

    /**
     * Méthode pour vérifier les conflits d'horaires
     */
    checkTimeConflicts(dayKey, startTime, endTime, excludeId = null) {
        const dayColumn = this.calendar.querySelector(`.day-column[data-day="${dayKey}"]`);
        if (!dayColumn) return false;
        
        const slots = dayColumn.querySelectorAll('.time-slot');
        
        for (const slot of slots) {
            if (excludeId && slot.dataset.dispoId === excludeId) continue;
            
            const timeRange = slot.querySelector('.time-range').textContent;
            const [slotStart, slotEnd] = timeRange.split(' - ');
            
            // Vérifier le chevauchement
            if (this.isTimeOverlap(startTime, endTime, slotStart, slotEnd)) {
                return true;
            }
        }
        
        return false;
    }

    /**
     * Vérifier le chevauchement de deux plages horaires
     */
    isTimeOverlap(start1, end1, start2, end2) {
        const toMinutes = (time) => {
            const [hours, minutes] = time.split(':').map(Number);
            return hours * 60 + minutes;
        };
        
        const start1Min = toMinutes(start1);
        const end1Min = toMinutes(end1);
        const start2Min = toMinutes(start2);
        const end2Min = toMinutes(end2);
        
        return (start1Min < end2Min && end1Min > start2Min);
    }

    /**
     * Exporter les créneaux hebdomadaires
     */
    exportWeeklySlots() {
        const slots = [];
        
        this.calendar.querySelectorAll('.day-column').forEach(column => {
            const day = column.dataset.day;
            column.querySelectorAll('.time-slot').forEach(slot => {
                const timeRange = slot.querySelector('.time-range').textContent;
                const [start, end] = timeRange.split(' - ');
                
                slots.push({
                    day: day,
                    start_time: start,
                    end_time: end,
                    is_active: slot.dataset.active === 'true'
                });
            });
        });
        
        return slots;
    }

    /**
     * Dupliquer les créneaux d'un jour vers un autre
     */
    async duplicateDaySlots(fromDay, toDay) {
        const fromColumn = this.calendar.querySelector(`.day-column[data-day="${fromDay}"]`);
        const toColumn = this.calendar.querySelector(`.day-column[data-day="${toDay}"]`);
        
        if (!fromColumn || !toColumn) return;
        
        const slots = fromColumn.querySelectorAll('.time-slot');
        if (slots.length === 0) {
            this.showNotification('Aucun créneau à dupliquer', 'warning');
            return;
        }
        
        // Confirmation
        if (!confirm(`Dupliquer les ${slots.length} créneaux vers ${this.getDayName(toDay)} ?`)) {
            return;
        }
        
        try {
            for (const slot of slots) {
                const timeRange = slot.querySelector('.time-range').textContent;
                const [start, end] = timeRange.split(' - ');
                
                // Créer le nouveau créneau via l'API
                await this.createSlot({
                    jour: toDay,
                    heure_debut: start,
                    heure_fin: end,
                    type_disponibilite: 'hebdomadaire',
                    is_active: slot.dataset.active === 'true'
                });
            }
            
            // Rafraîchir le calendrier
            await this.refreshWeeklyCalendar();
            this.showNotification('Créneaux dupliqués avec succès', 'success');
        } catch (error) {
            console.error('Erreur lors de la duplication:', error);
            this.showNotification('Erreur lors de la duplication', 'error');
        }
    }

    /**
     * Créer un créneau via l'API
     */
    async createSlot(data) {
        const formData = new FormData();
        for (const [key, value] of Object.entries(data)) {
            formData.append(key, value);
        }
        
        const response = await fetch('/rdv/disponibilite/add/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': this.getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (!response.ok) {
            throw new Error('Erreur lors de la création du créneau');
        }
        
        return await response.json();
    }

    /**
     * Obtenir le nom du jour
     */
    getDayName(dayKey) {
        const days = {
            'mon': 'Lundi',
            'tue': 'Mardi',
            'wed': 'Mercredi',
            'thu': 'Jeudi',
            'fri': 'Vendredi',
            'sat': 'Samedi',
            'sun': 'Dimanche'
        };
        return days[dayKey] || dayKey;
    }

    /**
     * Statistiques des créneaux
     */
    getStats() {
        const stats = {
            total: 0,
            active: 0,
            inactive: 0,
            byDay: {}
        };
        
        this.calendar.querySelectorAll('.day-column').forEach(column => {
            const day = column.dataset.day;
            const slots = column.querySelectorAll('.time-slot');
            
            stats.byDay[day] = {
                total: slots.length,
                active: 0,
                inactive: 0
            };
            
            slots.forEach(slot => {
                stats.total++;
                if (slot.dataset.active === 'true') {
                    stats.active++;
                    stats.byDay[day].active++;
                } else {
                    stats.inactive++;
                    stats.byDay[day].inactive++;
                }
            });
        });
        
        return stats;
    }
}

// CSS pour les animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100%);
        }
    }
    
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100%);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    @keyframes slideOutRight {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(100%);
        }
    }
    
    .field-error {
        border-color: #ef4444 !important;
    }
    
    .error-message {
        color: #ef4444;
        font-size: 12px;
        margin-top: 4px;
    }
    
    .loader {
        text-align: center;
        padding: 20px;
        color: #666;
    }
    
    .loader::after {
        content: '...';
        animation: dots 1.5s steps(4, end) infinite;
    }
    
    @keyframes dots {
        0%, 20% { content: '.'; }
        40% { content: '..'; }
        60%, 100% { content: '...'; }
    }
`;
document.head.appendChild(style);

// Initialiser le gestionnaire au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    window.weeklyDispoManager = new WeeklyDispoManager();
});