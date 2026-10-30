"""
Manejadores para los comandos /tareas y /pendientes de Academic Bot.

Permite consultar la totalidad de tareas del estudiante y filtrar aquellas
que vencen en los próximos 7 días con alertas prioritarias.
"""

import logging
from typing import List, Dict, Any
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
from bot.utils.formatters import (
    format_tareas,
    is_due_in_next_days,
    parse_iso_datetime,
)

logger = logging.getLogger(__name__)


async def tareas_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador del comando /tareas.
    
    Obtiene y muestra todas las tareas asignadas al usuario sin importar la fecha de entrega.
    """
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    token = auth_storage.get_token(chat_id)

    if not token:
        await update.message.reply_text(
            "🔒 *Acceso restringido*\n\n"
            "Debes iniciar sesión para consultar tus tareas.\n"
            "Usa /login para identificarte.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text("📋 Consultando tus tareas...")

    try:
        tareas = await api_client.get_tareas(token=token)
        mensaje = format_tareas(
            tareas=tareas,
            title="📋 *Todas tus Tareas:*",
            empty_message="🎉 ¡Excelente! No tienes tareas registradas en el sistema."
        )

        await update.message.reply_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )

    except ApiAuthError:
        auth_storage.remove_token(chat_id)
        await update.message.reply_text(
            "⚠️ *Sesión expirada.* Por favor, vuelve a iniciar sesión con /login.",
            parse_mode=ParseMode.MARKDOWN
        )
    except ApiConnectionError as exc:
        await update.message.reply_text(
            f"📡 *Error de conexión:* {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
    except ApiClientError as exc:
        logger.error("Error al obtener tareas: %s", exc)
        await update.message.reply_text(
            f"⚠️ Error al obtener las tareas: {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )


async def pendientes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador del comando /pendientes.
    
    Filtra y muestra exclusivamente las tareas que vencen en los próximos 7 días,
    ordenadas cronológicamente para facilitar la priorización del estudiante.
    """
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    token = auth_storage.get_token(chat_id)

    if not token:
        await update.message.reply_text(
            "🔒 *Acceso restringido*\n\n"
            "Inicia sesión con /login para ver tus entregas pendientes.",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await update.message.reply_text("⏳ Buscando entregas para los próximos 7 días...")

    try:
        todas_las_tareas = await api_client.get_tareas(token=token)

        # Filtrar tareas: no completadas y con vencimiento en <= 7 días
        pendientes_7_dias: List[Dict[str, Any]] = []
        for t in todas_las_tareas:
            estado = (t.get("estado") or "").lower()
            if estado in ("entregada", "completada", "calificada"):
                continue

            fecha_raw = t.get("fecha_entrega", t.get("fecha_limite"))
            if is_due_in_next_days(fecha_raw, days=7):
                pendientes_7_dias.append(t)

        # Ordenar por fecha de entrega ascendente
        def get_sort_key(t: Dict[str, Any]):
            dt = parse_iso_datetime(t.get("fecha_entrega", t.get("fecha_limite")))
            return dt.timestamp() if dt else float("inf")

        pendientes_7_dias.sort(key=get_sort_key)

        mensaje = format_tareas(
            tareas=pendientes_7_dias,
            title="⏳ *Entregas Pendientes (Próximos 7 Días):*",
            empty_message=(
                "🎉 *¡Todo al día!*\n\n"
                "No tienes entregas programadas para los próximos 7 días.\n"
                "Usa /tareas para revisar el historial completo o /recordar para crear una alarma."
            )
        )

        await update.message.reply_text(
            mensaje,
            parse_mode=ParseMode.MARKDOWN
        )

    except ApiAuthError:
        auth_storage.remove_token(chat_id)
        await update.message.reply_text(
            "⚠️ *Tu sesión ha expirado.*\nInicia sesión nuevamente con /login.",
            parse_mode=ParseMode.MARKDOWN
        )
    except ApiConnectionError as exc:
        await update.message.reply_text(
            f"📡 *Error de conexión:* {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
    except ApiClientError as exc:
        logger.error("Error al obtener pendientes: %s", exc)
        await update.message.reply_text(
            f"⚠️ No fue posible consultar los pendientes: {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
