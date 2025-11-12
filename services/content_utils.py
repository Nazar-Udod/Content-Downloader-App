import io
import hashlib
import requests
import yt_dlp
from pathlib import Path
from playwright.async_api import Error as PlaywrightError
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import Material

# Локальні імпорти
from config import (
    ESTIMATED_PDF_MB, ESTIMATED_SPOTIFY_MB, ESTIMATED_VIDEO_MB,
    ESTIMATED_AUDIO_MB, PDF_CACHE_DIR
)
from services.browser_manager import get_browser


def get_external_content_size_mb(link: str, content_type: str) -> (float, bool):
    """
    Отримує розмір для ЗОВНІШНІХ ресурсів (не для 'text').
    (Код функції повністю скопійовано з вашого файлу)
    """
    try:
        if content_type in ['pdf', 'doc', 'ppt']:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
            response = requests.head(link, allow_redirects=True, timeout=5, headers=headers)

            if response.status_code == 200:
                content_length = response.headers.get('Content-Length')
                if content_length:
                    return round(int(content_length) / (1024 * 1024), 2), False
            return ESTIMATED_PDF_MB, True


        elif content_type == 'video':
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                formats = info.get('formats', [])
                video_size = 0
                audio_size = 0

                video_streams = [
                    f for f in formats
                    if f.get('vcodec') != 'none' and f.get('acodec') == 'none' and (
                            f.get('filesize') or f.get('filesize_approx'))
                ]
                if video_streams:
                    best_video_stream = max(video_streams, key=lambda f: f.get('height', 0))
                    video_size = best_video_stream.get('filesize') or best_video_stream.get('filesize_approx')

                audio_streams = [
                    f for f in formats
                    if f.get('acodec') != 'none' and f.get('vcodec') == 'none' and (
                            f.get('filesize') or f.get('filesize_approx'))
                ]
                if audio_streams:
                    best_audio_stream = max(audio_streams, key=lambda f: f.get('abr', 0))
                    audio_size = best_audio_stream.get('filesize') or best_audio_stream.get('filesize_approx')

                if video_size > 0 and audio_size > 0:
                    total_size_bytes = video_size + audio_size
                    return round(total_size_bytes / (1024 * 1024), 2), False

                progressive_streams = [
                    f for f in formats
                    if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and (
                            f.get('filesize') or f.get('filesize_approx'))
                ]
                if progressive_streams:
                    best_prog_stream = max(progressive_streams, key=lambda f: f.get('height', 0))
                    prog_size = best_prog_stream.get('filesize') or best_prog_stream.get('filesize_approx')
                    if prog_size:
                        return round(prog_size / (1024 * 1024), 2), False
            return ESTIMATED_VIDEO_MB, True

        elif content_type == 'audio_yt_music':
            ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=False)
                filesize = info.get('filesize') or info.get('filesize_approx')
                if filesize:
                    return round(filesize / (1024 * 1024), 2), False
            return ESTIMATED_AUDIO_MB, True

    except Exception as e:
        print(f"Помилка отримання зовнішнього розміру для {link}: {e}")
        if content_type == 'video':
            return ESTIMATED_VIDEO_MB, True
        elif content_type == 'audio_yt_music':
            return ESTIMATED_AUDIO_MB, True
        else:
            return ESTIMATED_PDF_MB, True
    return 0.0, True


async def update_item_size(item: dict, db: AsyncSession) -> dict:
    """
    Оновлює розмір для одного елемента, генеруючи PDF-кеш, якщо потрібно.
    """
    updated_item = item.copy()
    size_mb = None
    is_estimated = False
    cache_file = updated_item.get('cache_file')
    browser_instance = get_browser()  # Отримуємо браузер з менеджера

    try:
        if updated_item['type'] == 'text':
            if not cache_file:
                url_hash = hashlib.md5(updated_item['link'].encode()).hexdigest()
                cache_file = f"{url_hash}.pdf"

            cache_path = PDF_CACHE_DIR / cache_file
            updated_item['cache_file'] = cache_file

            if not cache_path.exists():
                if browser_instance is None:
                    raise Exception("Браузер Playwright не запущено. Пропуск генерації PDF.")

                print(f"Генерація PDF (Playwright) для: {updated_item['link']}...")
                page = None
                try:
                    page = await browser_instance.new_page()
                    await page.goto(updated_item['link'], timeout=15000, wait_until='domcontentloaded')
                    await page.pdf(path=str(cache_path))
                    print(f"Збережено в: {cache_path}")
                except PlaywrightError as e:
                    print(f"!!! ПОМИЛКА (Playwright) для {updated_item['link']}: {e.message.splitlines()[0]}")
                    updated_item['cache_file'] = None
                    size_mb = ESTIMATED_PDF_MB
                    is_estimated = True
                finally:
                    if page:
                        await page.close()

            if cache_path.exists():
                size_bytes = cache_path.stat().st_size
                size_mb = round(size_bytes / (1024 * 1024), 2)
                is_estimated = False
            elif updated_item['cache_file'] is None:
                pass  # Помилка вже оброблена
            else:
                raise Exception(f"Файл кешу {cache_path} не знайдено, хоча помилки Playwright не було.")

        elif updated_item['type'] == 'audio_spotify':
            size_mb = ESTIMATED_SPOTIFY_MB
            is_estimated = True

        else:
            # Для всіх інших типів (video, audio_yt, pdf, doc...)
            size_mb, is_estimated = get_external_content_size_mb(updated_item['link'], updated_item['type'])

    except Exception as e:
        print(f"ПОМИЛКА (update_item_size) для {updated_item['link']}: {e}")
        if updated_item['type'] == 'video':
            size_mb = ESTIMATED_VIDEO_MB
        elif updated_item['type'] in ['audio_yt_music', 'audio_spotify']:
            size_mb = ESTIMATED_AUDIO_MB
        else:
            size_mb = ESTIMATED_PDF_MB
        is_estimated = True
        updated_item['cache_file'] = None

    updated_item['size_mb'] = size_mb
    updated_item['is_estimated'] = is_estimated

    if not is_estimated and size_mb is not None and updated_item.get('link'):
        try:
            result = await db.execute(
                select(Material).where(Material.URL == updated_item['link'])
            )
            material = result.scalars().first()

            # Оновлюємо, тільки якщо матеріал існує і розмір ще не встановлено
            if material and material.Size is None:
                material.Size = int(size_mb * 1024 * 1024)  # Конвертуємо MB в байти
                await db.commit()
                print(f"Оновлено розмір в БД (в байтах): {material.URL}")
        except Exception as e:
            print(f"ПОМИЛKA (оновлення розміру в БД): {e}")
            await db.rollback()

    return updated_item


async def generate_pdf_for_download(url: str) -> (bytes, str, str | None):
    """
    Генерує PDF для негайного завантаження.
    Повертає (pdf_content, filename, error_message)
    """
    browser_instance = get_browser()
    if browser_instance is None:
        return None, None, "Сервіс генерації PDF не запущено (Playwright)."

    page = None
    try:
        page = await browser_instance.new_page()
        await page.goto(url, timeout=15000, wait_until='domcontentloaded')

        pdf_content = await page.pdf()

        parsed_url = urlparse(url)
        filename = f"{parsed_url.netloc.replace('.', '_')}.pdf"

        return pdf_content, filename, None

    except PlaywrightError as e:
        error_message = e.message.splitlines()[0]
        print(f"ПОМИЛКА (Playwright) /convert для {url}: {error_message}")
        return None, None, f"Не вдалося згенерувати PDF (Playwright): {error_message}"
    except Exception as e:
        print(f"ЗАГАЛЬНА ПОМИЛКА /convert для {url}: {e}")
        return None, None, f"Загальна помилка сервера: {e}"
    finally:
        if page:
            await page.close()