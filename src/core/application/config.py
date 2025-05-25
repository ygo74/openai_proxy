import json
from src.core.models.configuration import AppConfig



def load_config() -> AppConfig:
    with open("config.json", "r") as config_file:
        config_data = json.load(config_file)
        return AppConfig(**config_data)