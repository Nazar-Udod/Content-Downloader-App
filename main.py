import os
import io
import pdfkit
import serpapi
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import requests
from pytube import YouTube
import math
import hashlib
from pathlib import Path

# --- Конфігурація ---

# Завантажуємо змінні з .env файлу
load_dotenv()

app = FastAPI(
    title="Web Content Downloader API",
    description="Система для пошуку та завантаження контенту з мережі.",
    version="0.1.0"
)

# Налаштування для шаблонів Jinja2
templates = Jinja2Templates(directory="templates")

# Отримання ключа API з системних змінних
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")

# Мідлвер сесій
if not APP_SECRET_KEY:
    print("ПОПЕРЕДЖЕННЯ: APP_SECRET_KEY не встановлено. Сесії не будуть безпечними.")
    # Використовуємо тимчасовий ключ для розробки, АЛЕ це НЕБЕЗПЕЧНО для production
    APP_SECRET_KEY = "temp_dev_key_please_replace"

app.add_middleware(
    SessionMiddleware,
    secret_key=APP_SECRET_KEY,
    https_only=False, # Встановити True у production при наявності HTTPS
    max_age=86400 * 14 # 14 днів
)

# Використовуємо, коли точний розмір неможливо отримати
ESTIMATED_PDF_MB = 2.0
ESTIMATED_SPOTIFY_MB = 5.0
ESTIMATED_VIDEO_MB = 150.0 # Запасний варіант для YouTube
ESTIMATED_AUDIO_MB = 5.0  # Запасний варіант для YT Music


# Папка кешу
PDF_CACHE_DIR = Path("pdf_cache")
@app.on_event("startup")
def on_startup():
    """Переконуємося, що папка для кешу PDF існує."""
    PDF_CACHE_DIR.mkdir(exist_ok=True)
    print(f"Папка кешу PDF знаходиться тут: {PDF_CACHE_DIR.resolve()}")

# Знаходимо розмір матеріалу
def get_external_content_size_mb(link: str, content_type: str) -> (float, bool):
    """
    Отримує розмір для ЗОВНІШНІХ ресурсів (не для 'text').
    Повертає (size_mb, is_estimated)
    """
    try:
        if content_type in ['pdf', 'doc', 'ppt']:
            # Додаємо user-agent, щоб уникнути блокування 403
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            # allow_redirects=True - важливо, оскільки посилання часто є перенаправленнями
            response = requests.head(link, allow_redirects=True, timeout=5, headers=headers)

            print(f"DEBUG: HEAD to {link}")
            print(f"DEBUG: Status Code: {response.status_code}")
            print(f"DEBUG: Headers: {response.headers}")

            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                if content_length:
                    size_bytes = int(content_length)
                    return round(size_bytes / (1024 * 1024), 2), False  # Точний розмір

            # Якщо щось пішло не так, повертаємо оцінку
            return ESTIMATED_PDF_MB, True

        elif content_type == 'video':
            yt = YouTube(link)
            # Шукаємо "прогресивний" потік (відео + аудіо) з роздільною здатністю 720p або нижче
            stream = yt.streams.filter(progressive=True, file_extension='mp4').get_highest_resolution()
            if stream:
                return round(stream.filesize / (1024 * 1024), 2), False  # Точний розмір
            return ESTIMATED_VIDEO_MB, True  # Оцінка

        elif content_type == 'audio_yt_music':
            yt = YouTube(link)
            stream = yt.streams.get_audio_only()
            if stream:
                return round(stream.filesize / (1024 * 1024), 2), False  # Точний розмір
            return ESTIMATED_AUDIO_MB, True  # Оцінка

    except Exception as e:
        print(f"Помилка отримання зовнішнього розміру для {link}: {e}")
        # Повертаємо оцінку у разі помилки
        if content_type == 'video':
            return ESTIMATED_VIDEO_MB, True
        elif content_type == 'audio_yt_music':
            return ESTIMATED_AUDIO_MB, True
        else:
            return ESTIMATED_PDF_MB, True

    # Запасний варіант, якщо тип контенту невідомий (хоча цього не має статися)
    return 0.0, True


def update_item_size(item: dict) -> dict:
    """
    ДОПОМІЖНА ФУНКЦІЯ:
    Отримує один елемент (dict), визначає його розмір
    (генеруючи PDF або роблячи зовнішній запит)
    і повертає оновлений елемент (dict).
    """
    # Ми копіюємо, щоб уникнути несподіваних змін
    updated_item = item.copy()

    size_mb = None
    is_estimated = False
    cache_file = updated_item.get('cache_file')

    try:
        if updated_item['type'] == 'text':
            # Створюємо унікальне, стабільне ім'я файлу на основі URL
            if not cache_file:
                url_hash = hashlib.md5(updated_item['link'].encode()).hexdigest()
                cache_file = f"{url_hash}.pdf"

            cache_path = PDF_CACHE_DIR / cache_file

            # Генеруємо, ТІЛЬКИ ЯКЩО файл ще не в кеші
            if not cache_path.exists():
                print(f"Генерація PDF для: {updated_item['link']}...")
                # Вказуємо шлях як рядок для pdfkit
                pdfkit.from_url(updated_item['link'], str(cache_path))
                print(f"Збережено в: {cache_path}")

            # Отримуємо розмір з файлу
            size_bytes = cache_path.stat().st_size
            size_mb = round(size_bytes / (1024 * 1024), 2)
            is_estimated = False
            updated_item['cache_file'] = cache_file

        elif updated_item['type'] == 'audio_spotify':
            size_mb = ESTIMATED_SPOTIFY_MB
            is_estimated = True

        else:
            # Для всіх інших типів (video, audio_yt, pdf, doc...)
            size_mb, is_estimated = get_external_content_size_mb(updated_item['link'], updated_item['type'])

    except Exception as e:
        print(f"ПОМИЛКА (update_item_size) для {updated_item['link']}: {e}")
        # Використовуємо оцінки як запасний варіант
        if updated_item['type'] == 'video':
            size_mb = ESTIMATED_VIDEO_MB
        elif updated_item['type'] in ['audio_yt_music', 'audio_spotify']:
            size_mb = ESTIMATED_AUDIO_MB
        else:
            size_mb = ESTIMATED_PDF_MB
        is_estimated = True
        updated_item['cache_file'] = None  # Помилка, отже кеш-файлу немає

    # Оновлюємо елемент
    updated_item['size_mb'] = size_mb
    updated_item['is_estimated'] = is_estimated

    return updated_item

# --- Ендпоінти ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Головна сторінка, яка відображає форму пошуку.
    """
    # Отримуємо поточний список оптимізації з сесії
    optimization_list = request.session.get("optimization_list", [])

    return templates.TemplateResponse("index.html", {
        "request": request,
        "optimization_count": len(optimization_list)
    })


@app.post("/search", response_class=HTMLResponse)
async def search_content(request: Request, query: str = Form(...)):
    """
    Обробляє пошуковий запит, використовуючи Serp API,
    та повертає результати на головну сторінку.
    """
    if not SERPAPI_API_KEY:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Ключ Serp API не налаштовано..."
        })

    # Отримуємо поточний список оптимізації з сесії для лічильника
    optimization_list = request.session.get("optimization_list", [])

    client = serpapi.Client()
    try:
        results = client.search({
            "q": query,
            "engine": "google",
            "api_key": SERPAPI_API_KEY,
        })

        processed_results = []
        if 'organic_results' in results:
            for result in results['organic_results']:
                link = result.get('link', '')
                title = result.get('title', '')

                if not link or not title:
                    continue

                result_type = 'text'
                if link.endswith('.pdf') or title.startswith('[PDF]'):
                    result_type = 'pdf'
                elif link.endswith('.doc') or link.endswith('.docx'):
                    result_type = 'doc'
                elif link.endswith('.ppt') or link.endswith('.pptx'):
                    result_type = 'ppt'
                elif 'youtube.com/watch' in link:
                    result_type = 'video'
                elif 'music.youtube.com' in link:
                    result_type = 'audio_yt_music'
                elif 'open.spotify.com' in link:
                    result_type = 'audio_spotify'

                processed_results.append({
                    'title': title,
                    'link': link,
                    'snippet': result.get('snippet', ''),
                    'type': result_type
                })

        return templates.TemplateResponse("index.html", {
            "request": request,
            "results": processed_results,
            "query": query,
            "optimization_count": len(optimization_list)  # Передаємо лічильник
        })
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Виникла помилка під час пошуку: {e}",
            "optimization_count": len(optimization_list)
        })


@app.post("/convert")
async def convert_to_pdf(url: str = Form(...)):
    """
    Конвертує URL в PDF.
    """
    try:
        pdf_content = pdfkit.from_url(url, False)
        parsed_url = urlparse(url)
        filename = f"{parsed_url.netloc.replace('.', '_')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        return HTMLResponse(
            content=f"<h1>Помилка конвертації</h1><p>{e}</p>",
            status_code=500
        )


@app.post("/add-to-list")
async def add_to_list(request: Request):
    """
    Отримує обрані елементи з пошуку, додає їх до списку в сесії
    та перенаправляє користувача назад на головну сторінку.
    """
    form_data = await request.form()
    selected_indices = form_data.getlist("selected_indices")

    # Отримуємо *існуючий* список із сесії
    optimization_list = request.session.get("optimization_list", [])

    # Створюємо set з існуючих посилань для швидкої перевірки на дублікати
    existing_links = {item['link'] for item in optimization_list}

    if selected_indices:
        for index in selected_indices:
            link = form_data.get(f"link_{index}")

            # Додаємо, тільки якщо посилання ще немає у списку
            if link not in existing_links:
                optimization_list.append({
                    "title": form_data.get(f"title_{index}"),
                    "link": link,
                    "snippet": form_data.get(f"snippet_{index}"),
                    "type": form_data.get(f"type_{index}"),
                    "weight": int(form_data.get(f"weight_{index}", 5)),
                    "size_mb": None,
                    "is_estimated": False,
                    "cache_file": None
                })
                existing_links.add(link)  # Оновлюємо set

    # Зберігаємо оновлений список назад у сесію
    request.session["optimization_list"] = optimization_list

    # Повертаємо користувача на головну сторінку
    return RedirectResponse(url="/", status_code=303)


@app.get("/optimization-list", response_class=HTMLResponse)
async def get_optimization_list(request: Request):
    """
    Відображає сторінку налаштування ("prepare.html")
    з повним списком елементів, збережених у сесії.
    """
    items = request.session.get("optimization_list", [])
    total_size = sum(item.get('size_mb', 0) for item in items if item.get('size_mb'))

    return templates.TemplateResponse("prepare.html", {
        "request": request,
        "items": items,
        "memory_size": request.session.get("memory_size", 1000),
        "total_size": round(total_size, 2)
    })


@app.get("/clear-list")
async def clear_list(request: Request):
    """
    Повністю очищує список оптимізації в сесії.
    """
    # Очищуємо сесію
    request.session["optimization_list"] = []
    request.session["memory_size"] = 1000

    # Перенаправляємо на головну сторінку ("/")
    return RedirectResponse(url="/", status_code=303)


@app.post("/fetch-sizes")
async def fetch_sizes(request: Request):
    """
    Примусово оновлює розміри для ВСІХ елементів у сесії,
    використовуючи допоміжну функцію update_item_size.
    """
    optimization_list = request.session.get("optimization_list", [])
    updated_list = []

    for item in optimization_list:
        # Викликаємо нашу нову функцію для кожного елемента
        updated_list.append(update_item_size(item))

    # Зберігаємо оновлений список
    request.session["optimization_list"] = updated_list

    # Повертаємо користувача на сторінку оптимізації
    return RedirectResponse(url="/optimization-list", status_code=303)

@app.get("/download-pdf/{filename}")
async def download_cached_pdf(filename: str):
    """
    Надає доступ до завантаження згенерованого PDF з кешу.
    """
    cache_path = PDF_CACHE_DIR / filename
    if not cache_path.exists():
        return HTMLResponse(content="<h1>Файл не знайдено</h1><p>Можливо, кеш було очищено.</p>", status_code=404)

    # Використовуємо FileResponse для ефективної віддачі файлу
    return FileResponse(
        path=cache_path,
        media_type="application/pdf",
        filename=f"{filename}.pdf"  # Пропонуємо користувачу ім'я файлу
    )


@app.post("/optimize", response_class=HTMLResponse)
async def optimize_content(request: Request):
    """
    Приймає список матеріалів зі сторінки налаштування (з оновленими вагами)
    та об'єм пам'яті. Виконує "оптимізацію" та оновлює сесію.
    """
    form_data = await request.form()
    memory_size = form_data.get("memory_size", "1000")
    item_count = int(form_data.get("item_count", 0))

    items_to_optimize = []
    for i in range(item_count):
        size_mb_str = form_data.get(f"size_mb_{i}", "0.0")
        try:
            size_mb = float(size_mb_str)
        except ValueError:
            size_mb = 0.0

        items_to_optimize.append({
            "title": form_data.get(f"title_{i}"),
            "link": form_data.get(f"link_{i}"),
            "snippet": form_data.get(f"snippet_{i}"),
            "type": form_data.get(f"type_{i}"),
            "weight": int(form_data.get(f"weight_{i}", 5)),
            "size_mb": size_mb,
            "is_estimated": form_data.get(f"is_estimated_{i}") == 'True',
            "cache_file": form_data.get(f"cache_file_{i}")
        })
        # Оновлюємо відсутні розміри
        fully_updated_list = []
        needs_update = False

        for item in items_to_optimize:
            # Перевіряємо, чи відсутній розмір
            if item.get('size_mb') is None or item.get('size_mb') == 0.0:
                needs_update = True
                updated_item = update_item_size(item)
                fully_updated_list.append(updated_item)
            else:
                fully_updated_list.append(item)

        if needs_update:
            items_to_optimize = fully_updated_list  # Використовуємо список з новими розмірами

        # Зберігаємо оновлені ваги та об'єм пам'яті в сесії
        request.session["optimization_list"] = items_to_optimize
        request.session["memory_size"] = memory_size

        # --- ЗАГЛУШКА АЛГОРИТМУ ---
        try:
            mb_limit = int(memory_size)
            optimized_results = sorted(items_to_optimize, key=lambda x: x['weight'], reverse=True)

        except Exception as e:
            return templates.TemplateResponse("prepare.html", {
                "request": request,
                "items": items_to_optimize,
                "memory_size": memory_size,
                "error": f"Помилка під час оптимізації: {e}",
                "total_size": sum(item.get('size_mb', 0) for item in items_to_optimize)
            })
        # --- Кінець заглушки ---

        # Повертаємо ту саму сторінку з результатами
        return templates.TemplateResponse("prepare.html", {
            "request": request,
            "items": items_to_optimize,  # Список з оновленими вагами
            "memory_size": memory_size,
            "optimized_results": optimized_results,  # Результат заглушки
            "total_size": round(sum(item.get('size_mb', 0) for item in items_to_optimize), 2)
        })