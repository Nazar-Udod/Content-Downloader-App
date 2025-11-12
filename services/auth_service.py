from fastapi import Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import User
from schemas import UserCreate
from database import get_db

# Налаштовуємо bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Перевіряє, чи збігається пароль з хешем."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Створює хеш пароля."""
    return pwd_context.hash(password)

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Знаходить користувача за email."""
    result = await db.execute(select(User).where(User.Email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, user: UserCreate) -> User:
    """Створює нового користувача в БД."""
    hashed_password = get_password_hash(user.password)
    db_user = User(Email=user.email, PasswordHash=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def get_current_user(
        request: Request,
        db: AsyncSession = Depends(get_db)
) -> User | None:
    """
    Залежність: Отримує email з сесії та повертає об'єкт User з БД.
    Якщо користувача немає, повертає None.
    """
    email = request.session.get("user_email")
    if not email:
        return None

    user = await get_user_by_email(db, email)
    return user

async def get_required_user(user: User | None = Depends(get_current_user)) -> User:
    """
    Залежність: Вимагає, щоб користувач був залогінений.
    Якщо ні - перенаправляє на сторінку /login.
    """
    if not user:
        # 307 - Temporary Redirect, каже браузеру повторити той самий POST/GET запит
        # на нову адресу (тобто на /login)
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return user