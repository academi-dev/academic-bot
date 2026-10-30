"""
Punto de entrada principal para Academic Bot.

Construye la aplicación de Telegram utilizando ApplicationBuilder, registra
manejadores, inicializa la cola de trabajos y arranca el ciclo de polling.
"""

import html
import json
import logging
import sys
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from bot.config import settings, setup_logging
from bot.handlers import register_all_handlers

logger = logging.getLogger("academic_bot.main")


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador global de errores no capturados en los handlers.
    
    Registra el trace del error en los logs y notifica amistosamente al usuario.
    """
    logger.error("Excepción no controlada mientras se procesaba una actualización:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        mensaje_usuario = (
            "⚠️ *Ocurrió un error inesperado al procesar tu solicitud.*\n"
            "El equipo técnico ha sido notificado. Por favor, intenta de nuevo en un momento."
        )
        try:
            await update.effective_message.reply_text(
                mensaje_usuario,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as send_err:
            logger.error("No se pudo enviar mensaje de error al usuario: %s", send_err)


def build_application() -> Application:
    """
    Crea y configura la instancia de Application de python-telegram-bot.

    Returns:
        Instancia lista para ejecutar polling.
    """
    settings.validate()

    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .build()
    )

    # Registrar todos los handlers de comandos y conversaciones
    register_all_handlers(application)

    # Registrar manejador global de errores
    application.add_error_handler(global_error_handler)

    return application


def main() -> None:
    """Función de arranque principal."""
    setup_logging()
    logger.info("Iniciando Academic Bot (Telegram)...")

    try:
        app = build_application()
        logger.info("Conexión con Telegram lista. Iniciando polling...")
        app.run_polling(drop_pending_updates=True)
    except ValueError as val_err:
        logger.critical("Error de configuración: %s", val_err)
        sys.exit(1)
    except Exception as exc:
        logger.critical("Error fatal al arrancar Academic Bot: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
