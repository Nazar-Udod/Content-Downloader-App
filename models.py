from sqlalchemy import Column, Integer, String, NVARCHAR, DateTime, ForeignKey, BIGINT, Identity
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "Users"
    UserID = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    Email = Column(NVARCHAR(255), nullable=False, unique=True)
    PasswordHash = Column(NVARCHAR(256), nullable=False)
    RegistrationDate = Column(DateTime, nullable=False, server_default=func.now())

    # Зв'язки
    folders = relationship("BookmarkFolder", back_populates="user", cascade="all, delete")
    history = relationship("HistoryMaterial", back_populates="user", cascade="all, delete")


class Material(Base):
    __tablename__ = "Materials"
    MaterialID = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    URL = Column(NVARCHAR(2048), nullable=False, unique=True)
    Type = Column(NVARCHAR(50), nullable=False)
    Size = Column(BIGINT, nullable=True)


class BookmarkFolder(Base):
    __tablename__ = "BookmarkFolders"
    FolderID = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    UserID = Column(Integer, ForeignKey("Users.UserID", ondelete="CASCADE"), nullable=False)
    Name = Column(NVARCHAR(255), nullable=False)
    CreationDate = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="folders")
    bookmarks = relationship("Bookmark", back_populates="folder", cascade="all, delete")


class Bookmark(Base):
    __tablename__ = "Bookmarks"
    BookmarkID = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    FolderID = Column(Integer, ForeignKey("BookmarkFolders.FolderID", ondelete="CASCADE"), nullable=False)
    MaterialID = Column(Integer, ForeignKey("Materials.MaterialID"), nullable=False)
    Name = Column(NVARCHAR(255), nullable=False)
    CreationDate = Column(DateTime, nullable=False, server_default=func.now())

    folder = relationship("BookmarkFolder", back_populates="bookmarks")
    material = relationship("Material")  # Зв'язок в один бік


class HistoryMaterial(Base):
    __tablename__ = "HistoryMaterials"
    HistoryID = Column(Integer, Identity(start=1, increment=1), primary_key=True)
    UserID = Column(Integer, ForeignKey("Users.UserID", ondelete="CASCADE"), nullable=False)
    MaterialID = Column(Integer, ForeignKey("Materials.MaterialID"), nullable=False)
    LoadDate = Column(DateTime, nullable=False, server_default=func.now())

    user = relationship("User", back_populates="history")
    material = relationship("Material")  # Зв'язок в один бік