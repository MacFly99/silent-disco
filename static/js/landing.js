(function() {
    const body = document.body;
    const pill = document.getElementById('pseudo-pill');
    const form = document.getElementById('pseudo-form');
    const input = document.getElementById('pseudo-input');
    const submit = document.getElementById('pseudo-submit');

    // ?next=/vote/<salle> : redirection automatique après saisie du pseudo
    // (utilisé quand on arrive depuis un QR code de /displays)
    function lireNext() {
        const params = new URLSearchParams(window.location.search);
        const next = params.get('next');
        // Sécurité : on n'accepte que les paths internes commençant par "/"
        if (next && next.startsWith('/') && !next.startsWith('//')) {
            return next;
        }
        return null;
    }

    function refresh() {
        const pseudo = localStorage.getItem('pseudo') || '';
        const next = lireNext();
        // Si déjà connecté + cible explicite → on y va direct
        if (pseudo && next) {
            window.location.replace(next);
            return;
        }
        if (pseudo) {
            body.classList.add('has-pseudo');
            pill.innerHTML = `<strong>${escapeHtml(pseudo)}</strong> · changer`;
        } else {
            body.classList.remove('has-pseudo');
            setTimeout(() => input.focus(), 50);
        }
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    input.addEventListener('input', () => {
        submit.disabled = input.value.trim().length === 0;
    });

    form.addEventListener('submit', (e) => {
        e.preventDefault();
        const valeur = input.value.trim().slice(0, 30);
        if (!valeur) return;
        localStorage.setItem('pseudo', valeur);
        // Génère et stocke un uuid persistant si pas encore présent
        if (!localStorage.getItem('user_uuid')) {
            const uuid = (crypto.randomUUID && crypto.randomUUID()) ||
                (Date.now().toString(36) + Math.random().toString(36).slice(2));
            localStorage.setItem('user_uuid', uuid);
        }
        input.value = '';
        // Si on arrive depuis un QR code (?next=/vote/...) on saute la sélection de salle
        const next = lireNext();
        if (next) {
            window.location.replace(next);
            return;
        }
        refresh();
    });

    pill.addEventListener('click', () => {
        localStorage.removeItem('pseudo');
        refresh();
    });

    refresh();
})();
