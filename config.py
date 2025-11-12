import os
from pathlib import Path
from dotenv import load_dotenv
from fastapi.templating import Jinja2Templates

# Завантажуємо змінні з .env файлу
load_dotenv()

# --- Налаштування API та Секретів ---
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
APP_SECRET_KEY = os.getenv("APP_SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

if not APP_SECRET_KEY:
    print("ПОПЕРЕДЖЕННЯ: APP_SECRET_KEY не встановлено. Сесії не будуть безпечними.")
    APP_SECRET_KEY = "temp_dev_key_please_replace"

if not DATABASE_URL:
     print("ПОПЕРЕДЖЕННЯ: DATABASE_URL не встановлено. Додаток не зможе підключитись до БД.")

# --- Налаштування Шаблонів ---
templates = Jinja2Templates(directory="templates")

# --- Налаштування Кешу ---
PDF_CACHE_DIR = Path("pdf_cache")

# --- Оцінки розмірів ---
ESTIMATED_PDF_MB = 2.0
ESTIMATED_SPOTIFY_MB = 5.0
ESTIMATED_VIDEO_MB = 150.0
ESTIMATED_AUDIO_MB = 5.0