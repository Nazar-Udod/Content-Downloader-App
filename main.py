from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

# Локальні імпорти
from config import APP_SECRET_KEY, PDF_CACHE_DIR
from services.browser_manager import start_browser, stop_browser
from routers import pages, search, content, optimize
from routers import auth
from routers import bookmarks
from database import Base, engine
from routers import history

# --- Створення FastAPI ---
app = FastAPI(
    title="Web Content Downloader API",
    description="Система для пошуку та завантаження контенту з мережі.",
    version="0.1.0"
)

# --- Middleware ---
app.add_middleware(
    SessionMiddleware,
    secret_key=APP_SECRET_KEY,
    https_only=False,  # Встановіть True для production
    max_age=86400 * 14  # 2 тижні
)


# --- Події життєвого циклу ---

@app.on_event("startup")


async def on_startup():
    """
    При старті сервера:
    1. Створюємо папку кешу.
    2. Запускаємо Playwright/браузер.
    3. Створюємо таблиці в БД (якщо їх немає).
    """
    # 3. Створення таблиць
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Таблиці бази даних перевірено/створено.")

    # 1. Папка кешу
    PDF_CACHE_DIR.mkdir(exist_ok=True)
    print(f"Папка кешу PDF знаходиться тут: {PDF_CACHE_DIR.resolve()}")

    # 2. Браузер
    await start_browser()


@app.on_event("shutdown")
async def on_shutdown():
    """
    Закриваємо Playwright при зупинці сервера.
    """
    await stop_browser()

# Монтуємо папку "Static"
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Підключення Роутерів ---
app.include_router(auth.router, tags=["Автентифікація"])
app.include_router(bookmarks.router, tags=["Закладки"])
app.include_router(history.router, tags=["Історія"])
app.include_router(pages.router, tags=["Основні Сторінки"])
app.include_router(search.router, tags=["Пошук"])
app.include_router(content.router, tags=["Керування Контентом"])
app.include_router(optimize.router, tags=["Оптимізація"])


@app.get("/api/health")
def health_check():
    return {"status": "ok"}