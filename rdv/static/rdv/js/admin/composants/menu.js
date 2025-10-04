// static/rdv/js/admin/menu.js
// Gestion responsive et idempotente du menu

(function () {
  if (window.__rdv_menu_init) return;
  window.__rdv_menu_init = true;

  // Utilitaire safe pour récupérer un élément
  const $ = sel => document.querySelector(sel);

  // Toggle sidebar (exposé globalement)
  function toggleSidebar() {
    const sidebar = $('#sidebar') || $('.sidebar');
    const overlay = $('.sidebar-overlay');
    const body = document.body;
    
    if (!sidebar) return;
    
    const isOpen = sidebar.classList.toggle('open');
    
    // Gestion de l'overlay
    if (overlay) {
      overlay.classList.toggle('active', isOpen);
    }
    
    // Empêcher le scroll du body sur mobile quand sidebar ouverte
    if (window.innerWidth <= 768) {
      body.classList.toggle('sidebar-open', isOpen);
    }
  }
  
  // Fonction pour fermer la sidebar
  function closeSidebar() {
    const sidebar = $('#sidebar') || $('.sidebar');
    const overlay = $('.sidebar-overlay');
    const body = document.body;
    
    if (!sidebar) return;
    
    sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
    body.classList.remove('sidebar-open');
  }
  
  // Exposer les fonctions globalement
  window.toggleSidebar = toggleSidebar;
  window.closeSidebar = closeSidebar;

  // Resize handler: fermer la sidebar automatiquement sur grands écrans
  if (!window.__rdv_menu_resize_bound) {
    let resizeTimer;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (window.innerWidth > 768) {
          closeSidebar();
        }
      }, 150);
    });
    window.__rdv_menu_resize_bound = true;
  }

  // Delegated click handler (nav tabs, logout, sidebar toggles)
  if (!window.__rdv_menu_click_bound) {
    document.addEventListener('click', function (ev) {
      
      // NAV TABS - fermer la sidebar sur mobile après navigation
      const nav = ev.target.closest && ev.target.closest('.nav-tab');
      if (nav) {
        ev.preventDefault();
        
        // Fermer la sidebar sur mobile
        if (window.innerWidth <= 768) {
          closeSidebar();
        }
        
        // Navigation AJAX ou normale
        if (typeof window.loadContent === 'function') {
          window.loadContent(nav.href || nav.getAttribute('href'));
        } else {
          window.location.href = nav.href || nav.getAttribute('href');
        }
        return;
      }

      // LOGOUT
      const logoutSel = ev.target.closest && ev.target.closest('#logout-link, .logout-btn, a.logout, [data-logout]');
      if (logoutSel) {
        ev.preventDefault();
        if (confirm("Êtes-vous sûr de vouloir vous déconnecter ?")) {
          const href = logoutSel.getAttribute('href') || logoutSel.dataset.href;
          if (href) window.location.href = href;
        }
        return;
      }

      // SIDEBAR TOGGLE (bouton hamburger ou autres toggles)
      const toggle = ev.target.closest && ev.target.closest('[data-toggle="sidebar"], .sidebar-toggle, .sidebar-toggle-btn, #sidebar-toggle');
      if (toggle) {
        ev.preventDefault();
        toggleSidebar();
        return;
      }
      
      // SIDEBAR CLOSE (bouton de fermeture spécifique)
      const closeBtn = ev.target.closest && ev.target.closest('.sidebar-close-btn');
      if (closeBtn) {
        ev.preventDefault();
        closeSidebar();
        return;
      }
      
      // OVERLAY CLICK - fermer la sidebar
      if (ev.target.classList.contains('sidebar-overlay')) {
        ev.preventDefault();
        closeSidebar();
        return;
      }
    }, false);

    window.__rdv_menu_click_bound = true;
  }

  // Gestion du clavier (Escape pour fermer la sidebar)
  if (!window.__rdv_menu_keyboard_bound) {
    document.addEventListener('keydown', function(ev) {
      if (ev.key === 'Escape' || ev.keyCode === 27) {
        const sidebar = $('#sidebar') || $('.sidebar');
        if (sidebar && sidebar.classList.contains('open')) {
          ev.preventDefault();
          closeSidebar();
        }
      }
    });
    window.__rdv_menu_keyboard_bound = true;
  }

  // Cleanup des handlers inline pour éviter les doublons
  try {
    const logoutEl = $('#logout-link') || $('.logout-btn') || $('a.logout') || $('[data-logout]');
    if (logoutEl) {
      if (logoutEl.hasAttribute('onclick')) {
        logoutEl.removeAttribute('onclick');
      }
      try { logoutEl.onclick = null; } catch (e) {}
    }
  } catch (e) {
    // ignore
  }

  // Fermer la sidebar si on clique à l'extérieur (touch devices)
  if ('ontouchstart' in window && !window.__rdv_menu_touch_bound) {
    document.addEventListener('touchstart', function(ev) {
      const sidebar = $('#sidebar') || $('.sidebar');
      const toggleBtn = $('.sidebar-toggle-btn');
      
      if (sidebar && sidebar.classList.contains('open')) {
        // Si le clic n'est ni dans la sidebar ni sur le bouton toggle
        if (!sidebar.contains(ev.target) && !toggleBtn?.contains(ev.target)) {
          closeSidebar();
        }
      }
    }, { passive: true });
    window.__rdv_menu_touch_bound = true;
  }

  // Support du swipe pour fermer la sidebar sur mobile
  if (!window.__rdv_menu_swipe_bound) {
    let touchStartX = 0;
    let touchEndX = 0;
    
    document.addEventListener('touchstart', function(ev) {
      const sidebar = $('#sidebar') || $('.sidebar');
      if (sidebar && sidebar.classList.contains('open') && sidebar.contains(ev.target)) {
        touchStartX = ev.changedTouches[0].screenX;
      }
    }, { passive: true });
    
    document.addEventListener('touchend', function(ev) {
      const sidebar = $('#sidebar') || $('.sidebar');
      if (sidebar && sidebar.classList.contains('open')) {
        touchEndX = ev.changedTouches[0].screenX;
        handleSwipe();
      }
    }, { passive: true });
    
    function handleSwipe() {
      const swipeDistance = touchEndX - touchStartX;
      // Swipe vers la gauche pour fermer (distance > 50px)
      if (swipeDistance < -50) {
        closeSidebar();
      }
    }
    
    window.__rdv_menu_swipe_bound = true;
  }

  // Export API pour debugging
  window.__rdv_menu = {
    toggleSidebar,
    closeSidebar,
    isInit: () => !!window.__rdv_menu_init,
    isOpen: () => {
      const sidebar = $('#sidebar') || $('.sidebar');
      return sidebar ? sidebar.classList.contains('open') : false;
    }
  };

  // Log de confirmation (retirer en production)
  console.log('📱 Menu responsive initialisé');

})();