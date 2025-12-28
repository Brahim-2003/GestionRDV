Gestion des Rendez-vous Médicaux

Projet académique de fin d’études – Application web développée avec Django.

Ce projet consiste en la conception et l’implémentation d’une application web de gestion des rendez-vous médicaux. Il vise à répondre aux besoins d’un système réel : prise de rendez-vous en ligne, gestion des disponibilités médicales et supervision administrative, dans un contexte impliquant des données sensibles.

Le projet a été réalisé dans un cadre académique et constitue un socle fonctionnel, non destiné à la production à ce stade.

Objectifs du projet :

    - Concevoir une architecture web modulaire et évolutive avec Django

    - Implémenter une logique métier claire pour la gestion des rendez-vous

    - Gérer des rôles utilisateurs distincts (patient, médecin, administrateur)

    - Manipuler une base de données relationnelle avec intégrité et cohérence

    - Appliquer les bonnes pratiques de développement web (séparation des couches, sécurité de base, lisibilité du code)

Fonctionnalités implémentées : 

    - Authentification et gestion des rôles utilisateurs

    - Prise de rendez-vous par les patients selon les disponibilités

    - Gestion des créneaux et des disponibilités par les médecins

    - Tableau de bord par rôle avec statistiques simples

    - Interface web responsive développée sans framework CSS externe

Fonctionnalités envisagées : 

    - Système de notifications (email / SMS)

    - Intégration d’un chatbot de prise de rendez-vous (Rasa)

    - Ajout de tests unitaires et fonctionnels

    - Déploiement et configuration serveur (Docker, CI/CD)

Technologies utilisées : 

    - Python 3

    - Django

    - PostgreSQL

    - HTML / CSS / JavaScript (sans framework CSS externe)

    - Git pour le contrôle de version

Structure du projet
    GestionRDV/
    ├── users/        # Gestion des utilisateurs et des rôles
    ├── rdv/          # Logique métier des rendez-vous
    ├── templates/    # Templates HTML
    ├── static/       # Fichiers CSS, JavaScript, images
    ├── manage.py
    ├── requirements.txt

Limites et axes d’amélioration : 

    - Ce projet a été réalisé dans un cadre académique avec des contraintes de temps.
    Les axes d’amélioration identifiés sont :

    - ajout de tests automatisés

    - renforcement de la sécurité (permissions fines, protection avancée des données)

    - optimisation des performances et de la base de données

    - déploiement dans un environnement réel

Ces perspectives motivent mon souhait d’approfondir le développement logiciel et l’intelligence artificielle dans un cadre universitaire plus exigeant.

