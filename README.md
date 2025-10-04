# Gestion des Rendez-vous Médicaux

> Projet en cours de développement – Non destiné à la production pour l’instant.

Ce projet est une application web de gestion des rendez-vous médicaux développée avec **Django**. 
Il permet aux patients de prendre rendez-vous en ligne, aux médecins de gérer leurs disponibilités, et aux administrateurs de superviser l’ensemble du système.

---

## Fonctionnalités prévues

- Authentification et gestion des rôles (patient, médecin, admin)
- Prise de rendez-vous par les patients
- Gestion des disponibilités par les médecins
- Tableau de bord avec statistiques par rôle
- Notifications (à venir)
- Chatbot de prise de rendez-vous (intégration future avec Rasa)

---

## Technologies utilisées

- [Django](https://www.djangoproject.com/)
- Python 3.x
- PostgreSQL 
- HTML/CSS/JavaScript (sans framework CSS externe)

---

## Structure du projet

```bash
GestionRDV/
├── users/               # Gestion des utilisateurs (auth, rôles)
├── rdv/                 # Application de prise de rendez-vous
├── templates/           # Templates HTML
├── static/              # Fichiers CSS, JS, images
├── manage.py
├── requirements.txt     # Dépendances

