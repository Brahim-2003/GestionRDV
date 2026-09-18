# rdv/cache.py
"""Clés et durées de vie du cache Redis pour l'app rdv (voir
GestionRDV/settings.py::CACHES). Module séparé de views.py pour que
rdv/signals.py puisse invalider ces clés sans dépendre du module de vues.

Ne JAMAIS mettre en cache ici la disponibilité réelle des créneaux
(api_search_medecins, api_creneaux_medecin) : ces données doivent rester
à jour en temps réel, même si leur calcul est coûteux.
"""

# CACHE_KEY_SYMPTOMES : référentiel quasi-statique (catégories de
# symptômes + spécialités suggérées, RechercheSymptome). Pas d'invalidation
# par signal : RechercheSymptome n'est modifiable par aucune vue ni par
# l'admin Django actuellement (vérifié — seule la migration de données
# 0006_seed_recherche_symptome le peuple). Le TTL reste donc la seule
# garantie de fraîcheur ; il n'est volontairement pas allongé pour cette
# raison. Si une interface d'édition est ajoutée un jour, ajouter alors un
# signal post_save/post_delete sur RechercheSymptome comme pour Medecin
# ci-dessous, et seulement à ce moment-là allonger ce TTL.
CACHE_KEY_SYMPTOMES = 'rdv:symptomes_categories'
CACHE_TTL_SYMPTOMES = 60 * 60  # 1h

# CACHE_KEY_SPECIALITES_COUNT : agrégat DB (nb de médecins par spécialité,
# affiché sur "prendre RDV"). Medecin EST modifiable (admin Django
# MedecinAdmin, et edit_medecin_view pour le médecin lui-même) : invalidé
# immédiatement sur toute création/modification/suppression d'un médecin
# (voir rdv/signals.py). Le TTL n'est donc plus que le filet de sécurité
# pour les cas non couverts par le signal (ex. modification en dehors de
# l'ORM) -> allongé en conséquence.
CACHE_KEY_SPECIALITES_COUNT = 'rdv:medecins_par_specialite_count'
CACHE_TTL_SPECIALITES_COUNT = 60 * 60 * 6  # 6h

# CACHE_KEY_DASHBOARD_STATS : statistiques admin, coûteuses (une dizaine de
# requêtes d'agrégation) mais qui évoluent avec l'activité réelle (nouveaux
# RDV, inscriptions...) en continu, sans événement de sauvegarde unique à
# écouter -> TTL court délibérément conservé, ne pas allonger.
CACHE_KEY_DASHBOARD_STATS = 'rdv:dashboard_admin_stats'
CACHE_TTL_DASHBOARD_STATS = 30  # 30s
