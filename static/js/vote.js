(function() {
    const pseudo = localStorage.getItem('pseudo') || '';

    // Pas de pseudo : on renvoie sur la home pour le saisir
    if (!pseudo) {
        window.location.replace('/');
        return;
    }

    const socket = io();
    const body = document.body;
    const container = document.getElementById('chansons');
    const pseudoActuel = document.getElementById('pseudo-actuel');

    const salleNom = window.INITIAL_STATE.salle;
    let chansons = window.INITIAL_STATE.chansons;
    let tourActuel = window.INITIAL_STATE.tour;
    let aVote = window.INITIAL_STATE.deja_vote;

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function render() {
        pseudoActuel.innerHTML = `tu votes en tant que <strong>${escapeHtml(pseudo)}</strong>`;

        if (aVote) {
            body.classList.add('has-voted');
            container.innerHTML = '';
            return;
        }
        body.classList.remove('has-voted');

        const pret = chansons.every(c => c.titre && c.pochette);
        if (!pret) {
            container.innerHTML = `
                <div class="attente">
                    <div class="spinner"></div>
                    <p>La salle n'est pas encore prête.<br>
                       L'organisateur doit connecter Spotify.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = chansons.map(c => `
            <div class="chanson-card">
                <img src="${c.pochette}" alt="${escapeHtml(c.titre)}">
                <div class="chanson-info">
                    <div class="titre">${escapeHtml(c.titre)}</div>
                    <div class="artiste">${escapeHtml(c.artiste)}</div>
                </div>
                <button class="voter" onclick="__voter(${c.id})" aria-label="Voter pour ${escapeHtml(c.titre)}">
                    <svg viewBox="0 0 24 24"><path d="M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4L9 16.2z"/></svg>
                </button>
            </div>
        `).join('');
    }

    window.__voter = function(chansonId) {
        if (aVote) return;
        aVote = true;
        if (navigator.vibrate) navigator.vibrate(15);
        const user_uuid = localStorage.getItem('user_uuid') || '';
        socket.emit('voter', { chanson_id: chansonId, pseudo, salle: salleNom, uuid: user_uuid });
        render();
    };

    socket.on('connect', () => {
        socket.emit('rejoindre_salle', { salle: salleNom });
    });

    socket.on('mise_a_jour_votes', (data) => {
        if (data.salle && data.salle !== salleNom) return;
        if (data.tour !== undefined && data.tour !== tourActuel) {
            tourActuel = data.tour;
            aVote = false;
        }
        chansons = data.chansons;
        render();
    });

    socket.on('erreur', (data) => {
        alert(data.message);
    });

    render();
})();
