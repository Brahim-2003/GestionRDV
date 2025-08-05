// static/rdv/js/admin/base.js

/**
 * Injecte et execute tous les <script> inline, et charge les <script src="">
 * en série avant d’appeler runAllInits().
 */
function injectAndExecuteScripts(container) {
  // Récupère tous les scripts du fragment
  const scripts = Array.from(container.querySelectorAll('script'));
  const externalLoads = [];

  scripts.forEach(old => {
    const s = document.createElement('script');
    // Inline
    if (!old.src) {
      s.textContent = old.textContent;
      document.body.appendChild(s);
    } else {
      // Externe : on crée une promise qui se résout au chargement
      const p = new Promise((resolve, reject) => {
        s.src = old.src;
        s.onload = resolve;
        s.onerror = reject;
      });
      // Important : charger immédiatement, sans async/defer
      s.async = false;
      document.body.appendChild(s);
      externalLoads.push(p);
    }
  });

  // Retourne une promesse qui se résout quand tous les externes sont chargés
  return Promise.all(externalLoads);
}

/**
 * Charge un fragment via AJAX dans #ajax-content,
 * injecte ses scripts, puis appelle runAllInits().
 */
function loadContent(url, pushState = true) {
  const contentDiv = document.getElementById('ajax-content');
  if (!contentDiv) return;

  contentDiv.innerHTML = '<p>Chargement…</p>';
  fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then(r => {
      if (!r.ok) throw new Error(`Erreur réseau ${r.status}`);
      return r.text();
    })
    .then(html => {
      contentDiv.innerHTML = html;
      // Injecte scripts et attend leur chargement
      return injectAndExecuteScripts(contentDiv)
        .then(() => {
          if (pushState) history.pushState({ url }, '', url);
          runAllInits();
        });
    })
    .catch(err => {
      console.error('Erreur AJAX loadContent:', err);
      contentDiv.innerHTML = '<p>Erreur lors du chargement.</p>';
    });
}

/**
 * Exécute toutes les fonctions window.initXXX()
 */
function runAllInits() {
  Object.keys(window).forEach(key => {
    if (key.startsWith('init') && typeof window[key] === 'function') {
      try { window[key](); }
      catch (e) { console.error(`Erreur dans ${key}():`, e); }
    }
  });
}

/**
 * Lie la navigation par onglets en AJAX
 */
function setupNavTabs() {
  document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.onclick = null;
    tab.addEventListener('click', e => {
      e.preventDefault();
      loadContent(tab.href);
    });
  });
}

// Historique back/forward
window.addEventListener('popstate', e => {
  if (e.state?.url) loadContent(e.state.url, false);
});

// Au premier chargement de la page
window.addEventListener('DOMContentLoaded', () => {
  setupNavTabs();
  runAllInits();
});

// Expose pour debug / usage manuel
window.loadContent = loadContent;
window.runAllInits = runAllInits;
