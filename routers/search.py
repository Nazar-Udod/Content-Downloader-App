import serpapi
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse

from config import templates, SERPAPI_API_KEY

router = APIRouter()


@router.post("/search", response_class=HTMLResponse)
async def search_content(request: Request, query: str = Form(...)):
    """
    Обробляє пошуковий запит.
    """
    optimization_list = request.session.get("optimization_list", [])
    base_context = {
        "request": request,
        "optimization_count": len(optimization_list),
        "user_email": request.session.get("user_email"),
        "query": query
    }

    if not SERPAPI_API_KEY:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "error": "Ключ Serp API не налаштовано..."
        })

    optimization_list = request.session.get("optimization_list", [])
    client = serpapi.Client()

    try:
        results = client.search({"q": query, "engine": "google", "api_key": SERPAPI_API_KEY})
        processed_results = []
        if 'organic_results' in results:
            for result in results['organic_results']:
                link = result.get('link', '')
                title = result.get('title', '')
                if not link or not title: continue

                # (Логіка визначення типу залишається такою ж)
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

        base_context["results"] = processed_results
        return templates.TemplateResponse("index.html", base_context)

    except Exception as e:
        base_context["error"] = f"Виникла помилка під час пошуку: {e}"
        return templates.TemplateResponse("index.html", base_context)