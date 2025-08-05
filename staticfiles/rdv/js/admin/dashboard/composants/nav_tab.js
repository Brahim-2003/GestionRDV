// Gestion des liens actifs
        document.querySelectorAll('.nav-tab').forEach(link => {
            link.addEventListener('click', function(e) {
                e.preventDefault();
                
                // Retirer la classe active de tous les liens
                document.querySelectorAll('.nav-tab').forEach(l => l.classList.remove('active'));
                
                // Ajouter la classe active au lien cliqué
                this.classList.add('active');
                
                // Mettre à jour le contenu (optionnel)
                const content = document.querySelector('.main-content h1');
                const text = this.querySelector('span').textContent;
                content.textContent = `${text}`;
            });
        });

        // Fonction pour toggle sidebar sur mobile
        function toggleSidebar() {
            const sidebar = document.getElementById('sidebar');
            const overlay = document.querySelector('.sidebar-overlay');
            
            sidebar.classList.toggle('open');
            overlay.classList.toggle('active');
        }

        // Gestion responsive
        window.addEventListener('resize', function() {
            if (window.innerWidth > 768) {
                const sidebar = document.getElementById('sidebar');
                const overlay = document.querySelector('.sidebar-overlay');
                
                sidebar.classList.remove('open');
                overlay.classList.remove('active');
            }
        });