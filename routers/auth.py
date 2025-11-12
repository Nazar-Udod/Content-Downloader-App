from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import templates
from database import get_db
from schemas import UserCreate, UserLogin
from services.auth_service import get_user_by_email, create_user, verify_password

router = APIRouter(tags=["Автентифікація"])


# --- GET (Відображення сторінок) ---

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Відображає сторінку входу."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Відображає сторінку реєстрації."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/logout")
async def logout(request: Request):
    """Видаляє користувача з сесії."""
    request.session.pop("user_email", None)
    return RedirectResponse(url="/", status_code=303)


# --- POST (Обробка форм) ---

@router.post("/login")
async def login_submit(request: Request, db: AsyncSession = Depends(get_db)):
    """Обробляє дані форми входу."""
    form_data = await request.form()
    user_data = UserLogin(email=form_data.get("email"), password=form_data.get("password"))

    error = None
    user = await get_user_by_email(db, user_data.email)

    if not user or not verify_password(user_data.password, user.PasswordHash):
        error = "Неправильний email або пароль"
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": error,
            "email": user_data.email
        }, status_code=401)

    # Зберігаємо email в сесії
    request.session["user_email"] = user.Email

    return RedirectResponse(url="/", status_code=303)


@router.post("/register")
async def register_submit(request: Request, db: AsyncSession = Depends(get_db)):
    """Обробляє дані форми реєстрації."""
    form_data = await request.form()

    if form_data.get("password") != form_data.get("password_confirm"):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Паролі не збігаються",
            "email": form_data.get("email")
        }, status_code=400)

    user_data = UserCreate(email=form_data.get("email"), password=form_data.get("password"))

    existing_user = await get_user_by_email(db, user_data.email)
    if existing_user:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Користувач з таким email вже існує",
            "email": user_data.email
        }, status_code=409)

    user = await create_user(db, user_data)

    # Автоматично логінимо користувача
    request.session["user_email"] = user.Email

    return RedirectResponse(url="/", status_code=303)