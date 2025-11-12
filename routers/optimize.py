import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from config import templates
from services.content_utils import update_item_size
from services.optimizer import solve_knapsack_problem

router = APIRouter()


@router.post("/optimize", response_class=HTMLResponse)
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
        if item.get('size_mb') is None or item.get('size_mb') == 0.0:
            items_needing_size.append(item)
        else:
            items_with_size.append(item)

    if items_needing_size:
        print(f"Оптимізація: оновлення {len(items_needing_size)} відсутніх розмірів (паралельно)...")
        tasks = [update_item_size(item) for item in items_needing_size]
        updated_items = await asyncio.gather(*tasks)
        items_to_optimize = items_with_size + updated_items
        print("Оновлення розмірів завершено.")
    # --- Кінець оновлення розмірів ---

    # Зберігаємо оновлені дані в сесії
    request.session["optimization_list"] = items_to_optimize
    request.session["memory_size"] = memory_size

    # --- Запуск Алгоритму ---
    optimized_results, error = solve_knapsack_problem(items_to_optimize, memory_size)

    total_size = round(sum(item.get('size_mb', 0) for item in items_to_optimize), 2)

    context = {
        "request": request,
        "items": items_to_optimize,
        "memory_size": memory_size,
        "total_size": total_size,
        "user_email": request.session.get("user_email"),
        "optimization_count": len(items_to_optimize)  # Кількість елементів, які ми оптимізували
    }

    if error:
        context["error"] = error
        return templates.TemplateResponse("prepare.html", context)

    # Додаємо результати до контексту і повертаємо
    context["optimized_results"] = optimized_results
    return templates.TemplateResponse("prepare.html", context)