(function() {
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
