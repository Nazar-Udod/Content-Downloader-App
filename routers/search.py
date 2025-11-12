import serpapi
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse  # <-- Змінено
from sqlalchemy.ext.asyncio import AsyncSession

from config import SERPAPI_API_KEY
from database import get_db

router = APIRouter()


@router.post("/search")
async def search_content(
        request: Request,
        query: str = Form(...),
):
    """
    Обробляє пошуковий запит, зберігає результати в сесію
    і перенаправляє на головну сторінку.
    """

    # Очищуємо старі результати
    request.session.pop("search_results", None)
    request.session.pop("search_query", None)
    request.session.pop("search_error", None)

    if not SERPAPI_API_KEY:
        request.session["search_error"] = "Ключ Serp API не налаштовано..."
        return RedirectResponse(url="/", status_code=303)

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

        # Зберігаємо результати в сесію
        request.session["search_results"] = processed_results
        request.session["search_query"] = query

    except Exception as e:
        # Зберігаємо помилку в сесію
        request.session["search_error"] = f"Виникла помилка під час пошуку: {e}"
        request.session["search_query"] = query

    # Перенаправляємо користувача на головну сторінку (GET /)
    return RedirectResponse(url="/", status_code=303)