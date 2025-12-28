// static/rdv/js/admin/menu.js
// Menu responsive – contrôle fiable de l'overlay (display + active)
(function () {
  if (window.__rdv_menu_final) return;
  window.__rdv_menu_final = true;

  const $ = sel => document.querySelector(sel);
  const isMobile = () => window.innerWidth <= 768;

  function elSidebar() { return $('#sidebar') || document.querySelector('.sidebar'); }
  function elToggle() { return $('#sidebar-toggle-btn') || document.querySelector('.sidebar-toggle-btn'); }
  function elOverlay() { return $('#sidebar-overlay') || document.querySelector('.sidebar-overlay'); }

  function ensureOverlay() {
    let ov = elOverlay();
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'sidebar-overlay';
      ov.className = 'sidebar-overlay';
      ov.setAttribute('aria-hidden', 'true');
      // minimal safe inline defaults so it doesn't block before CSS loads
      Object.assign(ov.style, {
        display: 'none',
        pointerEvents: 'none',
        opacity: '0',
        visibility: 'hidden',
        position: 'fixed',
        inset: '0',
        background: 'rgba(0,0,0,0.45)',
        zIndex: '1090',
      });
      document.body.appendChild(ov);
    }
    return ov;
  }

  function openSidebar() {
    const sidebar = elSidebar();
    const overlay = ensureOverlay();
    const toggle = elToggle();
    if (!sidebar) return;

    // Show overlay
    overlay.style.display = 'block';     // ensure it's in layout (important)
    // force reflow so transition works reliably
    overlay.getBoundingClientRect();
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    overlay.style.pointerEvents = 'auto';

    // Show sidebar
    sidebar.classList.add('open');
    sidebar.setAttribute('aria-hidden', 'false');
    document.body.classList.add('sidebar-open');

    if (toggle) toggle.setAttribute('aria-expanded', 'true');

    // defensive cleanup
    try {
      const ajax = document.getElementById('ajax-content');
      if (ajax) { ajax.style.filter = 'none'; ajax.style.backdropFilter = 'none'; }
      document.documentElement.style.filter = 'none';
      document.documentElement.style.backdropFilter = 'none';
    } catch (e) {}
  }

  function closeSidebar() {
    const sidebar = elSidebar();
    const overlay = elOverlay();
    const toggle = elToggle();
    if (!sidebar) return;

    // Hide sidebar
    sidebar.classList.remove('open');
    sidebar.setAttribute('aria-hidden', 'true');

    // Hide overlay visually and then remove from flow after transition
    if (overlay) {
      overlay.classList.remove('active');
      overlay.setAttribute('aria-hidden', 'true');
      overlay.style.pointerEvents = 'none';
      // after transition, ensure display none so it cannot intercept clicks
      setTimeout(() => {
        try { overlay.style.display = 'none'; } catch (e) {}
      }, 300);
    }

    document.body.classList.remove('sidebar-open');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');

    // defensive cleanup
    try {
      const ajax = document.getElementById('ajax-content');
      if (ajax) { ajax.style.filter = 'none'; ajax.style.backdropFilter = 'none'; }
      document.documentElement.style.filter = 'none';
      document.documentElement.style.backdropFilter = 'none';
    } catch (e) {}
  }

  function toggleSidebar() {
    const sidebar = elSidebar();
    if (!sidebar) return;
    if (!isMobile()) {
      // ensure persistent visible sidebar on desktop
      sidebar.classList.add('open');
      sidebar.setAttribute('aria-hidden', 'false');
      const ov = elOverlay();
      if (ov) { ov.classList.remove('active'); ov.style.display = 'none'; ov.style.pointerEvents = 'none'; }
      document.body.classList.remove('sidebar-open');
      elToggle()?.setAttribute('aria-expanded', 'false');
      return;
    }
    if (sidebar.classList.contains('open')) closeSidebar();
    else openSidebar();
  }

  // Delegated click handling (one listener)
  if (!window.__rdv_menu_click_bound) {
    document.addEventListener('click', function (ev) {
      // logout button confirmation
      const logoutBtn = ev.target.closest && ev.target.closest('#logout-link, .logout');
      if (logoutBtn) {
        ev.preventDefault();
        if (confirm('Êtes-vous sûr de vouloir vous déconnecter ?')) {
          const href = logoutBtn.href || logoutBtn.getAttribute('href');
          if (href) window.location.href = href;
        }
        return;
      }

      // nav-tabs (AJAX)
      const nav = ev.target.closest && ev.target.closest('.nav-tab');
      if (nav) {
        ev.preventDefault();
        if (isMobile()) closeSidebar();
        const href = nav.href || nav.getAttribute('href');
        if (href && typeof window.loadContent === 'function') window.loadContent(href);
        else if (href) window.location.href = href;
        return;
      }

      // toggle button
      const toggle = ev.target.closest && ev.target.closest('#sidebar-toggle-btn, .sidebar-toggle-btn, [data-toggle="sidebar"]');
      if (toggle) {
        ev.preventDefault();
        // make sure overlay exists and is display:block before toggling
        const ov = ensureOverlay();
        ov.style.display = 'block';
        toggleSidebar();
        return;
      }

      // close button inside sidebar
      const closeBtn = ev.target.closest && ev.target.closest('.sidebar-close-btn');
      if (closeBtn) { ev.preventDefault(); closeSidebar(); return; }

      // overlay click -> close
      if (ev.target && (ev.target.id === 'sidebar-overlay' || ev.target.classList?.contains('sidebar-overlay'))) {
        ev.preventDefault();
        closeSidebar();
        return;
      }
    }, false);
    window.__rdv_menu_click_bound = true;
  }

  // Escape key to close (mobile only)
  if (!window.__rdv_menu_keyboard_bound) {
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' || ev.keyCode === 27) {
        const s = elSidebar();
        if (s && s.classList.contains('open') && isMobile()) {
          ev.preventDefault();
          closeSidebar();
        }
      }
    }, false);
    window.__rdv_menu_keyboard_bound = true;
  }

  // Resize: if going to desktop, ensure overlay hidden and sidebar visible
  if (!window.__rdv_menu_resize_bound) {
    let rt;
    window.addEventListener('resize', function () {
      clearTimeout(rt);
      rt = setTimeout(() => {
        if (!isMobile()) {
          const s = elSidebar();
          if (s) { s.classList.add('open'); s.setAttribute('aria-hidden', 'false'); }
          const ov = elOverlay();
          if (ov) { ov.classList.remove('active'); ov.style.display = 'none'; ov.style.pointerEvents = 'none'; }
          document.body.classList.remove('sidebar-open');
          elToggle()?.setAttribute('aria-expanded', 'false');
        }
      }, 120);
    }, false);
    window.__rdv_menu_resize_bound = true;
  }

  // initial state on load
  function initState() {
    ensureOverlay(); // create if missing
    const s = elSidebar();
    if (!s) return;
    if (!isMobile()) {
      s.classList.add('open');
      s.setAttribute('aria-hidden', 'false');
      const ov = elOverlay();
      if (ov) { ov.classList.remove('active'); ov.style.display = 'none'; ov.style.pointerEvents = 'none'; }
      document.body.classList.remove('sidebar-open');
    } else {
      s.classList.remove('open');
      s.setAttribute('aria-hidden', 'true');
      const ov = elOverlay();
      if (ov) { ov.classList.remove('active'); ov.style.display = 'none'; ov.style.pointerEvents = 'none'; }
      document.body.classList.remove('sidebar-open');
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', initState);
  else initState();

  // Public API
  window.toggleSidebar = toggleSidebar;
  window.openSidebar = openSidebar;
  window.closeSidebar = closeSidebar;

  console.log('menu.js: overlay control ready');
})();