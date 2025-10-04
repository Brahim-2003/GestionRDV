// static/rdv/js/doctor/base_doctor.js

function injectAndExecuteScripts(container) {
  const scripts = Array.from(container.querySelectorAll('script'));
  const loads = [];

  scripts.forEach(old => {
    const s = document.createElement('script');
    // Inline
    if (!old.src) {
      s.textContent = old.textContent;
    } else {
      // Externe
      loads.push(new Promise((res, rej) => {
        s.src = old.src;
        s.onload = res;
        s.onerror = rej;
      }));
      s.async = false;
    }
    document.body.appendChild(s);
  });

  return Promise.all(loads);
}

/**
 * Normalise un path (supprime slash final, query & hash).
 */
function normalizePath(path) {
  let p = path.split('?')[0].split('#')[0];
  if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
  return p || '/';
}

/**
 * Met à jour la classe active en fonction de location.pathname
 */
function highlightActiveNav(url) {
  const current = normalizePath(new URL(url, window.location.origin).pathname);
  document.querySelectorAll('.nav-tab').forEach(link => {
    const href = link.getAttribute('href');
    const linkPath = normalizePath(new URL(href, window.location.origin).pathname);
    // on test current === linkPath ou current commence par linkPath + '/'
    if (current === linkPath || current.startsWith(linkPath + '/')) {
      link.classList.add('active');
    } else {
      link.classList.remove('active');
    }
  });
}

/**
 * Exécute toutes les fonctions window.initXXX()
 */
function runAllInits() {
  Object.keys(window).forEach(fn => {
    if (fn.startsWith('init') && typeof window[fn] === 'function') {
      try { window[fn](); }
      catch (e) { console.error(`Erreur dans ${fn}():`, e); }
    }
  });
}

// Ajouter avant loadContent()
function cleanupBeforeLoad() {
    // Détruire les modules qui ont une fonction destroy
    ['destroyPrendreRdv', 'cleanupDispoManagement'].forEach(fn => {
        if (typeof window[fn] === 'function') {
            try { window[fn](); } catch (e) { console.warn(`${fn} failed:`, e); }
        }
    });
    
    // Dispatch event pour signaler le déchargement
    document.dispatchEvent(new CustomEvent('fragment:unloaded'));
}



/**
 * Charge un fragment via AJAX et l’injecte dans #ajax-content.
 * Puis gère pushState, active nav et init.
 */
function loadContent(url, push = true) {
  const container = document.getElementById('ajax-content');
  if (!container) return;

  cleanupBeforeLoad(); // ✅ AJOUT ICI

  container.innerHTML = '<p>Chargement…</p>';
  fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
    .then(r => r.ok ? r.text() : Promise.reject(`HTTP ${r.status}`))
    .then(html => {
      // si le serveur renvoie une page complète contenant #ajax-content,
      // on tente d'extraire le fragment pour éviter de mettre toute la page
      let fragment = html;
      if (html.includes('<html') || html.includes('<body') || html.includes('id="ajax-content"')) {
        const tmp = document.createElement('div');
        tmp.innerHTML = html;
        const extracted = tmp.querySelector('#ajax-content');
        if (extracted) fragment = extracted.innerHTML;
        else {
          const body = tmp.querySelector('body');
          fragment = body ? body.innerHTML : html;
        }
      }


      container.innerHTML = fragment;
      return injectAndExecuteScripts(container);
    })
    .then(() => {
      if (push) history.pushState({ url }, '', url);
      highlightActiveNav(url);
      runAllInits();
    })
    .catch(err => {
      console.error('Erreur AJAX loadContent:', err);
      container.innerHTML = '<p>Erreur lors du chargement.</p>';
    });
}

/**
 * Lie les onglets du menu à loadContent()
 */
function setupNavTabs() {
  document.querySelectorAll('.nav-tab').forEach(link => {
    // éviter duplication d'handlers si appelé plusieurs fois
    try { link.onclick = null; } catch (e) {}
    link.addEventListener('click', e => {
      e.preventDefault();
      loadContent(link.href);
    });
  });
}

// Back/forward
window.addEventListener('popstate', e => {
  if (e.state?.url) {
    loadContent(e.state.url, false);
  }
});

// Au premier chargement
window.addEventListener('DOMContentLoaded', () => {
  setupNavTabs();
  // Active l'onglet correspondant à l'URL actuelle
  highlightActiveNav(window.location.href);
  runAllInits();
});



// Expose pour debug / usage manuel
window.loadContent = loadContent;
window.highlightActiveNav = highlightActiveNav;
window.runAllInits = runAllInits;
