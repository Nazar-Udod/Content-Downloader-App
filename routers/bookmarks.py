from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config import templates
from database import get_db
from models import User, BookmarkFolder, Bookmark
from services.auth_service import get_required_user
from services import bookmark_service as service

router = APIRouter(
    prefix="/bookmarks",
    tags=["Закладки"],
    # Усі ендпоінти в цьому файлі будуть вимагати логін
    dependencies=[Depends(get_required_user)]
)


@router.get("/", response_class=HTMLResponse)
async def get_bookmarks_page(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Відображає сторінку керування закладками.
    """
    folders = await service.get_user_folders_with_bookmarks(db, user)

    # Отримуємо дані для хедера з сесії
    optimization_list = request.session.get("optimization_list", [])

    return templates.TemplateResponse("bookmarks.html", {
        "request": request,
        "folders": folders,
        "user_email": user.Email,  # Передаємо email для хедера
        "optimization_count": len(optimization_list)  # Для хедера
    })


@router.post("/add")
async def add_bookmark(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Обробляє додавання нової закладки з головної форми пошуку.
    """
    form_data = await request.form()

    index = form_data.get("bookmark_index")
    if index is None:
        return RedirectResponse(url="/", status_code=303)

    url = form_data.get(f"url_{index}")
    name = form_data.get(f"name_{index}")
    type_str = form_data.get(f"type_{index}")
    folder_id_str = form_data.get(f"folder_id_{index}")

    if not all([url, name, type_str, folder_id_str]):
        return RedirectResponse(url="/", status_code=303)

    try:
        folder_id = int(folder_id_str)
    except ValueError:
        return RedirectResponse(url="/", status_code=303)

    folder = await service.check_folder_owner(db, user, folder_id)
    if not folder:
        return RedirectResponse(url="/", status_code=303)

    material = await service.get_or_create_material(db, url, type_str)
    await service.create_bookmark(db, folder.FolderID, material.MaterialID, name)

    return RedirectResponse(url="/", status_code=303)


@router.post("/folder/create")
async def create_folder(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db),
        name: str = Form(...)
):
    """
    Створює нову папку закладок.
    """
    if name:
        new_folder = BookmarkFolder(UserID=user.UserID, Name=name)
        db.add(new_folder)
        await db.commit()

    return RedirectResponse("/bookmarks", status_code=303)


@router.post("/folder/delete")
async def delete_folder(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db),
        folder_id: int = Form(...)
):
    """
    Видаляє папку (якщо це не стандартна).
    """
    folder = await service.check_folder_owner(db, user, folder_id)
    if folder and folder.Name != service.DEFAULT_FOLDER_NAME:
        await db.delete(folder)
        await db.commit()

    return RedirectResponse("/bookmarks", status_code=303)


@router.post("/folder/rename")
async def rename_folder(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db),
        folder_id: int = Form(...),
        new_name: str = Form(...)
):
    """
    Перейменовує папку.
    """
    folder = await service.check_folder_owner(db, user, folder_id)
    if folder and new_name:
        folder.Name = new_name
        await db.commit()

    return RedirectResponse("/bookmarks", status_code=303)


@router.post("/delete")
async def delete_bookmark(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db),
        bookmark_id: int = Form(...)
):
    """
    Видаляє окрему закладку.
    """
    bookmark = await service.check_bookmark_owner(db, user, bookmark_id)
    if bookmark:
        await db.delete(bookmark)
        await db.commit()

    return RedirectResponse("/bookmarks", status_code=303)


@router.post("/move")
async def move_bookmark(
        request: Request,
        user: User = Depends(get_required_user),
        db: AsyncSession = Depends(get_db),
        bookmark_id: int = Form(...),
        new_folder_id: int = Form(...)
):
    """
    Переміщує закладку в іншу папку.
    """
    bookmark = await service.check_bookmark_owner(db, user, bookmark_id)
    new_folder = await service.check_folder_owner(db, user, new_folder_id)

    if bookmark and new_folder:
        bookmark.FolderID = new_folder.FolderID
        await db.commit()

    return RedirectResponse("/bookmarks", status_code=303)