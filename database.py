import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from config import DATABASE_URL

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не встановлено в .env або config.py")

# Використовуємо aioodbc для SQL Server
engine = create_async_engine(DATABASE_URL)

# Створюємо фабрику асинхронних сесій
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

# Базовий клас для наших моделей
Base = declarative_base()

async def get_db() -> AsyncSession:
    """
    Залежність (Dependency) FastAPI для отримання сесії БД.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()