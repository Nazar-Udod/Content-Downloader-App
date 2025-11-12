from playwright.async_api import async_playwright, Browser, Playwright

# --- Глобальні змінні Playwright ---
_playwright_context: Playwright | None = None
_browser_instance: Browser | None = None


async def start_browser():
    """
    Запускає Playwright та браузер Chromium.
    Викликається при старті FastAPI.
    """
    global _playwright_context, _browser_instance

    print("Запуск Playwright...")
    try:
        _playwright_context = await async_playwright().start()
        # Ми запускаємо лише chromium, оскільки він найкраще підходить для PDF
        _browser_instance = await _playwright_context.chromium.launch()
        print("Браузер Chromium (Playwright) успішно запущено.")
    except Exception as e:
        print(f"!!! ПОМИЛКА ЗАПУСКУ PLAYWRIGHT !!!")
        print(f"PDF-генерація не працюватиме.")
        print(f"Переконайтеся, що ви виконали: 'pip install playwright' та 'python -m playwright install chromium'")
        print(f"Деталі помилки: {e}")
        _browser_instance = None


async def stop_browser():
    """
    Зупиняє браузер та Playwright.
    Викликається при зупинці FastAPI.
    """
    global _playwright_context, _browser_instance
    if _browser_instance:
        await _browser_instance.close()
        print("Браузер Chromium (Playwright) закрито.")
    if _playwright_context:
        await _playwright_context.stop()
        print("Playwright зупинено.")


def get_browser() -> Browser | None:
    """
    Надає доступ до глобального екземпляра браузера.
    """
    return _browser_instance