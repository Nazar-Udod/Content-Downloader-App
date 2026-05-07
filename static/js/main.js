function toggleFolder(folderId) {
    var list = document.getElementById('list-' + folderId);
    var arrow = document.getElementById('arrow-' + folderId);
    var header = document.getElementById('header-' + folderId);

    if (list.classList.contains('open')) {
        list.classList.remove('open');
        arrow.classList.remove('open');
        header.classList.remove('active');
    } else {
        list.classList.add('open');
        arrow.classList.add('open');
        header.classList.add('active');
    }
}

function downloadAllOptimized() {
    const allForms = document.querySelectorAll('.optimization-results .result-item .actions form');

    const formsToSubmit = Array.from(allForms).filter(form => {
        const typeInput = form.querySelector('input[name="type"]');
        if (!typeInput) return false;

        const type = typeInput.value;
        const ignoredTypes = ['video', 'audio_yt_music', 'audio_spotify'];

        return !ignoredTypes.includes(type);
    });

    if (formsToSubmit.length === 0) {
        alert('Немає файлів для завантаження (документів або веб-сторінок).');
        return;
    }

    if (!confirm(`Буде завантажено ${formsToSubmit.length} файлів. Продовжити?`)) {
        return;
    }

    formsToSubmit.forEach((form, index) => {
        setTimeout(() => {
            form.target = '_blank';

            form.submit();

        }, 800 * index);
    });
}