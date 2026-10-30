"""
Paquete de manejadores de Telegram para Academic Bot.

Registra todos los comandos y ConversationHandlers en la aplicación.
"""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from bot.handlers.auth import (
    get_login_conversation_handler,
    get_registro_conversation_handler,
    logout_command,
)
from bot.handlers.materias import materias_command
from bot.handlers.preguntas import get_preguntas_conversation_handler
from bot.handlers.recordatorios import get_recordar_conversation_handler
from bot.handlers.start import help_command, start_command
from bot.handlers.tareas import pendientes_command, tareas_command

logger = logging.getLogger(__name__)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manejador para comandos no reconocidos."""
    if update.message:
        await update.message.reply_text(
            "🤔 No reconozco ese comando.\n"
            "Escribe /help para ver la lista de comandos disponibles.",
            parse_mode=ParseMode.MARKDOWN
        )


def register_all_handlers(application: Application) -> None:
    """
    Registra todos los manejadores en la instancia de la aplicación de Telegram.

    Args:
        application: Instancia activa de telegram.ext.Application.
    """
    # 1. Comandos básicos informativos
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # 2. Conversaciones de Autenticación
    application.add_handler(get_login_conversation_handler())
    application.add_handler(get_registro_conversation_handler())
    application.add_handler(CommandHandler("logout", logout_command))

    # 3. Asignaturas y Tareas
    application.add_handler(CommandHandler("materias", materias_command))
    application.add_handler(CommandHandler("tareas", tareas_command))
    application.add_handler(CommandHandler("pendientes", pendientes_command))

    # 4. Recordatorios (job_queue)
    application.add_handler(get_recordar_conversation_handler())

    # 5. Preguntas RAG
    application.add_handler(get_preguntas_conversation_handler())

    # 6. Fallback para comandos desconocidos
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    logger.info("Todos los manejadores han sido registrados exitosamente.")


__all__ = [
    "help_command",
    "materias_command",
    "pendientes_command",
    "register_all_handlers",
    "start_command",
    "tareas_command",
]
