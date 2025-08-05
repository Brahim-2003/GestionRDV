// static/rdv/js/admin/users/users.js

function handleReset(e) {
  e.preventDefault();
  e.stopPropagation();
  document.getElementById('search-input').value = '';
  document.getElementById('role-select').value  = '';
  // Recharge la table (table-only=1)
  if (typeof window.fetchTable === 'function') {
    window.fetchTable({});
  }
}

function initUsers() {
  // Supprime/attache le listener de suppression sur chaque icône 🗑️
  document.querySelectorAll('.action-btn-delete').forEach(link => {
    link.removeEventListener('click', handleDeleteClick);
    link.addEventListener('click', handleDeleteClick);
  });

  // Supprime/attache le listener reset
  const resetBtn = document.getElementById('reset-btn');
  if (resetBtn) {
    resetBtn.removeEventListener('click', handleReset);
    resetBtn.addEventListener('click', handleReset);
  }
}

// Expose pour base.js
window.initUsers = initUsers;
