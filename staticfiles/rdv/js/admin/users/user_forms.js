document.addEventListener('DOMContentLoaded', function() {
  // identifie le formulaire (inscription ou admin)
  const form = document.querySelector('#create-user-form, #inscription-form');
  if (!form) return;

  form.addEventListener('submit', function(e) {
    e.preventDefault();
    
    const url = form.action;
    const data = new FormData(form);

    fetch(url, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      body: data
    })
    .then(r => {
      if (r.ok) return r.json();
      return r.json().then(err => Promise.reject(err));
    })
    .then(json => {
      if (json.status === 'ok') {
        // Si on est sur la liste admin, on recharge le tableau
        if (window.fetchTable) {
          window.fetchTable();
        }
        // Sinon, message de succès pour inscription
        else {
          alert('Inscription réussie ! Vous pouvez maintenant vous connecter.');
          form.reset();
        }
      } else {
        // Affiche les erreurs (simplement)
        console.error(json.errors);
        alert('Erreurs : ' + JSON.stringify(json.errors));
      }
    })
    .catch(err => {
      console.error('Erreur AJAX :', err);
      alert('Une erreur est survenue');
    });
  });
});
