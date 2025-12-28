document.addEventListener('DOMContentLoaded', function () {
    // Helpers
    const header = document.querySelector('.header');
    const headerHeight = () => header ? header.offsetHeight : 0;

    /* Smooth scrolling for internal anchors (account for fixed header) */
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const href = this.getAttribute('href');
            // only handle internal hash links with a non-empty target
            if (href && href.startsWith('#') && href.length > 1) {
                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    const targetY = target.getBoundingClientRect().top + window.pageYOffset - headerHeight() - 12;
                    window.scrollTo({
                        top: targetY,
                        behavior: 'smooth'
                    });
                }
            }
        });
    });

    /* Header scroll effect */
    window.addEventListener('scroll', () => {
        const hdr = document.querySelector('.header');
        if (!hdr) return;
        if (window.scrollY > 100) {
            hdr.style.background = 'rgba(255, 255, 255, 0.98)';
            hdr.style.boxShadow = '0 2px 30px rgba(0, 0, 0, 0.15)';
        } else {
            hdr.style.background = 'rgba(255, 255, 255, 0.95)';
            hdr.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
        }
    });

    /* Feature cards / stat cards animation on scroll */
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    document.querySelectorAll('.feature-card, .stat-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';
        card.style.transition = 'all 0.6s ease';
        observer.observe(card);
    });

    /* Mobile menu toggle (improved) */
    const mobileToggle = document.querySelector('.mobile-menu-toggle');
    const navLinks = document.querySelector('.nav-links');

    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', function () {
            const isOpen = navLinks.classList.toggle('show');
            this.setAttribute('aria-expanded', String(isOpen));
        });

        // Close mobile menu when clicking a nav link (helpful on small screens)
        navLinks.querySelectorAll('a').forEach(a => {
            a.addEventListener('click', () => {
                if (navLinks.classList.contains('show')) {
                    navLinks.classList.remove('show');
                    mobileToggle.setAttribute('aria-expanded', 'false');
                }
            });
        });
    }

    /* Button ripple effect (fixed selector & robust positioning) */
    // Correct selector: include dots for class selectors
    const buttons = document.querySelectorAll('.btn-primary, .btn-secondary, .btn-register, .btn-connect');

    buttons.forEach(button => {
        // ensure button is positioned as relative for the ripple
        const cs = window.getComputedStyle(button);
        if (cs.position === 'static') {
            button.style.position = 'relative';
        }
        button.style.overflow = 'hidden';

        button.addEventListener('click', function(e) {
            // ignore right-clicks and keyboard activation differences
            if (e.button === 2) return;

            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height) * 1.2;
            const x = (e.clientX || rect.left + rect.width / 2) - rect.left - size / 2;
            const y = (e.clientY || rect.top + rect.height / 2) - rect.top - size / 2;

            const ripple = document.createElement('span');
            ripple.className = 'ripple-effect';
            ripple.style.position = 'absolute';
            ripple.style.borderRadius = '50%';
            ripple.style.pointerEvents = 'none';
            ripple.style.width = `${size}px`;
            ripple.style.height = `${size}px`;
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            ripple.style.transform = 'scale(0)';
            ripple.style.opacity = '0.6';
            ripple.style.background = 'rgba(255,255,255,0.35)';
            ripple.style.transition = 'transform 600ms linear, opacity 600ms linear';

            this.appendChild(ripple);

            // force reflow then start animation
            requestAnimationFrame(() => {
                ripple.style.transform = 'scale(3.5)';
                ripple.style.opacity = '0';
            });

            setTimeout(() => {
                ripple.remove();
            }, 650);
        });
    });

    /* Add ripple keyframes fallback style (in case not present) */
    if (!document.getElementById('ripple-styles')) {
        const style = document.createElement('style');
        style.id = 'ripple-styles';
        style.textContent = `
            .ripple-effect { will-change: transform, opacity; }
        `;
        document.head.appendChild(style);
    }
});
