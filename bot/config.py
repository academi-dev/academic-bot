"""
Módulo de configuración para Academic Bot.

Carga y valida variables de entorno para la conexión con Telegram,
academic-api y academic-rag.
"""

import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

# Cargar variables de entorno desde archivo .env si existe
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Configuración inmutable de la aplicación obtenida desde variables de entorno."""

    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
    RAG_BASE_URL: str = os.getenv("RAG_BASE_URL", "http://localhost:8001/api/v1").rstrip("/")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "30.0"))

    def validate(self) -> None:
        """
        Valida que las variables de entorno críticas estén presentes.
        
        Lanza ValueError si falta alguna configuración indispensable.
        """
        if not self.TELEGRAM_BOT_TOKEN or self.TELEGRAM_BOT_TOKEN == "your-bot-token":
            raise ValueError(
                "La variable de entorno TELEGRAM_BOT_TOKEN no está configurada. "
                "Define un token válido en el archivo .env o en el entorno."
            )


# Instancia singleton de configuración
settings = Settings()


def setup_logging() -> None:
    """Configura el formato estándar de logging para el bot."""
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=log_level
    )
    # Reducir ruido de librerías externas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)
