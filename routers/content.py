import io
import asyncio
from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import (
    HTMLResponse, StreamingResponse, RedirectResponse, FileResponse
)
from sqlalchemy.ext.asyncio import AsyncSession

from config import templates, PDF_CACHE_DIR
from database import get_db
from models import User
from services.content_utils import update_item_size, generate_pdf_for_download
from services.auth_service import get_current_user
from services.history_service import add_to_history

router = APIRouter()


@router.post("/convert")
async def convert_to_pdf(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User | None = Depends(get_current_user)
):
    """
    Конвертує URL в PDF.
    Приймає АБО індекс 'convert_index' (з index.html),
    АБО прямий 'url' (з bookmarks.html/history.html).
    """
    form_data = await request.form()
    url = None

    index = form_data.get("convert_index")
    if index is not None:
        url = form_data.get(f"link_{index}")
        if not url:
            request.session["convert_error"] = "Не вдалося знайти URL для конвертації за індексом."
            return RedirectResponse(url="/", status_code=303)

    if url is None:
        url = form_data.get("url")

    if url is None:
        request.session["convert_error"] = "Не вдалося знайти URL або індекс для конвертації."
        return RedirectResponse(url="/", status_code=303)

    pdf_content, filename, error = await generate_pdf_for_download(url)

    if error:
        request.session["convert_error"] = error
        return RedirectResponse(url="/", status_code=303)

    if user:
        try:
            await add_to_history(db, user, url, "text")
        except Exception as e:
            print(f"ПОМИЛКА (convert history): {e}")

    return StreamingResponse(
        io.BytesIO(pdf_content),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.post("/fetch-sizes")
# 1. ДОДАЙТЕ db: AsyncSession
async def fetch_sizes(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Примусово оновлює розміри для ВСІХ елементів у сесії,
    використовуючи asyncio.gather для паралельної обробки.
    """
    optimization_list = request.session.get("optimization_list", [])
    if not optimization_list:
        return RedirectResponse(url="/optimization-list", status_code=303)

    print(f"Отримання розмірів для {len(optimization_list)} елементів (паралельно)...")

    tasks = [update_item_size(item, db) for item in optimization_list]
    updated_list = await asyncio.gather(*tasks)

    print("Отримання розмірів завершено.")
    request.session["optimization_list"] = updated_list

    return RedirectResponse(url="/optimization-list", status_code=303)