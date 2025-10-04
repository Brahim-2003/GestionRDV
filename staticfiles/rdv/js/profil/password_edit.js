// static/rdv/js/modal/password_edit.js
(function () {
  "use strict";

  const q = (s) => document.querySelector(s);

  // Récupération du cookie CSRF
  function getCookie(name) {
    if (!document.cookie) return null;
    let value = null;
    document.cookie.split(";").forEach((c) => {
      c = c.trim();
      if (c.startsWith(name + "=")) {
        value = decodeURIComponent(c.slice(name.length + 1));
      }
    });
    return value;
  }

  async function loadPasswordForm(url) {
    const container = q("#edit-password-modal-form-container");
    if (!container) return;
    container.innerHTML = "<p>Chargement du formulaire…</p>";
    try {
      const res = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const html = await res.text();
      container.innerHTML = html;
      bindPasswordForm(container);
    } catch (err) {
      console.error("Erreur de chargement du form:", err);
      container.innerHTML =
        "<p style='color:red'>Impossible de charger le formulaire.</p>";
    }
  }

  function bindPasswordForm(container) {
    if (!container) return;
    const form = container.querySelector("form[data-ajax='1']");
    if (!form) return;

    if (form.dataset.bound === "1") return;
    form.dataset.bound = "1";

    form.addEventListener("submit", async (e) => {
      e.preventDefault();

      try {
        const data = new FormData(form);
        const res = await fetch(form.action, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "X-Requested-With": "XMLHttpRequest",
          },
          body: data,
          credentials: "same-origin",
        });

        // JSON → succès
        if (res.headers.get("content-type")?.includes("application/json")) {
          const json = await res.json();
          if (json.success) {
            closePasswordModal();
            alert("Mot de passe modifié avec succès !");
            return;
          }
        }

        // Sinon, renvoyer le fragment HTML (form avec erreurs)
        const html = await res.text();
        container.innerHTML = html;
        bindPasswordForm(container);
      } catch (err) {
        console.error("Erreur de soumission du form:", err);
        alert("Impossible de modifier le mot de passe.");
      }
    });
  }

  function openPasswordModal(url) {
    const modal = q("#edit-password-modal");
    if (!modal) return;
    modal.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
    loadPasswordForm(url);
  }

  function closePasswordModal() {
    const modal = q("#edit-password-modal");
    if (!modal) return;
    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
    const container = q("#edit-password-modal-form-container");
    if (container) container.innerHTML = "<p>Chargement du formulaire…</p>";
  }

  // Delegation globale → marche même si les boutons arrivent plus tard
  document.addEventListener("click", (e) => {
    // Ouvrir modal mot de passe
    const btn = e.target.closest("button[data-target='#edit-password-modal']");
    if (btn) {
      e.preventDefault();
      const url =
        btn.dataset.formUrl ||
        btn.getAttribute("data-form-url") ||
        btn.getAttribute("href");
      if (!url) {
        console.error("Pas d’URL de formulaire pour ce bouton");
        return;
      }
      openPasswordModal(url);
      return;
    }

    // Fermer modal
    if (
      e.target.closest("#edit-password-modal .modal-close") ||
      e.target.closest("#edit-password-modal .modal-cancel")
    ) {
      e.preventDefault();
      closePasswordModal();
    }
  });

  // Expose pour debug
  window.openPasswordModal = openPasswordModal;
  window.closePasswordModal = closePasswordModal;
})();
