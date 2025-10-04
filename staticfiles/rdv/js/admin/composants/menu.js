// static/rdv/js/admin/menu.js
// Idempotent + delegation-based menu handlers

(function () {
  if (window.__rdv_menu_init) return;
  window.__rdv_menu_init = true;

  // utilitaire safe pour récupérer un élément (supporte query selector string)
  const $ = sel => document.querySelector(sel);

  // Toggle sidebar (exposé globalement)
  function toggleSidebar() {
    const sidebar = $('#sidebar') || document.querySelector('.sidebar');
    const overlay = document.querySelector('.sidebar-overlay');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('active');
  }
  window.toggleSidebar = toggleSidebar;

  // Resize handler: collapse sidebar on wide screens
  if (!window.__rdv_menu_resize_bound) {
    window.addEventListener('resize', function () {
      if (window.innerWidth > 768) {
        const sidebar = $('#sidebar') || document.querySelector('.sidebar');
        const overlay = document.querySelector('.sidebar-overlay');
        sidebar?.classList.remove('open');
        overlay?.classList.remove('active');
      }
    });
    window.__rdv_menu_resize_bound = true;
  }

  // Delegated click handler (nav tabs, logout, sidebar toggles)
  if (!window.__rdv_menu_click_bound) {
    document.addEventListener('click', function (ev) {
      // NAV TABS (delegation) - a single handler for all .nav-tab
      const nav = ev.target.closest && ev.target.closest('.nav-tab');
      if (nav) {
        ev.preventDefault();
        // Prefer loadContent if defined (AJAX navigation)
        if (typeof window.loadContent === 'function') {
          window.loadContent(nav.href || nav.getAttribute('href'));
        } else {
          // fallback normal navigation
          window.location.href = nav.href || nav.getAttribute('href');
        }
        return;
      }

      // LOGOUT - match by id or common classes/attributes
      const logoutSel = ev.target.closest && ev.target.closest('#logout-link, .logout-btn, a.logout, [data-logout]');
      if (logoutSel) {
        ev.preventDefault();
        // Show a single confirm; no duplicate possible because we only have 1 delegated listener
        if (confirm("Êtes-vous sûr de vouloir vous déconnecter ?")) {
          const href = logoutSel.getAttribute('href') || logoutSel.dataset.href;
          if (href) window.location.href = href;
        }
        return;
      }

      // SIDEBAR TOGGLE (any element with data-toggle="sidebar" or .sidebar-toggle)
      const toggle = ev.target.closest && ev.target.closest('[data-toggle="sidebar"], .sidebar-toggle, #sidebar-toggle');
      if (toggle) {
        ev.preventDefault();
        toggleSidebar();
        return;
      }
    }, false);

    window.__rdv_menu_click_bound = true;
  }

  // If there are static per-link handlers attached elsewhere and they cause duplicates,
  // replacing them by delegation solves the double-confirm. But we still remove inline
  // "onclick" attributes on logout link to be safe (non-destructive).
  try {
    const logoutEl = $('#logout-link') || document.querySelector('.logout-btn') || document.querySelector('a.logout') || document.querySelector('[data-logout]');
    if (logoutEl) {
      // clear inline onclick if present (to avoid duplicate inline handlers firing)
      if (logoutEl.hasAttribute('onclick')) {
        logoutEl.removeAttribute('onclick');
      }
      // clear old DOM0 handler if any
      try { logoutEl.onclick = null; } catch (e) {}
    }
  } catch (e) {
    // ignore
  }

  // Export a small API for debugging
  window.__rdv_menu = {
    toggleSidebar,
    isInit: () => !!window.__rdv_menu_init
  };

})();
