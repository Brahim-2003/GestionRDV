// static/rdv/js/patient/liste_attente.js

function initListeAttente() {
    const root = document.getElementById('liste-attente-root');
    if (!root) return;

    function getCookie(name) {
        const match = document.cookie.split(';')
            .map(c => c.trim())
            .find(c => c.startsWith(name + '='));
        return match ? decodeURIComponent(match.split('=')[1]) : '';
    }

    root.querySelectorAll('.js-desinscrire-liste-attente').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (!confirm("Annuler cette inscription en liste d'attente ?")) return;

            const url = btn.dataset.desinscrireUrl;
            btn.disabled = true;

            try {
                const res = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const data = await res.json();
                if (data.success) {
                    const row = btn.closest('tr');
                    if (row) row.remove();
                } else {
                    btn.disabled = false;
                }
            } catch (err) {
                console.error('Erreur désinscription liste d\'attente:', err);
                btn.disabled = false;
            }
        });
    });
}

window.initListeAttente = initListeAttente;
