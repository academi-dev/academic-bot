"""
Manejadores para los comandos /start y /help de Academic Bot.

Presenta el mensaje de bienvenida, información de la plataforma y el menú de comandos disponibles.
"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.utils.auth_storage import auth_storage


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador del comando /start.
    
    Da la bienvenida al estudiante, verifica si ya tiene sesión activa y
    ofrece las opciones principales.
    """
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name if update.effective_user else "Estudiante"
    is_auth = auth_storage.is_authenticated(chat_id)
    stored_user = auth_storage.get_user_info(chat_id) or {}
    nombre_usuario = stored_user.get("nombre", user_name)

    auth_status = (
        f"✅ *Sesión activa como:* _{nombre_usuario}_"
        if is_auth
        else "🔒 *Estado:* Sin sesión activa. Inicia sesión con /login o regístrate con /registro."
    )

    welcome_text = (
        f"🎓 *¡Bienvenido al Asistente de Academic, {user_name}!* 🎓\n\n"
        f"Sistema de gestión universitaria diseñado para acompañarte en tu día a día académico.\n\n"
        f"{auth_status}\n\n"
        f"📌 *Comandos más utilizados:*\n"
        f"📚 /materias — Consulta tus asignaturas inscritas\n"
        f"📋 /tareas — Revisa todas tus tareas\n"
        f"⏳ /pendientes — Entregas de los próximos 7 días\n"
        f"⏰ /recordar — Programa recordatorios automáticos\n"
        f"🤖 /preguntar — Consulta al asistente inteligente (RAG)\n"
        f"ℹ️ /help — Menú completo de comandos y ayuda\n\n"
        f"💡 _Tip: Para comenzar, inicia sesión con_ `/login`."
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador del comando /help.
    
    Despliega la lista detallada de comandos clasificados por categoría.
    """
    if not update.message:
        return

    help_text = (
        "📖 *Guía de Comandos — Academic Bot*\n\n"
        "🔐 *Autenticación y Cuenta:*\n"
        "• /login — Inicia sesión con correo y contraseña\n"
        "• /registro — Crea una nueva cuenta de estudiante\n"
        "• /logout — Cierra tu sesión actual de este chat\n\n"
        "📚 *Gestión Académica:*\n"
        "• /materias — Lista tus materias matriculadas y profesores\n"
        "• /tareas — Muestra todas tus tareas y estados\n"
        "• /pendientes — Muestra tareas que vencen en los próximos 7 días\n\n"
        "⏰ *Recordatorios y Productividad:*\n"
        "• /recordar — Programa un aviso automático para una tarea\n"
        "  _Ejemplo rápido:_ `/recordar 2h Estudiar para Física`\n\n"
        "🤖 *Asistente Inteligente (RAG):*\n"
        "• /preguntar — Haz una consulta académica basada en tus documentos\n"
        "  _Ejemplo:_ `/preguntar ¿Cuáles son los temas del primer parcial?`\n\n"
        "ℹ️ *Información:* /help | /start\n"
        "❌ *Cancelar operación actual:* /cancelar\n\n"
        "---\n"
        "🏛️ *Academic Dev Team:* Jean Mena (@hilton45) & Eyfer Mena (@Eyfer3174)"
    )

    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )
