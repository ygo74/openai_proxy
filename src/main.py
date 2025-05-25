from fastapi import FastAPI
from src.api.v1 import router_v1
from src.core.application.config import load_config
from src.core.models.configuration import AppConfig
from src.infrastructure.database import init_db
import logging


app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.get("/")
def read_root():
    logger.debug("Handling request to root endpoint.")
    return {"message": "Welcome to the OpenAI Proxy!"}

# Set up the application
def setup_application():
    logger.debug("Setting up the application.")
    # Load configuration
    AppConfig = load_config()
    # Init database connections
    init_db(AppConfig)

setup_application()
logger.debug("Application setup complete.")


# Include the router in the main app
app.include_router(router_v1)