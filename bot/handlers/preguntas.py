"""
Manejador para el comando /preguntar de Academic Bot.

Permite enviar consultas al servicio academic-rag y mostrar las respuestas generadas
junto con sus fuentes documentales, citas y fragmentos de texto.
"""

import logging
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.services.rag_client import (
    RagClientError,
    RagConnectionError,
    rag_client,
)
from bot.utils.auth_storage import auth_storage
from bot.utils.formatters import format_rag_response

logger = logging.getLogger(__name__)

# Estado para la conversación interactiva de preguntas
PREGUNTA_TEXTO = 0


async def process_and_reply_question(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    question: str
) -> None:
    """Ejecuta la consulta contra academic-rag y responde al usuario en Telegram."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    token = auth_storage.get_token(chat_id)

    # Indicar que el bot está procesando / escribiendo
    await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    msg_espera = await update.message.reply_text("🤖 Consultando tus documentos académicos con RAG...")

    try:
        response = await rag_client.ask_question(query=question, token=token)
        mensaje_formateado = format_rag_response(response=response, query=question)

        # Editar o responder
        await msg_espera.edit_text(
            mensaje_formateado,
            parse_mode=ParseMode.MARKDOWN
        )

    except RagConnectionError as exc:
        await msg_espera.edit_text(
            f"📡 *Servicio RAG no disponible*\n\n"
            f"{exc.message}\n"
            f"Por favor, intenta más tarde o consulta con tu docente.",
            parse_mode=ParseMode.MARKDOWN
        )
    except RagClientError as exc:
        logger.error("Error al consultar RAG: %s", exc)
        await msg_espera.edit_text(
            f"⚠️ *Error en la consulta:* {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as exc:
        logger.exception("Error inesperado en /preguntar: %s", exc)
        await msg_espera.edit_text(
            "❌ Ocurrió un error inesperado al procesar la respuesta. Intenta con una pregunta más específica."
        )


async def preguntar_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Punto de entrada de /preguntar.
    
    Si se envían argumentos (`/preguntar ¿Qué es...?`), responde de inmediato.
    Si se invoca sin argumentos, solicita la pregunta al usuario.
    """
    if not update.message:
        return ConversationHandler.END

    args = context.args or []
    if args:
        question = " ".join(args).strip()
        await process_and_reply_question(update, context, question)
        return ConversationHandler.END

    await update.message.reply_text(
        "🤖 *Asistente Inteligente Académico (RAG)*\n\n"
        "Escribe la pregunta que deseas formular sobre tus asignaturas, "
        "fechas, rúbricas o material de estudio:\n\n"
        "_(Escribe /cancelar para salir)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return PREGUNTA_TEXTO


async def preguntar_receive_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el texto de la pregunta y la envía al servicio RAG."""
    if not update.message or not update.message.text:
        return PREGUNTA_TEXTO

    question = update.message.text.strip()
    await process_and_reply_question(update, context, question)
    return ConversationHandler.END


async def cancel_preguntar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la consulta de preguntas."""
    if update.message:
        await update.message.reply_text("🚫 Consulta al asistente cancelada.")
    return ConversationHandler.END


def get_preguntas_conversation_handler() -> ConversationHandler:
    """Construye el ConversationHandler para el comando /preguntar."""
    return ConversationHandler(
        entry_points=[CommandHandler("preguntar", preguntar_start)],
        states={
            PREGUNTA_TEXTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, preguntar_receive_texto)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancel_preguntar),
            CommandHandler("cancel", cancel_preguntar),
        ],
        allow_reentry=True,
    )
