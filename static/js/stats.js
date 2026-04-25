(function() {
    const INTERVAL_MS = 5000;

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function rangIcon(idx) {
        if (idx === 1) return '🥇';
        if (idx === 2) return '🥈';
        if (idx === 3) return '🥉';
        return idx;
    }

    function lignesHtml(c) {
        if (!c.users || c.users.length === 0) {
            return '<div class="vide">Aucun vote pour le moment.</div>';
        }
        return c.users.map((user, i) => {
            const idx = i + 1;
            const topClass = idx <= 3 ? `top-${idx}` : '';
            const champ = c.key === 'general' ? user.votes : user.votes_salle;
            let metaParts = [];
            if (c.key === 'general' && user.votes_par_salle) {
                metaParts = Object.entries(user.votes_par_salle)
                    .map(([nom, n]) => `${nom} : ${n}`);
            }
            const meta = c.key === 'general'
                ? `<span class="meta">${metaParts.length ? metaParts.join(' · ') : '—'}</span>`
                : '';
            return `
                <div class="ligne ${topClass}">
                    <div class="rang">${rangIcon(idx)}</div>
                    <div class="pseudo">${escapeHtml(user.pseudo)}${meta}</div>
                    <div class="votes">${champ}<span class="unite"> vote${champ > 1 ? 's' : ''}</span></div>
                </div>
            `;
        }).join('');
    }

    function compteurHtml(c) {
        const champ = c.key === 'general' ? 'votes' : 'votes_salle';
        const total = (c.users || []).reduce((acc, u) => acc + (u[champ] || 0), 0);
        const nbVotants = (c.users || []).length;
        return `${nbVotants} votant${nbVotants > 1 ? 's' : ''} · ${total} vote${total > 1 ? 's' : ''}`;
    }

    async function rafraichir() {
        try {
            const res = await fetch('/stats.json', {cache: 'no-store'});
            if (!res.ok) return;
            const data = await res.json();
            for (const c of data) {
                const panel = document.querySelector(`.panel[data-panel="${c.key}"]`);
                if (!panel) continue;
                const compteur = panel.querySelector('.compteur');
                const classement = panel.querySelector('.classement');
                if (compteur) compteur.textContent = compteurHtml(c);
                if (classement) classement.innerHTML = lignesHtml(c);
            }
        } catch (e) {
            // silencieux : si le serveur est temporairement indispo, on retentera
        }
    }

    setInterval(rafraichir, INTERVAL_MS);
})();