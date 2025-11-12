from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import templates
from database import get_db
from models import User
from services.auth_service import get_required_user, get_current_user
from services import history_service

router = APIRouter(
    prefix="/history",
    tags=["Історія"]
)


@router.get("/", response_class=HTMLResponse)
async def get_history_page(
        request: Request,
        user: User = Depends(get_required_user),  # Ця сторінка захищена
        db: AsyncSession = Depends(get_db)
):
    """
    Відображає сторінку історії користувача.
    """
    history_items = await history_service.get_user_history(db, user)
    optimization_list = request.session.get("optimization_list", [])

    return templates.TemplateResponse("history.html", {
        "request": request,
        "history_items": history_items,
        "user_email": user.Email,
        "optimization_count": len(optimization_list)
    })


@router.post("/track-click")
async def track_click_and_redirect(
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: User | None = Depends(get_current_user),  # Необов'язковий користувач
        url: str = Form(...),
        type: str = Form(...)
):
    """
    Реєструє клік (додає до історії), якщо користувач залогінений,
    і одразу перенаправляє користувача на цільовий URL.
    """
    if user:
        try:
            await history_service.add_to_history(db, user, url, type)
        except Exception as e:
            print(f"ПОМИЛКА (track-click history): {e}")
            # Не перериваємо користувача, просто логуємо

    # Завжди перенаправляємо користувача на URL, який він хотів
    return RedirectResponse(url=url, status_code=303)