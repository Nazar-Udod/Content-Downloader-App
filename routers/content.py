import io
import asyncio
from fastapi import APIRouter, Request, Form
from fastapi.responses import (
    HTMLResponse, StreamingResponse, RedirectResponse, FileResponse
)

from config import templates, PDF_CACHE_DIR
from services.content_utils import update_item_size, generate_pdf_for_download

router = APIRouter()


@router.post("/convert")
async def convert_to_pdf(request: Request, url: str = Form(...)):
    """
    Конвертує URL в PDF та віддає на завантаження.
    """
    pdf_content, filename, error = await generate_pdf_for_download(url)

    if error:
        request.session["convert_error"] = error
        return RedirectResponse(url="/", status_code=303)

    return StreamingResponse(
        io.BytesIO(pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/fetch-sizes")
async def fetch_sizes(request: Request):
    """
    Примусово оновлює розміри для ВСІХ елементів у сесії,
    використовуючи asyncio.gather для паралельної обробки.
    """
    optimization_list = request.session.get("optimization_list", [])
    if not optimization_list:
        return RedirectResponse(url="/optimization-list", status_code=303)

    print(f"Отримання розмірів для {len(optimization_list)} елементів (паралельно)...")

    tasks = [update_item_size(item) for item in optimization_list]
    updated_list = await asyncio.gather(*tasks)

    print("Отримання розмірів завершено.")
    request.session["optimization_list"] = updated_list

    return RedirectResponse(url="/optimization-list", status_code=303)


@router.get("/download-pdf/{filename}")
async def download_cached_pdf(filename: str):
    """
    Надає доступ до завантаження згенерованого PDF з кешу.
    """
    # Запобігаємо Path Traversal
    if ".." in filename or "/" in filename:
        return HTMLResponse(content="<h1>Неприпустиме ім'я файлу</h1>", status_code=400)

    cache_path = PDF_CACHE_DIR / filename
    if not cache_path.exists():
        return HTMLResponse(content="<h1>Файл не знайдено</h1><p>Можливо, кеш було очищено.</p>", status_code=404)

    return FileResponse(
        path=cache_path,
        media_type="application/pdf",
        filename=f"{filename}.pdf"  # Надсилаємо оригінальне ім'я
    )