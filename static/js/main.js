// Функція для сторінки закладок (bookmarks.html)
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

// Функція для сторінки оптимізації (prepare.html)
function downloadAllOptimized() {
    // Знаходимо всі форми в блоці результатів
    const allForms = document.querySelectorAll('.optimization-results .result-item .actions form');

    // Фільтруємо форми: залишаємо тільки ті, що НЕ є відео або аудіо
    const formsToSubmit = Array.from(allForms).filter(form => {
        const typeInput = form.querySelector('input[name="type"]');
        if (!typeInput) return false;

        const type = typeInput.value;
        // Список типів, які треба ігнорувати
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

    // Запускаємо сабміт форм із затримкою
    formsToSubmit.forEach((form, index) => {
        setTimeout(() => {
            // Примусово встановлюємо target="_blank", щоб завантаження
            // відкривалося в новій вкладці/фоні і не блокувало поточну сторінку
            // для виконання наступних ітерацій циклу.
            form.target = '_blank';

            form.submit();

        }, 800 * index); // Інтервал 800мс, щоб не "задушити" браузер
    });
}