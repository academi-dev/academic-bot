"""
Manejador para el comando /materias de Academic Bot.

Permite consultar el listado de asignaturas matriculadas por el estudiante
a través de academic-api y presentarlas formateadas con emojis y Markdown.
"""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.services.api_client import (
    ApiAuthError,
    ApiClientError,
    ApiConnectionError,
    api_client,
)
from bot.utils.auth_storage import auth_storage
from bot.utils.formatters import format_materias

logger = logging.getLogger(__name__)


async def materias_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador del comando /materias.
    
    Verifica la sesión activa del usuario, consulta sus asignaturas a academic-api
    y envía la lista estructurada con detalles de docentes y créditos.
    """
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    token = auth_storage.get_token(chat_id)

    if not token:
        await update.message.reply_text(
            "🔒 *Acceso restringido*\n\n"
            "Debes iniciar sesión para consultar tus materias.\n"
            "Usa /login para ingresar o /registro para crear tu cuenta.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text("📚 Consultando tus materias inscritas...")

    try:
        materias = await api_client.get_materias(token=token)
        mensaje = format_materias(materias)

        await update.message.reply_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )

    except ApiAuthError:
        # El token expiró o fue revocado
        auth_storage.remove_token(chat_id)
        await update.message.reply_text(
            "⚠️ *Tu sesión ha expirado.*\n"
            "Por favor, inicia sesión nuevamente utilizando /login.",
            parse_mode=ParseMode.MARKDOWN
        )
    except ApiConnectionError as exc:
        await update.message.reply_text(
            f"📡 *Problema de conexión:*\n{exc.message}\n"
            f"El servidor de asignaturas no está disponible en este momento.",
            parse_mode=ParseMode.MARKDOWN
        )
    except ApiClientError as exc:
        logger.error("Error al obtener materias: %s", exc)
        await update.message.reply_text(
            f"⚠️ No se pudieron obtener tus materias: {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
