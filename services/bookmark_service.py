from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from models import User, Material, BookmarkFolder, Bookmark

# Назва стандартної папки
DEFAULT_FOLDER_NAME = "Мої закладки"


async def create_default_folder(db: AsyncSession, user: User):
    """
    Створює стандартну папку "Мої закладки" для нового користувача.
    """
    default_folder = BookmarkFolder(UserID=user.UserID, Name=DEFAULT_FOLDER_NAME)
    db.add(default_folder)
    await db.commit()


async def get_user_folders(db: AsyncSession, user: User) -> list[BookmarkFolder]:
    """
    Отримує список усіх папок закладок для користувача.
    """
    result = await db.execute(
        select(BookmarkFolder)
        .where(BookmarkFolder.UserID == user.UserID)
        .order_by(BookmarkFolder.Name)
    )
    return result.scalars().all()


async def get_user_folders_with_bookmarks(db: AsyncSession, user: User) -> list[BookmarkFolder]:
    """
    Отримує список папок, одразу підвантажуючи пов'язані з ними
    закладки та матеріали.
    """
    result = await db.execute(
        select(BookmarkFolder)
        .where(BookmarkFolder.UserID == user.UserID)
        .options(
            selectinload(BookmarkFolder.bookmarks)
            .selectinload(Bookmark.material)
        )
        .order_by(BookmarkFolder.Name)
    )
    # unique() потрібен, щоб уникнути дублікатів папок через JOIN
    return result.scalars().unique().all()


async def get_or_create_material(db: AsyncSession, url: str, type: str) -> Material:
    """
    Знаходить матеріал за URL. Якщо його немає в БД, створює новий.
    """
    result = await db.execute(
        select(Material).where(Material.URL == url)
    )
    material = result.scalars().first()

    if not material:
        print(f"Створення нового матеріалу: {url}")
        material = Material(URL=url, Type=type, Size=None)  # Розмір буде отримано пізніше
        db.add(material)
        await db.commit()
        await db.refresh(material)

    return material


async def create_bookmark(db: AsyncSession, folder_id: int, material_id: int, name: str):
    """
    Створює сам запис закладки, що пов'язує папку і матеріал.
    """
    new_bookmark = Bookmark(
        FolderID=folder_id,
        MaterialID=material_id,
        Name=name  # Власна назва, яку дав користувач
    )
    db.add(new_bookmark)
    await db.commit()


async def check_bookmark_owner(db: AsyncSession, user: User, bookmark_id: int) -> Bookmark | None:
    """
    Перевіряє, чи належить закладка користувачу, і повертає її.
    """
    result = await db.execute(
        select(Bookmark)
        .join(BookmarkFolder)
        .where(
            Bookmark.BookmarkID == bookmark_id,
            BookmarkFolder.UserID == user.UserID
        )
    )
    return result.scalars().first()


async def check_folder_owner(db: AsyncSession, user: User, folder_id: int) -> BookmarkFolder | None:
    """
    Перевіряє, чи належить папка користувачу, і повертає її.
    """
    result = await db.execute(
        select(BookmarkFolder)
        .where(
            BookmarkFolder.FolderID == folder_id,
            BookmarkFolder.UserID == user.UserID
        )
    )
    return result.scalars().first()