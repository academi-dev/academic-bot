"""
Manejador del comando /recordar para Academic Bot.

Permite programar alertas y recordatorios automáticos de tareas utilizando
la cola de trabajos (job_queue / APScheduler) de python-telegram-bot.
"""

import logging
from typing import Dict, Any
from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.utils.formatters import (
    format_reminder_notification,
    parse_time_offset_or_date,
)

logger = logging.getLogger(__name__)

# Estados del ConversationHandler para recordatorios
RECORDAR_TAREA, RECORDAR_TIEMPO = range(2)


async def send_reminder_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Función de callback ejecutada por la cola de trabajos (job_queue) cuando se cumple el tiempo.
    
    Envía el mensaje de recordatorio al chat del estudiante.
    """
    job_data: Dict[str, Any] = context.job.data if context.job and context.job.data else {}
    chat_id = job_data.get("chat_id")
    tarea = job_data.get("tarea", "Tarea académica pendiente")
    fecha_entrega = job_data.get("fecha_entrega")

    if not chat_id:
        logger.error("Job de recordatorio ejecutado sin chat_id en job.data")
        return

    mensaje = format_reminder_notification(
        tarea_titulo=tarea,
        fecha_entrega=fecha_entrega
    )

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode=ParseMode.MARKDOWN
        )
        logger.info("Recordatorio enviado exitosamente a chat_id %s: %s", chat_id, tarea)
    except Exception as exc:
        logger.error("Error al enviar recordatorio a chat_id %s: %s", chat_id, exc)


async def recordar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Punto de entrada para el comando /recordar.
    
    Soporta dos modalidades:
    1. Directa con argumentos: `/recordar 30m Estudiar Álgebra Lineal`
    2. Conversacional paso a paso: solicita tarea y luego tiempo.
    """
    if not update.effective_chat or not update.message:
        return ConversationHandler.END

    chat_id = update.effective_chat.id

    if not context.job_queue:
        await update.message.reply_text(
            "⚠️ La cola de trabajos (job_queue) no está disponible en este momento. "
            "Verifica la instalación de python-telegram-bot[job-queue]."
        )
        return ConversationHandler.END

    # Revisar si el usuario pasó argumentos directos: ej. /recordar 2h Terminar informe
    args = context.args or []
    if len(args) >= 2:
        tiempo_str = args[0]
        asunto = " ".join(args[1:])

        segundos = parse_time_offset_or_date(tiempo_str)
        if segundos is not None:
            # Programar inmediatamente
            context.job_queue.run_once(
                callback=send_reminder_job,
                when=segundos,
                chat_id=chat_id,
                data={"chat_id": chat_id, "tarea": asunto},
                name=f"remind_{chat_id}_{asunto[:15]}"
            )

            minutos_aprox = max(1, round(segundos / 60))
            await update.message.reply_text(
                f"⏰ *¡Recordatorio programado con éxito!* ⏰\n\n"
                f"📌 *Asunto:* {asunto}\n"
                f"⏳ *Se activará en:* aprox. {minutos_aprox} minuto(s) (`{tiempo_str}`)\n\n"
                f"Te avisaré por este chat en el momento exacto.",
                parse_mode=ParseMode.MARKDOWN
            )
            return ConversationHandler.END

    # Flujo conversacional interactivo
    context.user_data.pop("recordar_tarea", None)

    await update.message.reply_text(
        "⏰ *Programar un Recordatorio Académico*\n\n"
        "Paso 1/2: ¿Para qué *tarea, examen o asunto* deseas programar el recordatorio?\n\n"
        "_(Escribe /cancelar para cancelar)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    return RECORDAR_TAREA


async def recordar_receive_tarea(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la descripción o título de la tarea a recordar."""
    if not update.message or not update.message.text:
        return RECORDAR_TAREA

    tarea = update.message.text.strip()
    context.user_data["recordar_tarea"] = tarea

    await update.message.reply_text(
        f"📌 Asunto: *{tarea}*\n\n"
        f"Paso 2/2: ¿En cuánto tiempo deseas recibir el aviso?\n\n"
        f"Puedes escribir:\n"
        f"• Relativo: `15m` (15 min), `2h` (2 horas), `1d` (1 día), `30s`\n"
        f"• Fecha/hora UTC: `2026-10-30 18:00` o `30/10/2026 18:00`",
        parse_mode=ParseMode.MARKDOWN
    )
    return RECORDAR_TIEMPO


async def recordar_receive_tiempo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la especificación de tiempo y programa el job en la cola."""
    if not update.effective_chat or not update.message or not update.message.text:
        return RECORDAR_TIEMPO

    chat_id = update.effective_chat.id
    tiempo_texto = update.message.text.strip()
    tarea = context.user_data.get("recordar_tarea", "Tarea académica")

    segundos = parse_time_offset_or_date(tiempo_texto)
    if segundos is None:
        await update.message.reply_text(
            "⚠️ No pude interpretar ese tiempo o la fecha ya pasó.\n"
            "Ejemplos válidos: `10m`, `1h30m`, `2h`, `1d` o `2026-10-31 15:00`.\n\n"
            "Intenta de nuevo:"
        )
        return RECORDAR_TIEMPO

    if not context.job_queue:
        await update.message.reply_text("❌ Error interno: job_queue no está activo.")
        return ConversationHandler.END

    # Programar en APScheduler / job_queue
    context.job_queue.run_once(
        callback=send_reminder_job,
        when=segundos,
        chat_id=chat_id,
        data={"chat_id": chat_id, "tarea": tarea},
        name=f"remind_{chat_id}_{tarea[:15]}"
    )

    minutos_aprox = max(1, round(segundos / 60))
    await update.message.reply_text(
        f"✅ *¡Recordatorio configurado exitosamente!*\n\n"
        f"📌 *Tarea:* {tarea}\n"
        f"⏱️ *Tiempo restante:* ~{minutos_aprox} minuto(s) (`{tiempo_texto}`)\n\n"
        f"Recibirás una notificación por aquí cuando venza el plazo. 🚀",
        parse_mode=ParseMode.MARKDOWN
    )

    context.user_data.pop("recordar_tarea", None)
    return ConversationHandler.END


async def cancel_recordar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la programación del recordatorio."""
    if update.message:
        await update.message.reply_text(
            "🚫 Programación de recordatorio cancelada.",
            reply_markup=ReplyKeyboardRemove()
        )
    context.user_data.pop("recordar_tarea", None)
    return ConversationHandler.END


def get_recordar_conversation_handler() -> ConversationHandler:
    """Construye el ConversationHandler para el comando /recordar."""
    return ConversationHandler(
        entry_points=[CommandHandler("recordar", recordar_start)],
        states={
            RECORDAR_TAREA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recordar_receive_tarea)
            ],
            RECORDAR_TIEMPO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recordar_receive_tiempo)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancel_recordar),
            CommandHandler("cancel", cancel_recordar),
        ],
        allow_reentry=True,
    )
