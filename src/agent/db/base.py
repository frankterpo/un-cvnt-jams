"""Database configuration and session management."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import DateTime, MetaData, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

# Load environment variables
load_dotenv()

class Base(DeclarativeBase):
    """Shared base for all models."""
    
    metadata = MetaData()

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        onupdate=func.now(), 
        nullable=False
    )

# Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///social_agent.db")

# Detect engine type to configure optimized settings
is_postgres = DATABASE_URL.startswith("postgresql")

connect_args = {}
engine_kwargs = {
    "echo": False,
    "future": True,
}

if is_postgres:
    # Production PostgreSQL Settings
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
        "pool_pre_ping": True,
    })
    
    ssl_mode = os.getenv("DB_SSL_MODE", "prefer") # 'require' for strict RDS
    if ssl_mode:
        connect_args["sslmode"] = ssl_mode
        engine_kwargs["connect_args"] = connect_args
else:
    # SQLite Settings for Dev
    connect_args["check_same_thread"] = False
    engine_kwargs["connect_args"] = connect_args

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
