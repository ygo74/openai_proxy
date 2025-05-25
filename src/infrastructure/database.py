from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.core.models.models import Base, Model
from src.core.application.config import AppConfig
import logging
from datetime import datetime
from typing import Dict, Any

SessionLocal = None
logger = logging.getLogger(__name__)

def init_db(config: AppConfig) -> None:
    logger.debug("Initializing database with config: %s", config)
    global SessionLocal
    db_type: str = config.db_type
    if db_type == "sqlite":
        logger.debug("Using SQLite database.")
        engine = create_engine("sqlite:///./models.db")
    elif db_type == "postgres":
        logger.debug("Using PostgreSQL database.")
        raise NotImplementedError("PostgreSQL support is not implemented yet.")
    else:
        logger.error("Unsupported database type: %s", db_type)
        raise ValueError(f"Unsupported database type: {db_type}")

    try:
        logger.debug("Creating tables...")
        Base.metadata.create_all(bind=engine)
        logger.debug("Tables created successfully.")
    except Exception as e:
        logger.error("Error creating tables: %s", e)
        raise

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.debug("Database initialized successfully.")

def save_or_update_model(session: Session, model_data: Dict[str, Any]) -> None:
    technical_name = f"{model_data['provider']}_{model_data['name']}"
    existing_model = session.query(Model).filter_by(technical_name=technical_name).first()
    if existing_model:
        existing_model.url = model_data["url"]
        existing_model.updated = datetime.utcnow()
        existing_model.capabilities = model_data.get("capabilities", {})
    else:
        new_model = Model(
            url=model_data["url"],
            name=model_data["name"],
            technical_name=technical_name,
            capabilities = model_data.get("capabilities", {})
        )
        session.add(new_model)
    session.commit()

# Dependency to get a database session
def get_db():
    if SessionLocal is None:
        raise RuntimeError("SessionLocal is not initialized. Ensure init_db() is called before using the database.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()