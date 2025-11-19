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
    const itemsToDownload = document.querySelectorAll('.optimization-results .result-item[data-download-url]');

    if (itemsToDownload.length === 0) {
        alert('Немає файлів для завантаження (тільки відео/аудіо).');
        return;
    }

    itemsToDownload.forEach((item, index) => {
        const url = item.dataset.downloadUrl;
        const a = document.createElement('a');
        a.href = url;
        if (url.startsWith('/')) {
            a.download = '';
        } else {
            a.target = '_blank';
        }
        document.body.appendChild(a);
        setTimeout(() => {
            a.click();
            document.body.removeChild(a);
        }, 150 * index);
    });
}