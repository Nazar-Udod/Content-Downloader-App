from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
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


@router.post("/add-to-list")
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


@router.get("/optimization-list", response_class=HTMLResponse)
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


@router.get("/clear-list")
async def clear_list(request: Request):
    """
    Очищує список оптимізації.
    """
    request.session["optimization_list"] = []
    request.session["memory_size"] = 1000
    return RedirectResponse(url="/", status_code=303)