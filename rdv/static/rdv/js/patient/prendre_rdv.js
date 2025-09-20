// ====================
// Variables globales
// ====================
let currentStep = 1;
let selectedSpecialty = null;
let selectedDoctor = null;
let selectedDate = null;
let selectedTime = null;
let currentMonth = new Date();
let doctorData = {};
let specialtyName = "";


// ====================
// Navigation Steps
// ====================
function showStep(step) {
    document.querySelectorAll(".content-section").forEach(s => s.classList.remove("active"));
    document.getElementById(`step-${step}`).classList.add("active");

    document.querySelectorAll(".step").forEach(s => s.classList.remove("active"));
    for (let i = 1; i <= step; i++) {
        document.querySelector(`.step[data-step="${i}"]`).classList.add("active");
    }
    currentStep = step;
}
// --- nextStep (devient async) ---
async function nextStep() {
    if (currentStep === 1) {
        if (!selectedSpecialty) return alert("Veuillez choisir une spécialité.");
        // Charger les médecins pour la spécialité avant d'afficher l'étape 2
        try {
            await loadDoctors(selectedSpecialty);
        } catch (err) {
            console.error("Erreur lors du chargement des médecins dans nextStep:", err);
            return alert("Impossible de charger les médecins. Réessayez.");
        }
        // passer à l'étape 2
        goToStep(2);
        return;
    }

    if (currentStep === 2) {
        if (!selectedDoctor) return alert("Veuillez choisir un médecin.");
        goToStep(3);
        // précharger créneaux pour mois courant si nécessaire
        await fetchCreneauxForMonth(selectedDoctor, calendarYear, calendarMonth);
        renderCalendarMonth(calendarYear, calendarMonth);
        return;
    }

    if (currentStep === 3) {
        if (!selectedDate || !selectedTime) return alert("Veuillez choisir une date et un créneau.");
        confirmAppointment();
        return;
    }
}

function previousStep() {
    if (currentStep > 1) showStep(currentStep - 1);
}


// ====================
// Step 1: Spécialité
// ====================
document.querySelectorAll(".speciality-card").forEach(card => {
    card.addEventListener("click", () => {
        document.querySelectorAll(".speciality-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");

        selectedSpecialty = card.dataset.speciality;
        specialtyName = card.querySelector(".speciality-name").innerText;
        document.getElementById("step1-continue").disabled = false;
    });
});
document.getElementById("step1-continue").addEventListener("click", async () => {
    await loadDoctors();
    nextStep();
});


// --- loadDoctors corrigée (gère { medecins: [...] } ) ---
async function loadDoctors(specialty) {
    const list = document.getElementById('doctor-list');
    if (!list) return;
    list.innerHTML = '<div style="padding:20px;">Chargement des médecins…</div>';

    try {
        const url = new URL('/rdv/api/search/medecins/', window.location.origin);
        url.searchParams.append('specialite', specialty);
        const resp = await fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });

        if (!resp.ok) throw new Error(`Erreur HTTP ${resp.status}`);

        const json = await resp.json();

        // Adapter au format attendu : json.medecins OR json (cas où API renverrait directement tableau)
        const doctors = Array.isArray(json) ? json : (Array.isArray(json.medecins) ? json.medecins : []);

        doctorsData = {}; // reset
        list.innerHTML = '';

        if (doctors.length === 0) {
            list.innerHTML = `<div style="text-align:center; padding:30px; color:var(--gray-600);">
                <i class="bx bx-user-x" style="font-size:36px;"></i>
                <p>Aucun médecin disponible pour cette spécialité.</p>
            </div>`;
            return;
        }

        doctors.forEach(doc => {
            doctorsData[doc.id] = doc;
            const card = document.createElement('div');
            card.className = 'doctor-card';
            card.dataset.doctorId = doc.id;
            card.innerHTML = `
                <div class="doctor-photo">${doc.photo_url ? `<img src="${escapeHtml(doc.photo_url)}" alt="photo">` : `<div class="photo-placeholder">${escapeHtml((doc.nom||'?')[0])}</div>`}</div>
                <div class="doctor-info">
                    <div class="doctor-name">${escapeHtml(doc.nom || '—')}</div>
                    <div class="doctor-meta">
                        <div class="meta-item"><i class="bx bx-building"></i> ${escapeHtml(doc.cabinet || '—')}</div>
                        <div class="meta-item"><i class="bx bx-globe"></i> ${escapeHtml(doc.langues || '—')}</div>
                    </div>
                </div>
                <div class="doctor-actions">
                    <button type="button" class="choose-doctor-btn">Choisir</button>
                </div>
            `;
            // events
            card.querySelector('.choose-doctor-btn').addEventListener('click', (ev) => {
                ev.stopPropagation();
                onSelectDoctor(doc.id, card);
            });
            card.addEventListener('click', () => onSelectDoctor(doc.id, card));
            list.appendChild(card);
        });

    } catch (err) {
        console.error('loadDoctors error', err);
        list.innerHTML = `<div style="color:crimson; padding:20px;">Erreur lors du chargement des médecins.</div>`;
        throw err; // on remonte pour que nextStep puisse gérer si besoin
    }
}


// ====================
// Step 3: Calendrier
// ====================
function renderCalendar() {
    const grid = document.getElementById("calendar-grid");
    const title = document.getElementById("calendar-title");

    grid.querySelectorAll(".calendar-day").forEach(d => d.remove());

    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    title.textContent = currentMonth.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });

    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const startDay = (firstDay.getDay() + 6) % 7;

    for (let i = 0; i < startDay; i++) {
        grid.appendChild(document.createElement("div"));
    }

    for (let d = 1; d <= lastDay.getDate(); d++) {
        const date = new Date(year, month, d);
        const div = document.createElement("div");
        div.className = "calendar-day";
        div.textContent = d;

        div.addEventListener("click", () => {
            document.querySelectorAll(".calendar-day").forEach(c => c.classList.remove("selected"));
            div.classList.add("selected");
            selectedDate = date;
            loadTimeSlots(date);
        });

        grid.appendChild(div);
    }
}
function previousMonth() {
    currentMonth.setMonth(currentMonth.getMonth() - 1);
    renderCalendar();
}
function nextMonth() {
    currentMonth.setMonth(currentMonth.getMonth() + 1);
    renderCalendar();
}
async function loadTimeSlots(date) {
    const section = document.getElementById("time-slots-section");
    const container = document.getElementById("time-slots");
    section.style.display = "block";
    container.innerHTML = "Chargement...";

    try {
        const start = new Date(date);
        const end = new Date(date);
        end.setHours(23, 59, 59);

        const res = await fetch(`/rdv/api/creneaux/medecins/?medecin_id=${selectedDoctor.id}&date_debut=${start.toISOString()}&date_fin=${end.toISOString()}`);
        const slots = await res.json();
        container.innerHTML = "";

        if (slots.length === 0) {
            container.innerHTML = "<p>Aucune disponibilité pour ce jour.</p>";
            return;
        }

        slots.forEach(slot => {
            const btn = document.createElement("button");
            btn.className = "time-slot-btn";
            btn.textContent = slot.heure;
            btn.addEventListener("click", () => {
                document.querySelectorAll(".time-slot-btn").forEach(b => b.classList.remove("selected"));
                btn.classList.add("selected");
                selectedTime = slot.heure;
                document.getElementById("step3-continue").disabled = false;
            });
            container.appendChild(btn);
        });
    } catch (e) {
        container.innerHTML = "<p>Erreur de chargement</p>";
    }
}


// ====================
// Confirmation
// ====================
function confirmAppointment() {
    document.getElementById("summary-doctor").innerText = doctorData.nom;
    document.getElementById("summary-specialty").innerText = specialtyName;
    document.getElementById("summary-date").innerText = selectedDate.toLocaleDateString("fr-FR");
    document.getElementById("summary-time").innerText = selectedTime;
    document.getElementById("summary-cabinet").innerText = doctorData.cabinet || "-";
    document.getElementById("summary-price").innerText = doctorData.tarif ? doctorData.tarif + " €" : "-";

    document.getElementById("confirmation-modal").classList.remove("hidden");
}
function closeModal() {
    document.getElementById("confirmation-modal").classList.add("hidden");
}
async function submitAppointment() {
    const btn = document.getElementById("submit-btn");
    const txt = document.getElementById("submit-text");
    const loading = document.getElementById("submit-loading");

    txt.style.display = "none";
    loading.style.display = "inline-block";

    try {
        const motif = document.getElementById("motif").value;
        const res = await fetch("/rdv/api/reserver/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": getCSRFToken() },
            body: JSON.stringify({
                medecin_id: doctorData.id,
                date: selectedDate.toISOString().split("T")[0],
                heure: selectedTime,
                motif: motif
            })
        });
        const data = await res.json();

        if (res.ok) {
            alert("Rendez-vous confirmé !");
            window.location.href = "/rdv/liste_rdv_patient/";
        } else {
            alert("Erreur : " + (data.message || "Impossible de réserver"));
        }
    } catch (e) {
        alert("Erreur de connexion");
    } finally {
        txt.style.display = "inline";
        loading.style.display = "none";
    }
}
function getCSRFToken() {
    const name = "csrftoken";
    const cookies = document.cookie.split("; ");
    for (let cookie of cookies) {
        if (cookie.startsWith(name + "=")) {
            return cookie.split("=")[1];
        }
    }
    return "";
}


// ====================
// Init
// ====================
document.addEventListener("DOMContentLoaded", () => {
    renderCalendar();
});
