"""
Database connection and session management for LQOA
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import os
from contextlib import contextmanager
from typing import Generator

from .models import Base

def get_database_url() -> str:
    """Get database URL from environment variables"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        # Default to SQLite for local development
        database_url = "sqlite:///./lqoa.db"
    
    # Handle Render's postgres:// URLs (need to convert to postgresql://)
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    return database_url

def create_database_engine():
    """Create and configure database engine"""
    database_url = get_database_url()
    
    # Engine configuration
    if database_url.startswith("sqlite"):
        # SQLite configuration
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=os.getenv("DB_ECHO", "false").lower() == "true"
        )
    else:
        # PostgreSQL configuration
        engine = create_engine(
            database_url,
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300
        )
    
    return engine

# Create engine and session factory
engine = create_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_tables():
    """Create all database tables"""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """Drop all database tables - use with caution!"""
    Base.metadata.drop_all(bind=engine)

@contextmanager
def get_database_session() -> Generator[Session, None, None]:
    """Get database session with automatic cleanup"""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session"""
    with get_database_session() as session:
        yield session