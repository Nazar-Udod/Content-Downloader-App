from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models import User
from schemas import UserCreate

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