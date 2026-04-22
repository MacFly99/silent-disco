(function() {
    // --- Édition des salles ---
    const editor = document.getElementById('salles-editor');
    const btnAjouter = document.getElementById('btn-ajouter-salle');
    const btnSauver = document.getElementById('btn-sauver-salles');

    function creerCarte(nom = '', couleur = '#1DB954', clientId = '', playlistId = '') {
        const div = document.createElement('div');
        div.className = 'salle-edit';
        div.dataset.nom = nom;
        div.innerHTML = `
            <div class="salle-edit-header">
                <span class="pastille-couleur" style="background: ${couleur}"></span>
                <input class="champ-nom" type="text" value="${escapeHtml(nom)}" placeholder="ex: pop">
                <input class="champ-couleur" type="color" value="${couleur}">
                <button class="btn-supprimer" type="button" aria-label="Supprimer">✕</button>
            </div>
            <label>Client ID</label>
            <input class="champ-client-id" type="text" value="${escapeHtml(clientId)}">
            <label>Client Secret</label>
            <input class="champ-client-secret" type="password" value="" placeholder="">
            <label>Playlist ID</label>
            <input class="champ-playlist-id" type="text" value="${escapeHtml(playlistId)}">
        `;
        brancher(div);
        return div;
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function brancher(carte) {
        const pastille = carte.querySelector('.pastille-couleur');
        const couleurInput = carte.querySelector('.champ-couleur');
        couleurInput.addEventListener('input', () => {
            pastille.style.background = couleurInput.value;
        });
        carte.querySelector('.btn-supprimer').addEventListener('click', () => {
            if (confirm('Supprimer cette salle ?')) carte.remove();
        });
    }

    // Brancher les cartes rendues côté serveur
    editor.querySelectorAll('.salle-edit').forEach(brancher);

    btnAjouter.addEventListener('click', () => {
        const carte = creerCarte();
        editor.appendChild(carte);
        carte.querySelector('.champ-nom').focus();
    });

    btnSauver.addEventListener('click', async () => {
        const payload = [];
        for (const carte of editor.querySelectorAll('.salle-edit')) {
            payload.push({
                nom: carte.querySelector('.champ-nom').value.trim().toLowerCase(),
                couleur: carte.querySelector('.champ-couleur').value,
                client_id: carte.querySelector('.champ-client-id').value.trim(),
                client_secret: carte.querySelector('.champ-client-secret').value.trim(),
                playlist_id: carte.querySelector('.champ-playlist-id').value.trim(),
            });
        }
        btnSauver.disabled = true;
        try {
            const res = await fetch('/admin/salles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'erreur inconnue');
            afficherFlash('Salles sauvegardées');
            setTimeout(() => window.location.reload(), 600);
        } catch (e) {
            alert('Erreur : ' + e.message);
            btnSauver.disabled = false;
        }
    });

    // --- Archivage (existant) ---
    const backdrop = document.getElementById('modal-backdrop');
    const modalType = document.getElementById('modal-type');
    const modalInput = document.getElementById('modal-input');
    const btnConfirmer = document.getElementById('btn-confirmer');
    const btnAnnuler = document.getElementById('btn-annuler');
    const flash = document.getElementById('flash');
    let typeEnCours = null;

    document.querySelectorAll('.btn-clear').forEach(btn => {
        btn.addEventListener('click', () => ouvrirModal(btn.dataset.type));
    });

    btnAnnuler.addEventListener('click', fermerModal);
    backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) fermerModal();
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
            fermerModal();
            setTimeout(() => window.location.reload(), 800);
        } catch (e) {
            alert('Erreur : ' + e.message);
            btnConfirmer.disabled = false;
        }
    });

    function ouvrirModal(type) {
        typeEnCours = type;
        modalType.textContent = type;
        modalInput.value = '';
        btnConfirmer.disabled = true;
        backdrop.classList.add('visible');
        setTimeout(() => modalInput.focus(), 50);
    }

    function fermerModal() {
        backdrop.classList.remove('visible');
        typeEnCours = null;
    }

    function afficherFlash(msg) {
        flash.textContent = msg;
        flash.classList.add('visible');
        setTimeout(() => flash.classList.remove('visible'), 2500);
    }
})();
