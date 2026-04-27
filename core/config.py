import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # CREDENCIALES DE TELEGRAM (Obtenidas de @BotFather)
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")

    # ID del dueño del bot
    OWNER_ID = int(os.getenv("OWNER_ID", 0))

    # Configuraciones de descarga
    DOWNLOAD_DIR = "downloads"
    COOKIES_FILE = "cookies.txt"
    
    # Límites (Opcional para escalar)
    MAX_SIMULTANEOUS_DOWNLOADS = 30