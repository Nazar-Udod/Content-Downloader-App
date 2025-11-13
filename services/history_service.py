from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from models import User, Material, HistoryMaterial
from services.bookmark_service import get_or_create_material


async def add_to_history(db: AsyncSession, user: User, url: str, type_str: str):
    """
    Додає матеріал до історії користувача.
    Створює матеріал, якщо він не існує, і записує подію завантаження.
    """
    # 1. Знаходимо або створюємо матеріал
    material = await get_or_create_material(db, url, type_str)

    # 2. Створюємо запис в історії
    # Ми не перевіряємо наявність, а просто додаємо новий запис
    # кожного разу, щоб фіксувати кожну взаємодію.
    history_entry = HistoryMaterial(
        UserID=user.UserID,
        MaterialID=material.MaterialID
    )
    db.add(history_entry)
    await db.commit()
    print(f"Додано до історії [User: {user.UserID}]: {url}")


async def get_user_history(db: AsyncSession, user: User) -> list[HistoryMaterial]:
    """
    Отримує всю історію завантажень для користувача.
    """
    result = await db.execute(
        select(HistoryMaterial)
        .where(HistoryMaterial.UserID == user.UserID)
        .options(
            selectinload(HistoryMaterial.material)
        )
        .order_by(HistoryMaterial.LoadDate.desc())  # Новіші спочатку
    )
    return result.scalars().all()


async def check_history_owner(db: AsyncSession, user: User, history_id: int) -> HistoryMaterial | None:
    """
    Перевіряє, чи належить запис історії користувачу, і повертає його.
    """
    result = await db.execute(
        select(HistoryMaterial)
        .where(
            HistoryMaterial.HistoryID == history_id,
            HistoryMaterial.UserID == user.UserID
        )
    )
    return result.scalars().first()


async def delete_history_item(db: AsyncSession, user: User, history_id: int):
    """
    Видаляє один запис з історії користувача.
    """
    item_to_delete = await check_history_owner(db, user, history_id)

    if item_to_delete:
        await db.delete(item_to_delete)
        await db.commit()
        print(f"Видалено запис історії {history_id} для користувача {user.UserID}")
    else:
        print(f"Помилка видалення: Запис історії {history_id} не знайдено або немає доступу.")