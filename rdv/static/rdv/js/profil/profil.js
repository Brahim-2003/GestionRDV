// static/rdv/js/profil.js
(function () {
  "use strict";

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
      document.cookie.split(";").forEach((cookie) => {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          cookieValue = decodeURIComponent(cookie.slice(name.length + 1));
        }
      });
    }
    return cookieValue;
  }

  function bindProfileForm(modalEl, containerEl, url) {
    const form = containerEl.querySelector("form");
    if (!form) return;

    if (form.dataset.bound === "1") return;
    form.dataset.bound = "1";

    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      e.stopPropagation();

      const formData = new FormData(form);

      const submitBtn = form.querySelector("button[type='submit']");
      const origText = submitBtn ? submitBtn.textContent : null;
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = "Enregistrement…";
      }

      try {
        const res = await fetch(url, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "X-Requested-With": "XMLHttpRequest",
          },
          body: formData,
        });

        const text = await res.text();
        let data = null;
        try {
          data = JSON.parse(text);
        } catch (_) {}

        if (!res.ok || (data && data.success === false)) {
          // réponse HTML avec erreurs → injecter
          containerEl.innerHTML = text;
          bindProfileForm(modalEl, containerEl, url);
          return;
        }

        // succès → fermer modal
        modalEl.classList.add("hidden");
        modalEl.setAttribute("aria-hidden", "true");
        containerEl.innerHTML = "<p>Chargement du formulaire…</p>";

        if (typeof window.showToast === "function") {
          window.showToast("Profil mis à jour");
        } else {
          alert("Profil mis à jour !");
        }

        window.location.reload();
      } catch (err) {
        console.error("Erreur submit profil:", err);
        alert("Impossible d'enregistrer. Réessaie.");
      } finally {
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = origText || "Enregistrer";
        }
      }
    });
  }

  // -----------------------
  // Délégation globale
  // -----------------------
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".edit-btn");
    if (!btn) return;

    e.preventDefault();

    const url = btn.dataset.formUrl;
    const modalSelector = btn.dataset.target;
    const containerSelector = btn.dataset.container;

    if (!url || !modalSelector || !containerSelector) {
      console.error("⚠️ Bouton mal configuré:", btn);
      return;
    }

    try {
      UserModal.init({
        modalSelector: modalSelector,
        containerSelector: containerSelector,
      });

      const containerEl = await UserModal.loadFragment(url);
      const modalEl = document.querySelector(modalSelector);

      // bind close
      modalEl.querySelectorAll(".modal-close, .modal-cancel").forEach((el) => {
        if (el.dataset.bound === "1") return;
        el.dataset.bound = "1";
        el.addEventListener("click", () => UserModal.close());
      });

      // bind form
      bindProfileForm(modalEl, containerEl, url);

      UserModal.open();
    } catch (err) {
      console.error("Erreur de chargement du formulaire:", err);
      alert("Impossible de charger le formulaire. Vérifie l'URL ou la vue Django.");
    }
  });
})();
