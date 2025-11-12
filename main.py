import os
import io
import asyncio
from playwright.async_api import async_playwright, Browser, Error as PlaywrightError  # Додано
import serpapi
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware
import requests
import yt_dlp
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
    APP_SECRET_KEY = "temp_dev_key_please_replace"

app.add_middleware(
    SessionMiddleware,
    secret_key=APP_SECRET_KEY,
    https_only=False,
    max_age=86400 * 14
)

# Оцінки розмірів
ESTIMATED_PDF_MB = 2.0
ESTIMATED_SPOTIFY_MB = 5.0
ESTIMATED_VIDEO_MB = 150.0
ESTIMATED_AUDIO_MB = 5.0

# Папка кешу
PDF_CACHE_DIR = Path("pdf_cache")

# --- Глобальні змінні Playwright ---
playwright_context = None
browser_instance: Browser | None = None


@app.on_event("startup")
async def on_startup():
    """
    Переконуємося, що папка кешу існує ТА запускаємо Playwright.
    """
    global playwright_context, browser_instance

    PDF_CACHE_DIR.mkdir(exist_ok=True)
    print(f"Папка кешу PDF знаходиться тут: {PDF_CACHE_DIR.resolve()}")

    print("Запуск Playwright...")
    try:
        playwright_context = await async_playwright().start()
        # Ми запускаємо лише chromium, оскільки він найкраще підходить для PDF
        browser_instance = await playwright_context.chromium.launch()
        print("Браузер Chromium (Playwright) успішно запущено.")
    except Exception as e:
        print(f"!!! ПОМИЛКА ЗАПУСКУ PLAYWRIGHT !!!")
        print(f"PDF-генерація не працюватиме.")
        print(f"Переконайтеся, що ви виконали: 'pip install playwright' та 'python -m playwright install chromium'")
        print(f"Деталі помилки: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    """Закриваємо Playwright при зупинці сервера."""
    global playwright_context, browser_instance
    if browser_instance:
        await browser_instance.close()
        print("Браузер Chromium (Playwright) закрито.")
    if playwright_context:
        await playwright_context.stop()
        print("Playwright зупинено.")


# --- Допоміжні функції ---

def get_external_content_size_mb(link: str, content_type: str) -> (float, bool):
    """
    Отримує розмір для ЗОВНІШНІХ ресурсів (не для 'text').
    """
    try:
        if content_type in ['pdf', 'doc', 'ppt']:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            response = requests.head(link, allow_redirects=True, timeout=5, headers=headers)

            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                if content_length:
                    return round(int(content_length) / (1024 * 1024), 2), False
            return ESTIMATED_PDF_MB, True


        elif content_type == 'video':

            ydl_opts = {

                'quiet': True,

                'no_warnings': True,

            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:


                info = ydl.extract_info(link, download=False)

                formats = info.get('formats', [])

                video_size = 0

                audio_size = 0

                video_streams = [

                    f for f in formats

                    if f.get('vcodec') != 'none' and f.get('acodec') == 'none' and (
                                f.get('filesize') or f.get('filesize_approx'))

                ]

                if video_streams:
                    # Пріоритет за_висотою кадру

                    best_video_stream = max(video_streams, key=lambda f: f.get('height', 0))

                    video_size = best_video_stream.get('filesize') or best_video_stream.get('filesize_approx')

                audio_streams = [

                    f for f in formats

                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and (
                                f.get('filesize') or f.get('filesize_approx'))

                ]

                if audio_streams:
                    # Пріоритет за_аудіо бітрейтом (abr)

                    best_audio_stream = max(audio_streams, key=lambda f: f.get('abr', 0))

                    audio_size = best_audio_stream.get('filesize') or best_audio_stream.get('filesize_approx')


                if video_size > 0 and audio_size > 0:
                    total_size_bytes = video_size + audio_size

                    return round(total_size_bytes / (1024 * 1024), 2), False


                progressive_streams = [

                    f for f in formats

                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and (
                                f.get('filesize') or f.get('filesize_approx'))

                ]

                if progressive_streams:

                    best_prog_stream = max(progressive_streams, key=lambda f: f.get('height', 0))

                    prog_size = best_prog_stream.get('filesize') or best_prog_stream.get('filesize_approx')

                    if prog_size:
                        return round(prog_size / (1024 * 1024), 2), False

            return ESTIMATED_VIDEO_MB, True


        elif content_type == 'audio_yt_music':

            ydl_opts = {

                'format': 'bestaudio/best',

                'quiet': True,

                'no_warnings': True,

            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:

                info = ydl.extract_info(link, download=False)

                filesize = info.get('filesize') or info.get('filesize_approx')

                if filesize:
                    return round(filesize / (1024 * 1024), 2), False

            return ESTIMATED_AUDIO_MB, True

    except Exception as e:
        print(f"Помилка отримання зовнішнього розміру для {link}: {e}")
        if content_type == 'video':
            return ESTIMATED_VIDEO_MB, True
        elif content_type == 'audio_yt_music':
            return ESTIMATED_AUDIO_MB, True
        else:
            return ESTIMATED_PDF_MB, True
    return 0.0, True


async def update_item_size(item: dict) -> dict:
    """
    ДОПОМІЖНА АСИНХРОННА ФУНКЦІЯ
    """
    updated_item = item.copy()
    size_mb = None
    is_estimated = False
    cache_file = updated_item.get('cache_file')

    try:
        if updated_item['type'] == 'text':
            if not cache_file:
                url_hash = hashlib.md5(updated_item['link'].encode()).hexdigest()
                cache_file = f"{url_hash}.pdf"

            cache_path = PDF_CACHE_DIR / cache_file
            updated_item['cache_file'] = cache_file

            if not cache_path.exists():
                if browser_instance is None:
                    raise Exception("Браузер Playwright не запущено. Пропуск генерації PDF.")

                print(f"Генерація PDF (Playwright) для: {updated_item['link']}...")
                page = None
                try:
                    page = await browser_instance.new_page()
                    await page.goto(updated_item['link'], timeout=15000, wait_until='domcontentloaded')

                    await page.pdf(path=str(cache_path))

                    print(f"Збережено в: {cache_path}")

                except PlaywrightError as e:
                    print(f"!!! ПОМИЛКА (Playwright) для {updated_item['link']}: {e.message.splitlines()[0]}")
                    print(f"--- Використовуємо приблизний розмір.")
                    updated_item['cache_file'] = None
                    size_mb = ESTIMATED_PDF_MB
                    is_estimated = True

                finally:
                    if page:
                        await page.close()

            # Якщо файл існує (був там, або ми його щойно створили)
            if cache_path.exists():
                size_bytes = cache_path.stat().st_size
                size_mb = round(size_bytes / (1024 * 1024), 2)
                is_estimated = False

            # Якщо сталася помилка Playwright, size_mb та is_estimated вже встановлені
            elif updated_item['cache_file'] is None:
                pass  # Помилка вже оброблена

            else:
                # Дивний випадок: помилки не було, але файлу немає
                raise Exception(f"Файл кешу {cache_path} не знайдено, хоча помилки Playwright не було.")

        elif updated_item['type'] == 'audio_spotify':
            size_mb = ESTIMATED_SPOTIFY_MB
            is_estimated = True

        else:
            # Для всіх інших типів (video, audio_yt, pdf, doc...)
            size_mb, is_estimated = get_external_content_size_mb(updated_item['link'], updated_item['type'])

    except Exception as e:
        print(f"ПОМИЛКА (update_item_size) для {updated_item['link']}: {e}")
        # Загальний запасний варіант
        if updated_item['type'] == 'video':
            size_mb = ESTIMATED_VIDEO_MB
        elif updated_item['type'] in ['audio_yt_music', 'audio_spotify']:
            size_mb = ESTIMATED_AUDIO_MB
        else:
            size_mb = ESTIMATED_PDF_MB

        is_estimated = True
        updated_item['cache_file'] = None

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
    optimization_list = request.session.get("optimization_list", [])

    convert_error = request.session.pop("convert_error", None)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "optimization_count": len(optimization_list),
        "convert_error": convert_error
    })


@app.post("/search", response_class=HTMLResponse)
async def search_content(request: Request, query: str = Form(...)):
    """
    Обробляє пошуковий запит.
    """
    if not SERPAPI_API_KEY:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Ключ Serp API не налаштовано..."
        })

    optimization_list = request.session.get("optimization_list", [])

    convert_error = request.session.pop("convert_error", None)

    client = serpapi.Client()
    try:
        results = client.search({"q": query, "engine": "google", "api_key": SERPAPI_API_KEY})
        processed_results = []
        if 'organic_results' in results:
            for result in results['organic_results']:
                link = result.get('link', '')
                title = result.get('title', '')
                if not link or not title: continue

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
                    'title': title, 'link': link,
                    'snippet': result.get('snippet', ''), 'type': result_type
                })

        return templates.TemplateResponse("index.html", {
            "request": request, "results": processed_results, "query": query,
            "optimization_count": len(optimization_list)
        })
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request, "error": f"Виникла помилка під час пошуку: {e}",
            "optimization_count": len(optimization_list)
        })


@app.post("/convert")
async def convert_to_pdf(request: Request, url: str = Form(...)):
    """
    Конвертує URL в PDF.
    Повертає PDF або перенаправляє на / з помилкою.
    """
    if browser_instance is None:
        # Помилка сервера. Записуємо в сесію і перенаправляємо
        request.session["convert_error"] = "Сервіс генерації PDF не запущено (Playwright)."
        return RedirectResponse(url="/", status_code=303)

    page = None
    try:
        page = await browser_instance.new_page()
        await page.goto(url, timeout=15000, wait_until='domcontentloaded')

        pdf_content = await page.pdf()

        parsed_url = urlparse(url)
        filename = f"{parsed_url.netloc.replace('.', '_')}.pdf"

        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except PlaywrightError as e:
        error_message = e.message.splitlines()[0]
        print(f"ПОМИЛКА (Playwright) /convert для {url}: {error_message}")
        request.session["convert_error"] = f"Не вдалося згенерувати PDF (Playwright): {error_message}"
        return RedirectResponse(url="/", status_code=303)

    except Exception as e:
        print(f"ЗАГАЛЬНА ПОМИЛКА /convert для {url}: {e}")
        request.session["convert_error"] = f"Загальна помилка сервера: {e}"
        return RedirectResponse(url="/", status_code=303)

    finally:
        if page:
            await page.close()


@app.post("/add-to-list")
async def add_to_list(request: Request):
    """
    Додає обрані елементи до сесії.
    """
    form_data = await request.form()
    selected_indices = form_data.getlist("selected_indices")
    optimization_list = request.session.get("optimization_list", [])
    existing_links = {item['link'] for item in optimization_list}

    if selected_indices:
        for index in selected_indices:
            link = form_data.get(f"link_{index}")
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
                existing_links.add(link)

    request.session["optimization_list"] = optimization_list
    return RedirectResponse(url="/", status_code=303)


@app.get("/optimization-list", response_class=HTMLResponse)
async def get_optimization_list(request: Request):
    """
    Відображає сторінку налаштування ("prepare.html").
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
    Очищує список оптимізації.
    """
    request.session["optimization_list"] = []
    request.session["memory_size"] = 1000
    return RedirectResponse(url="/", status_code=303)


@app.post("/fetch-sizes")
async def fetch_sizes(request: Request):
    """
    Примусово оновлює розміри для ВСІХ елементів у сесії,
    використовуючи asyncio.gather для паралельної обробки.
    """
    optimization_list = request.session.get("optimization_list", [])

    print(f"Отримання розмірів для {len(optimization_list)} елементів (паралельно)...")

    # Створюємо список завдань
    tasks = [update_item_size(item) for item in optimization_list]

    # Запускаємо всі завдання паралельно
    updated_list = await asyncio.gather(*tasks)

    print("Отримання розмірів завершено.")

    # Зберігаємо оновлений список
    request.session["optimization_list"] = updated_list

    return RedirectResponse(url="/optimization-list", status_code=303)


@app.get("/download-pdf/{filename}")
async def download_cached_pdf(filename: str):
    """
    Надає доступ до завантаження згенерованого PDF з кешу.
    """
    cache_path = PDF_CACHE_DIR / filename
    if not cache_path.exists():
        return HTMLResponse(content="<h1>Файл не знайдено</h1><p>Можливо, кеш було очищено.</p>", status_code=404)

    return FileResponse(
        path=cache_path,
        media_type="application/pdf",
        filename=f"{filename}.pdf"
    )


@app.post("/optimize", response_class=HTMLResponse)
async def optimize_content(request: Request):
    """
    Виконує оптимізацію.
    Якщо розміри відсутні, він асинхронно оновить їх ПЕРЕД запуском алгоритму.
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

    # --- Оновлення відсутніх розмірів ---
    items_with_size = []
    items_needing_size = []

    for item in items_to_optimize:
        # Перевіряємо, чи відсутній розмір (None, 0.0)
        if item.get('size_mb') is None or item.get('size_mb') == 0.0:
            items_needing_size.append(item)
        else:
            items_with_size.append(item)

    # Якщо є елементи, які потребують оновлення розміру
    if items_needing_size:
        print(f"Оптимізація: оновлення {len(items_needing_size)} відсутніх розмірів (паралельно)...")

        # Запускаємо оновлення паралельно
        tasks = [update_item_size(item) for item in items_needing_size]
        updated_items = await asyncio.gather(*tasks)

        # Об'єднуємо списки
        items_to_optimize = items_with_size + updated_items
        print("Оновлення розмірів завершено.")

    # --- Кінець оновлення розмірів ---

    # Зберігаємо оновлені ваги, розміри та об'єм пам'яті в сесії
    request.session["optimization_list"] = items_to_optimize
    request.session["memory_size"] = memory_size

    # --- АЛГОРИТМ РЮКЗАКА (МЕТОД ГІЛОК ТА МЕЖ) ---
    optimized_results = []
    try:
        mb_limit = float(memory_size)
        processed_items = []
        free_items_indices = set()

        for i, item in enumerate(items_to_optimize):
            size = item.get('size_mb', 0.0)
            value = item.get('weight', 0)
            if value <= 0 or size < 0: continue
            if size == 0.0:
                free_items_indices.add(i)
                continue
            if size > mb_limit: continue
            processed_items.append({
                'value': value, 'size': size,
                'density': value / size, 'original_index': i
            })

        processed_items.sort(key=lambda x: x['density'], reverse=True)
        n = len(processed_items)
        Vbest = 0.0
        best_selection_indices = set()

        def calculate_bound(node_index: int, current_value: float, current_size: float) -> float:
            bound = current_value
            total_size = current_size
            for i in range(node_index, n):
                item = processed_items[i]
                if total_size + item['size'] <= mb_limit:
                    total_size += item['size']
                    bound += item['value']
                else:
                    remaining_capacity = mb_limit - total_size
                    bound += item['density'] * remaining_capacity
                    break
            return bound

        def solve_knapsack(node_index: int, current_value: float, current_size: float,
                           current_selection_indices: list):
            nonlocal Vbest, best_selection_indices
            if node_index == n:
                if current_value > Vbest:
                    Vbest = current_value
                    best_selection_indices = set(current_selection_indices)
                return

            bound = calculate_bound(node_index, current_value, current_size)
            if bound <= Vbest: return

            item = processed_items[node_index]
            if current_size + item['size'] <= mb_limit:
                current_selection_indices.append(item['original_index'])
                solve_knapsack(
                    node_index + 1,
                    current_value + item['value'],
                    current_size + item['size'],
                    current_selection_indices
                )
                current_selection_indices.pop()

            solve_knapsack(
                node_index + 1,
                current_value,
                current_size,
                current_selection_indices
            )

        solve_knapsack(0, 0.0, 0.0, [])
        final_indices = best_selection_indices.union(free_items_indices)
        for i in final_indices:
            optimized_results.append(items_to_optimize[i])

    except Exception as e:
        return templates.TemplateResponse("prepare.html", {
            "request": request, "items": items_to_optimize, "memory_size": memory_size,
            "error": f"Помилка під час оптимізації: {e}",
            "total_size": round(sum(item.get('size_mb', 0) for item in items_to_optimize), 2)
        })

    # Повертаємо ту саму сторінку з результатами
    return templates.TemplateResponse("prepare.html", {
        "request": request,
        "items": items_to_optimize,
        "memory_size": memory_size,
        "optimized_results": optimized_results,
        "total_size": round(sum(item.get('size_mb', 0) for item in items_to_optimize), 2)
    })