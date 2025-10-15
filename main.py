import os
import io
import pdfkit
import serpapi
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from urllib.parse import urlparse
from dotenv import load_dotenv

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


# --- Ендпоінти ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """
    Головна сторінка, яка відображає форму пошуку.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/search", response_class=HTMLResponse)
async def search_content(request: Request, query: str = Form(...)):
    """
    Обробляє пошуковий запит, використовуючи Serp API,
    та повертає результати на головну сторінку.
    """
    if not SERPAPI_API_KEY:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Ключ Serp API не налаштовано. Будь ласка, створіть файл .env або встановіть системну змінну."
        })

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
                result_type = 'text'  # За замовчуванням
                if 'youtube.com/watch' in link:
                    result_type = 'video'
                elif 'music.youtube.com' in link:
                    result_type = 'audio_yt_music'
                elif 'open.spotify.com' in link:
                    result_type = 'audio_spotify'

                processed_results.append({
                    'title': result.get('title', 'Без назви'),
                    'link': link,
                    'snippet': result.get('snippet', ''),
                    'type': result_type
                })

        return templates.TemplateResponse("index.html", {
            "request": request,
            "results": processed_results,
            "query": query
        })
    except Exception as e:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": f"Виникла помилка під час пошуку: {e}"
        })


@app.post("/convert")
async def convert_to_pdf(url: str = Form(...)):
    """
    Приймає URL, конвертує HTML-сторінку в PDF за допомогою pdfkit
    і повертає PDF-файл для завантаження.
    """
    try:
        # Конвертуємо URL в PDF. `False` означає, що результат повернеться
        # як байтовий рядок, а не збережеться у файл на сервері.
        pdf_content = pdfkit.from_url(url, False)

        # Створюємо ім'я файлу на основі домену
        parsed_url = urlparse(url)
        filename = f"{parsed_url.netloc.replace('.', '_')}.pdf"

        # Повертаємо потік з PDF-даними
        return StreamingResponse(
            io.BytesIO(pdf_content),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        # Повертаємо HTML-сторінку з повідомленням про помилку
        return HTMLResponse(
            content=f"<h1>Помилка конвертації</h1><p>Не вдалося сконвертувати URL: {url}</p><p>Помилка: {e}</p>",
            status_code=500
        )

