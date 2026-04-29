(function() {
    const socket = io();
    const salles = {};

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function msVersMinSec(ms) {
        const totalSec = Math.floor(ms / 1000);
        const min = Math.floor(totalSec / 60);
        const sec = totalSec % 60;
        return `${min}:${sec.toString().padStart(2, '0')}`;
    }

    // Init un état par salle + DOM refs + QR
    document.querySelectorAll('.tuile').forEach(tuile => {
        const nom = tuile.dataset.salle;
        const initial = (window.INITIAL_STATE.salles || []).find(s => s.nom === nom) || {};

        salles[nom] = {
            tuile,
            chansons: initial.chansons || [],
            tour: initial.tour || 0,
            progressionMs: 0,
            dureeMs: 0,
            enLecture: false,
            dernierTimestamp: null,
            el: {
                pochette: tuile.querySelector('.pochette-en-cours'),
                titre: tuile.querySelector('.titre-en-cours'),
                artiste: tuile.querySelector('.artiste-en-cours'),
                barre: tuile.querySelector('.barre'),
                temps: tuile.querySelector('.temps'),
                chansons: tuile.querySelector('.chansons'),
            },
        };

        // Génère le QR code vers /vote/<salle>
        const qrEl = tuile.querySelector('.qr');
        const url = qrEl.dataset.url;
        if (url && window.QRCode) {
            new QRCode(qrEl, {
                text: url,
                width: 170,
                height: 170,
                colorDark: '#000',
                colorLight: '#fff',
                correctLevel: QRCode.CorrectLevel.M,
            });
        }

        renderChansons(nom);
    });

    function renderChansons(nom) {
        const s = salles[nom];
        if (!s) return;
        const maxVotes = Math.max(...s.chansons.map(c => c.votes), 0);
        s.el.chansons.innerHTML = s.chansons.map(c => {
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

    function mettreAJourBarre(nom) {
        const s = salles[nom];
        if (!s || s.dureeMs === 0) return;
        const pct = Math.min((s.progressionMs / s.dureeMs) * 100, 100);
        s.el.barre.style.width = pct + '%';
        s.el.temps.textContent =
            `${msVersMinSec(s.progressionMs)} / ${msVersMinSec(s.dureeMs)}`;
    }

    setInterval(() => {
        const maintenant = Date.now();
        for (const nom in salles) {
            const s = salles[nom];
            if (s.enLecture && s.dernierTimestamp) {
                const ecoule = maintenant - s.dernierTimestamp;
                s.progressionMs = Math.min(s.progressionMs + ecoule, s.dureeMs);
                s.dernierTimestamp = maintenant;
                mettreAJourBarre(nom);
            }
        }
    }, 500);

    socket.on('connect', () => {
        for (const nom in salles) {
            socket.emit('rejoindre_salle', { salle: nom });
        }
    });

    socket.on('chanson_en_cours', (data) => {
        const nom = data.salle;
        const s = salles[nom];
        if (!s) return;
        s.progressionMs = data.progression_ms;
        s.dureeMs = data.duree_ms;
        s.enLecture = data.en_lecture;
        s.dernierTimestamp = Date.now();
        s.el.titre.textContent = data.titre || 'En attente…';
        s.el.artiste.textContent = data.artiste || '';
        s.el.pochette.src = data.pochette || '';
        mettreAJourBarre(nom);
    });

    socket.on('mise_a_jour_votes', (data) => {
        const s = salles[data.salle];
        if (!s) return;
        s.chansons = data.chansons;
        if (data.tour !== undefined) s.tour = data.tour;
        renderChansons(data.salle);
    });
})();
