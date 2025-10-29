import os
import io
import pdfkit
import serpapi
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware

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
                    "weight": int(form_data.get(f"weight_{index}", 5))
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

    return templates.TemplateResponse("prepare.html", {
        "request": request,
        "items": items,
        "memory_size": request.session.get("memory_size", 1000)  # Зберігаємо і пам'ять
    })


@app.get("/clear-list")
async def clear_list(request: Request):
    """
    Повністю очищує список оптимізації в сесії.
    """
    request.session["optimization_list"] = []
    request.session["memory_size"] = 1000  # Скинемо і пам'ять

    # Визначаємо, звідки прийшов користувач, і повертаємо його
    referer = request.headers.get("referer", "/")
    # Запобігаємо перенаправленню на сам /clear-list
    if "/clear-list" in referer:
        referer = "/"

    return RedirectResponse(url=referer, status_code=303)


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
        items_to_optimize.append({
            "title": form_data.get(f"title_{i}"),
            "link": form_data.get(f"link_{i}"),
            "snippet": form_data.get(f"snippet_{i}"),
            "type": form_data.get(f"type_{i}"),
            "weight": int(form_data.get(f"weight_{i}", 5))
        })

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
                "error": f"Помилка під час оптимізації: {e}"
            })
        # --- Кінець заглушки ---

        # Повертаємо ту саму сторінку з результатами
        return templates.TemplateResponse("prepare.html", {
            "request": request,
            "items": items_to_optimize,  # Список з оновленими вагами
            "memory_size": memory_size,
            "optimized_results": optimized_results  # Результат заглушки
        })