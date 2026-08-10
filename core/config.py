import os
from dotenv import load_dotenv

load_dotenv()


def validate_required_credentials():
    api_id = os.getenv("API_ID", "")
    api_hash = os.getenv("API_HASH", "")
    bot_token = os.getenv("BOT_TOKEN", "")

    if not api_id or not api_hash or not bot_token:
        raise ValueError(
            "Faltan credenciales de Telegram. Define API_ID, API_HASH y BOT_TOKEN en el archivo .env o el entorno."
        )

    return {
        "API_ID": int(api_id),
        "API_HASH": api_hash,
        "BOT_TOKEN": bot_token,
    }


class Config:
    # CREDENCIALES DE TELEGRAM (Obtenidas de @BotFather)
    credentials = validate_required_credentials() if os.getenv("API_ID") or os.getenv("API_HASH") or os.getenv("BOT_TOKEN") else {}
    API_ID = int(credentials.get("API_ID", 0))
    API_HASH = credentials.get("API_HASH", "")
    BOT_TOKEN = credentials.get("BOT_TOKEN", "")

    # ID del dueño del bot
    OWNER_ID = int(os.getenv("OWNER_ID", 0))

    # Configuraciones de descarga
    DOWNLOAD_DIR = "downloads"
    COOKIES_FILE = "cookies.txt"

    # Límites (Opcional para escalar)
    MAX_SIMULTANEOUS_DOWNLOADS = 30