// static/rdv/js/admin/base.js

/**
 * Normalise un chemin : supprime slash final, 
 * et garde au moins "/".
 */
function normalizePath(path) {
  if (!path) return '/';
  // Retire les query et hash
  path = path.split('?')[0].split('#')[0];
  // Supprime slash final sauf s'il est seul
  if (path.length > 1 && path.endsWith('/')) {
    path = path.slice(0, -1);
  }
  return path || '/';
}

/**
 * Met à jour la classe "active" du menu en fonction de l'URL actuelle.
 * On cherche l'onglet dont le href est le préfixe le plus long de location.pathname.
 */
function highlightActiveNav(currentUrl) {
  const currentPath = normalizePath(new URL(currentUrl, window.location.origin).pathname);

  let bestMatch = null;
  let bestLength = -1;

  document.querySelectorAll('.nav-tab').forEach(link => {
    const linkPath = normalizePath(new URL(link.href, window.location.origin).pathname);

    // Si currentPath commence par linkPath, c'est un candidat
    if (currentPath === linkPath || currentPath.startsWith(linkPath + '/')) {
      if (linkPath.length > bestLength) {
        bestLength = linkPath.length;
        bestMatch = link;
      }
    }
  });

  // Si aucun match (cas rare), on peut fallback sur root "/"
  if (!bestMatch) {
    bestMatch = document.querySelector('.nav-tab[href="/rdv"], .nav-tab[href="/rdv/"]');
  }

  // Applique la classe active uniquement sur le meilleur match
  document.querySelectorAll('.nav-tab').forEach(link => link.classList.remove('active'));
  if (bestMatch) bestMatch.classList.add('active');
}

/**
 * Injecte et exécute tous les <script> inline, et recharge les externes en série.
 */
function injectAndExecuteScripts(container) {
  const scripts = Array.from(container.querySelectorAll('script'));
  const loads = [];

  scripts.forEach(old => {
    const s = document.createElement('script');
    if (old.src) {
      // Externe
      loads.push(new Promise((res, rej) => {
        s.src = old.src;
        s.onload = res;
        s.onerror = rej;
      }));
      s.async = false;
    } else {
      // Inline
      s.textContent = old.textContent;
    }
    document.body.appendChild(s);
  });

  return Promise.all(loads);
}

/**
 * Charge un fragment via AJAX dans #ajax-content,
 * met à jour l'historique et l'onglet actif puis init.
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
    .then(html => injectAndExecuteScripts(contentDiv).then(() => {
      contentDiv.innerHTML = html;
      if (pushState) history.pushState({ url }, '', url);
      highlightActiveNav(url);
      runAllInits();
    }))
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
 * Lie les onglets du menu pour passer par loadContent()
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
  if (e.state?.url) {
    loadContent(e.state.url, false);
    highlightActiveNav(e.state.url);
  }
});

// Initialisation au premier chargement
window.addEventListener('DOMContentLoaded', () => {
  setupNavTabs();
  highlightActiveNav(window.location.href);
  runAllInits();
});

// Pour debug
window.loadContent = loadContent;
window.runAllInits = runAllInits;
window.highlightActiveNav = highlightActiveNav;
