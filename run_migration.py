"""Run database migrations - creates any missing tables."""
from app.repositories.implementations.sqlalchemy_models import Base
from sqlalchemy import create_engine
import os

db_url = os.environ.get(
    "DATABASE_URL",
    "postgresql://voice_auth:voice_auth_pass@postgres:5432/voice_auth"
)
engine = create_engine(db_url)
Base.metadata.create_all(engine)
print("Migration complete - all tables up to date")
