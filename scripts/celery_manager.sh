# Script de gestion des tâches Celery

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  Gestionnaire Celery - GestionRDV${NC}"
echo -e "${GREEN}================================${NC}\n"

# Fonction pour afficher l'aide
show_help() {
    echo "Usage: ./scripts/celery_manager.sh [COMMANDE]"
    echo ""
    echo "Commandes disponibles:"
    echo "  setup       - Configuration initiale complète"
    echo "  start       - Démarre tous les services"
    echo "  stop        - Arrête tous les services"
    echo "  restart     - Redémarre worker et beat"
    echo "  status      - Affiche le statut des services"
    echo "  logs        - Affiche les logs en temps réel"
    echo "  test        - Lance les tests des tâches"
    echo "  init-tasks  - Initialise les tâches périodiques"
    echo "  shell       - Ouvre un shell Celery"
    echo "  purge       - Vide la queue Redis"
    echo "  monitor     - Statistiques en temps réel"
    echo "  help        - Affiche cette aide"
    echo ""
}

# Configuration initiale
setup() {
    echo -e "${YELLOW}▶ Configuration initiale...${NC}"
    
    # Créer le dossier logs
    mkdir -p logs
    touch logs/django.log logs/celery.log
    
    # Migrations
    echo -e "${YELLOW}▶ Migrations Django...${NC}"
    docker-compose exec web python manage.py makemigrations
    docker-compose exec web python manage.py migrate
    
    # Initialiser les tâches périodiques
    echo -e "${YELLOW}▶ Initialisation des tâches périodiques...${NC}"
    docker-compose exec web python manage.py init_periodic_tasks
    
    # Créer un superuser si nécessaire
    echo -e "${YELLOW}▶ Création du superuser (si nécessaire)...${NC}"
    docker-compose exec web python manage.py createsuperuser --noinput || true
    
    echo -e "${GREEN}✓ Configuration terminée!${NC}\n"
}

# Démarrer les services
start() {
    echo -e "${YELLOW}▶ Démarrage des services...${NC}"
    docker-compose up -d
    sleep 3
    docker-compose ps
    echo -e "${GREEN}✓ Services démarrés!${NC}\n"
}

# Arrêter les services
stop() {
    echo -e "${YELLOW}▶ Arrêt des services...${NC}"
    docker-compose down
    echo -e "${GREEN}✓ Services arrêtés!${NC}\n"
}

# Redémarrer worker et beat
restart() {
    echo -e "${YELLOW}▶ Redémarrage worker et beat...${NC}"
    docker-compose restart worker beat
    echo -e "${GREEN}✓ Redémarrage terminé!${NC}\n"
}

# Statut des services
status() {
    echo -e "${YELLOW}▶ Statut des services:${NC}\n"
    docker-compose ps
    
    echo -e "\n${YELLOW}▶ Vérification Redis:${NC}"
    docker-compose exec redis redis-cli ping || echo -e "${RED}Redis ne répond pas!${NC}"
    
    echo -e "\n${YELLOW}▶ Tâches Celery actives:${NC}"
    docker-compose exec worker celery -A GestionRDV inspect active || true
    
    echo ""
}

# Logs en temps réel
show_logs() {
    echo -e "${YELLOW}▶ Logs en temps réel (Ctrl+C pour quitter):${NC}\n"
    docker-compose logs -f worker beat
}

# Tests
run_tests() {
    echo -e "${YELLOW}▶ Lancement des tests...${NC}\n"
    
    # Créer des RDV de test
    echo -e "${YELLOW}1. Création de RDV de test...${NC}"
    docker-compose exec web python manage.py create_test_rdv --expired
    docker-compose exec web python manage.py create_test_rdv --starting
    docker-compose exec web python manage.py create_test_rdv --reminder
    
    # Tester les tâches
    echo -e "\n${YELLOW}2. Test des tâches Celery...${NC}"
    docker-compose exec web python manage.py test_celery --task=all
    
    echo -e "\n${GREEN}✓ Tests terminés!${NC}\n"
}

# Initialiser les tâches périodiques
init_tasks() {
    echo -e "${YELLOW}▶ Initialisation des tâches périodiques...${NC}"
    docker-compose exec web python manage.py init_periodic_tasks
    echo -e "${GREEN}✓ Tâches initialisées!${NC}"
    echo -e "${YELLOW}Redémarrez beat: docker-compose restart beat${NC}\n"
}

# Shell Celery
celery_shell() {
    echo -e "${YELLOW}▶ Ouverture du shell Celery...${NC}\n"
    docker-compose exec worker bash
}

# Purger la queue
purge_queue() {
    echo -e "${RED}⚠ Cette action va supprimer toutes les tâches en attente!${NC}"
    read -p "Continuer? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}▶ Vidage de la queue Redis...${NC}"
        docker-compose exec redis redis-cli FLUSHALL
        echo -e "${GREEN}✓ Queue vidée!${NC}\n"
    else
        echo -e "${YELLOW}Annulé.${NC}\n"
    fi
}

# Monitoring
monitor() {
    echo -e "${YELLOW}▶ Statistiques Celery:${NC}\n"
    
    echo -e "${YELLOW}Tâches enregistrées:${NC}"
    docker-compose exec worker celery -A GestionRDV inspect registered
    
    echo -e "\n${YELLOW}Tâches actives:${NC}"
    docker-compose exec worker celery -A GestionRDV inspect active
    
    echo -e "\n${YELLOW}Statistiques:${NC}"
    docker-compose exec worker celery -A GestionRDV inspect stats
    
    echo ""
}

# Menu interactif
interactive_menu() {
    while true; do
        echo -e "${GREEN}================================${NC}"
        echo -e "${GREEN}  Menu Interactif${NC}"
        echo -e "${GREEN}================================${NC}"
        echo "1) Démarrer les services"
        echo "2) Arrêter les services"
        echo "3) Redémarrer worker/beat"
        echo "4) Voir le statut"
        echo "5) Voir les logs"
        echo "6) Lancer les tests"
        echo "7) Initialiser les tâches"
        echo "8) Monitoring"
        echo "9) Quitter"
        echo ""
        read -p "Choix: " choice
        
        case $choice in
            1) start ;;
            2) stop ;;
            3) restart ;;
            4) status ;;
            5) show_logs ;;
            6) run_tests ;;
            7) init_tasks ;;
            8) monitor ;;
            9) echo -e "${GREEN}Au revoir!${NC}"; exit 0 ;;
            *) echo -e "${RED}Choix invalide${NC}\n" ;;
        esac
        
        read -p "Appuyez sur Entrée pour continuer..."
        clear
    done
}

# Parser les arguments
case "${1:-}" in
    setup)
        setup
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        show_logs
        ;;
    test)
        run_tests
        ;;
    init-tasks)
        init_tasks
        ;;
    shell)
        celery_shell
        ;;
    purge)
        purge_queue
        ;;
    monitor)
        monitor
        ;;
    help|--help|-h)
        show_help
        ;;
    "")
        interactive_menu
        ;;
    *)
        echo -e "${RED}Commande inconnue: $1${NC}\n"
        show_help
        exit 1
        ;;
esac