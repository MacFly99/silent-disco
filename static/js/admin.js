(function() {
    const flash = document.getElementById('flash');

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function afficherFlash(msg) {
        flash.textContent = msg;
        flash.classList.add('visible');
        setTimeout(() => flash.classList.remove('visible'), 2500);
    }

    // ========================================================================
    // Gestion des salles via modal
    // ========================================================================

    // État : liste JS miroir de config/salles.json, injectée par le template.
    // On la récupère à partir du DOM initial pour éviter un appel supplémentaire.
    let salles = [];
    document.querySelectorAll('#salles-liste .salle-row').forEach(row => {
        salles.push({
            nom: row.dataset.nom,
            couleur: row.querySelector('.pastille-couleur').style.background,
            playlist_id: '',       // sera rempli quand on clique "éditer" (via fetch)
            client_id: '',
            client_secret: '',
            client_secret_masque: '',
            _loaded: false,
        });
    });

    const modal = document.getElementById('salle-modal');
    const modalTitre = document.getElementById('salle-modal-titre');
    const champNom = document.getElementById('salle-modal-nom');
    const champCouleur = document.getElementById('salle-modal-couleur');
    const champClientId = document.getElementById('salle-modal-client-id');
    const champClientSecret = document.getElementById('salle-modal-client-secret');
    const champPlaylistId = document.getElementById('salle-modal-playlist-id');
    const secretHint = document.getElementById('salle-modal-secret-hint');
    const btnAjouter = document.getElementById('btn-ajouter-salle');
    const btnFermer = document.getElementById('salle-modal-fermer');
    const btnAnnuler = document.getElementById('salle-modal-annuler');
    const btnEnregistrer = document.getElementById('salle-modal-enregistrer');
    const btnSupprimer = document.getElementById('salle-modal-supprimer');

    let editionEnCours = null;  // nom de la salle en cours d'édition, ou null pour création

    function ouvrirModalEdition(salle) {
        editionEnCours = salle.nom;
        modalTitre.textContent = 'Éditer la salle';
        champNom.value = salle.nom;
        champNom.readOnly = true;
        champCouleur.value = salle.couleur || '#1DB954';
        champClientId.value = salle.client_id || '';
        champClientSecret.value = '';
        champClientSecret.placeholder = salle.client_secret_masque || '';
        secretHint.textContent = salle.client_secret_masque
            ? `(laisse vide pour garder l'actuel : ${salle.client_secret_masque})`
            : '';
        champPlaylistId.value = salle.playlist_id || '';
        btnSupprimer.style.display = 'inline-block';
        modal.classList.add('visible');
    }

    function ouvrirModalCreation() {
        editionEnCours = null;
        modalTitre.textContent = 'Nouvelle salle';
        champNom.value = '';
        champNom.readOnly = false;
        champCouleur.value = '#1DB954';
        champClientId.value = '';
        champClientSecret.value = '';
        champClientSecret.placeholder = '';
        secretHint.textContent = '';
        champPlaylistId.value = '';
        btnSupprimer.style.display = 'none';
        modal.classList.add('visible');
        setTimeout(() => champNom.focus(), 50);
    }

    function fermerModal() {
        modal.classList.remove('visible');
        editionEnCours = null;
    }

    async function chargerDetailsSalle(nom) {
        // Récupère la config complète (avec secret masqué) depuis le serveur
        const res = await fetch('/admin/salles');
        const data = await res.json();
        return data.find(s => s.nom === nom);
    }

    // --- Handlers ---

    btnAjouter.addEventListener('click', ouvrirModalCreation);
    btnFermer.addEventListener('click', fermerModal);
    btnAnnuler.addEventListener('click', fermerModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) fermerModal();
    });

    // Clic sur une salle dans la liste → ouvrir modal édition
    document.querySelectorAll('#salles-liste .salle-row').forEach(row => {
        row.addEventListener('click', async (e) => {
            e.stopPropagation();
            const nom = row.dataset.nom;
            try {
                const salle = await chargerDetailsSalle(nom);
                if (salle) ouvrirModalEdition(salle);
            } catch (err) {
                alert('Erreur de chargement : ' + err.message);
            }
        });
    });

    btnEnregistrer.addEventListener('click', async () => {
        const nom = champNom.value.trim().toLowerCase();
        if (!nom) { alert('Nom requis'); return; }

        // Construire le payload complet : on repart de la liste serveur
        const res = await fetch('/admin/salles');
        const liste = await res.json();

        const entry = {
            nom,
            couleur: champCouleur.value,
            client_id: champClientId.value.trim(),
            client_secret: champClientSecret.value.trim(),
            playlist_id: champPlaylistId.value.trim(),
        };

        if (!entry.client_id || !entry.playlist_id) {
            alert('Client ID et Playlist ID sont obligatoires');
            return;
        }

        const idx = liste.findIndex(s => s.nom === (editionEnCours || nom));
        if (idx >= 0) {
            // Édition : on conserve le secret masqué si vide (backend gère)
            liste[idx] = entry;
        } else {
            if (!entry.client_secret) {
                alert('Client Secret requis pour une nouvelle salle');
                return;
            }
            liste.push(entry);
        }

        btnEnregistrer.disabled = true;
        try {
            const resp = await fetch('/admin/salles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(liste),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'erreur inconnue');
            afficherFlash('Salle enregistrée');
            setTimeout(() => window.location.reload(), 600);
        } catch (e) {
            alert('Erreur : ' + e.message);
            btnEnregistrer.disabled = false;
        }
    });

    btnSupprimer.addEventListener('click', async () => {
        if (!editionEnCours) return;
        if (!confirm(`Supprimer la salle "${editionEnCours}" ?\nSon cache Spotify sera effacé.`)) return;

        const res = await fetch('/admin/salles');
        const liste = (await res.json()).filter(s => s.nom !== editionEnCours);

        btnSupprimer.disabled = true;
        try {
            const resp = await fetch('/admin/salles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(liste),
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'erreur inconnue');
            afficherFlash('Salle supprimée');
            setTimeout(() => window.location.reload(), 600);
        } catch (e) {
            alert('Erreur : ' + e.message);
            btnSupprimer.disabled = false;
        }
    });

    // ========================================================================
    // Archivage des logs (existant)
    // ========================================================================
    const backdrop = document.getElementById('modal-backdrop');
    const modalType = document.getElementById('modal-type');
    const modalInput = document.getElementById('modal-input');
    const btnConfirmer = document.getElementById('btn-confirmer');
    const btnAnnulerArchiv = document.getElementById('btn-annuler');
    let typeEnCours = null;

    document.querySelectorAll('.btn-clear').forEach(btn => {
        btn.addEventListener('click', () => ouvrirModalArchiv(btn.dataset.type));
    });

    btnAnnulerArchiv.addEventListener('click', fermerModalArchiv);
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) fermerModalArchiv();
    });

    modalInput.addEventListener('input', () => {
        btnConfirmer.disabled = modalInput.value.trim().toUpperCase() !== 'CONFIRMER';
    });

    btnConfirmer.addEventListener('click', async () => {
        if (!typeEnCours) return;
        btnConfirmer.disabled = true;
        try {
            const res = await fetch(`/admin/archiver/${typeEnCours}`, { method: 'POST' });
            const data = await res.json();
            const n = (data.archived || []).length;
            afficherFlash(n === 0
                ? `Aucun fichier à archiver pour ${typeEnCours}`
                : `${n} fichier(s) archivé(s) pour ${typeEnCours}`);
            fermerModalArchiv();
            setTimeout(() => window.location.reload(), 800);
        } catch (e) {
            alert('Erreur : ' + e.message);
            btnConfirmer.disabled = false;
        }
    });

    function ouvrirModalArchiv(type) {
        typeEnCours = type;
        modalType.textContent = type;
        modalInput.value = '';
        btnConfirmer.disabled = true;
        backdrop.classList.add('visible');
        setTimeout(() => modalInput.focus(), 50);
    }

    function fermerModalArchiv() {
        backdrop.classList.remove('visible');
        typeEnCours = null;
    }
})();
