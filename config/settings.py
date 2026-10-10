# ❌ ACTUEL: Config dans plein de fichiers
# - telegram_code.py: TOKEN, BOT_USERNAME
# - API_SmartCorp.py: API_KEY, API_URL
# - ordermanager.py: Différentes constantes
# - chat.ini: Hyperparamètres du modèle

# ✅ SOLUTION: Config centralisée

# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    BOT_USERNAME = '@SmartCorpBot'

    # API
    API_URL = 'https://scdakar.mondjago.com/api/product-store/1'
    API_KEY = os.getenv('API_KEY')
    API_TIMEOUT = 30

    # Cache
    CACHE_MAX_SIZE = 1000
    CACHE_TTL = 600

    # Model
    MODEL_PATH = 'best_model_tfidf.pth'
    MODEL_HIDDEN_SIZE = 60
    MODEL_NUM_LAYERS = 1

    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')

    # Logging
    LOG_LEVEL = 'INFO'
    LOG_FILE = 'bot.log'

