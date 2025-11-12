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