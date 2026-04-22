(function() {
    const socket = io();

    const salleNom = window.INITIAL_STATE.salle;
    const salleCouleur = window.INITIAL_STATE.couleur;
    let chansons = window.INITIAL_STATE.chansons;
    let tourActuel = window.INITIAL_STATE.tour;

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    // --- Rendu des cards de vote ---
    function renderChansons() {
        const maxVotes = Math.max(...chansons.map(c => c.votes), 0);
        const container = document.getElementById('chansons');
        container.innerHTML = chansons.map(c => {
            const pct = maxVotes > 0 ? (c.votes / maxVotes) * 100 : 0;
            return `
                <div class="chanson-card">
                    <img src="${c.pochette}" alt="${escapeHtml(c.titre)}">
                    <div class="titre">${escapeHtml(c.titre)}</div>
                    <div class="artiste">${escapeHtml(c.artiste)}</div>
                    <div class="barre-votes-container">
                        <div class="barre-votes" style="width:${pct}%"></div>
                    </div>
                    <div class="votes-label">${c.votes} vote${c.votes > 1 ? 's' : ''}</div>
                </div>
            `;
        }).join('');
    }

    renderChansons();

    // --- Progression chanson en cours ---
    let progressionMs = 0;
    let dureeMs = 0;
    let enLecture = false;
    let dernierTimestamp = null;

    function msVersMinSec(ms) {
        const totalSec = Math.floor(ms / 1000);
        const min = Math.floor(totalSec / 60);
        const sec = totalSec % 60;
        return `${min}:${sec.toString().padStart(2, '0')}`;
    }

    function mettreAJourBarre() {
        if (dureeMs === 0) return;
        const pct = Math.min((progressionMs / dureeMs) * 100, 100);
        document.getElementById('barre').style.width = pct + '%';
        document.getElementById('temps').textContent =
            `${msVersMinSec(progressionMs)} / ${msVersMinSec(dureeMs)}`;
    }

    setInterval(() => {
        if (enLecture && dernierTimestamp) {
            const maintenant = Date.now();
            const ecoule = maintenant - dernierTimestamp;
            progressionMs = Math.min(progressionMs + ecoule, dureeMs);
            dernierTimestamp = maintenant;
            mettreAJourBarre();
        }
    }, 500);

    socket.on('connect', () => {
        socket.emit('rejoindre_salle', { salle: salleNom });
    });

    socket.on('chanson_en_cours', (data) => {
        progressionMs = data.progression_ms;
        dureeMs = data.duree_ms;
        enLecture = data.en_lecture;
        dernierTimestamp = Date.now();

        document.getElementById('titre-en-cours').textContent = data.titre;
        document.getElementById('artiste-en-cours').textContent = data.artiste;
        document.getElementById('pochette-en-cours').src = data.pochette;
        mettreAJourBarre();
    });

    socket.on('mise_a_jour_votes', (data) => {
        if (data.salle && data.salle !== salleNom) return;
        chansons = data.chansons;
        if (data.tour !== undefined) tourActuel = data.tour;
        renderChansons();
    });

    socket.on('file_attente', (data) => {
        const fileDiv = document.getElementById('file-attente');
        const fileListe = document.getElementById('file-liste');

        if (data.file && data.file.length > 0) {
            fileDiv.style.display = 'block';
            fileListe.innerHTML = data.file.map((chanson, index) => {
                const salleTag = chanson.salle
                    ? `<span class="pastille-salle" style="background:rgba(var(--accent-rgb),0.2);color:var(--accent)">${escapeHtml(chanson.salle)}</span>`
                    : '';
                const prochaine = index === 0
                    ? '<div style="color:var(--accent)">▶ Prochaine</div>'
                    : '';
                return `
                    <div class="chanson-card">
                        <img src="${chanson.pochette}" alt="${escapeHtml(chanson.titre)}">
                        <div class="titre">${escapeHtml(chanson.titre)}</div>
                        <div class="artiste">${escapeHtml(chanson.artiste)}</div>
                        ${salleTag}
                        ${prochaine}
                    </div>
                `;
            }).join('');
        } else {
            fileDiv.style.display = 'none';
        }
    });
})();
