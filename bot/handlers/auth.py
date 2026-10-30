"""
Manejadores de autenticación para Academic Bot.

Implementa los flujos conversacionales de /login y /registro utilizando ConversationHandler,
así como el comando /logout y la cancelación de operaciones.
"""

import logging
import re
from typing import Dict
from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.services.api_client import (
    ApiAuthError,
    ApiClientError,
    ApiConflictError,
    ApiConnectionError,
    ApiValidationError,
    api_client,
)
from bot.utils.auth_storage import auth_storage

logger = logging.getLogger(__name__)

# Estados para la conversación de Login
LOGIN_EMAIL, LOGIN_PASSWORD = range(2)

# Estados para la conversación de Registro
REG_NOMBRE, REG_EMAIL, REG_PASSWORD = range(2, 5)

EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


# ==========================================
# FLUJO DE LOGIN
# ==========================================

async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso interactivo de inicio de sesión."""
    if not update.effective_chat or not update.message:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    if auth_storage.is_authenticated(chat_id):
        user_info = auth_storage.get_user_info(chat_id) or {}
        nombre = user_info.get("nombre", "Estudiante")
        await update.message.reply_text(
            f"ℹ️ Ya tienes una sesión activa como *{nombre}*.\n"
            f"Si deseas cambiar de cuenta, escribe /logout primero.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # Limpiar datos previos en el contexto del usuario
    context.user_data.pop("login_email", None)

    await update.message.reply_text(
        "🔐 *Inicio de Sesión — Academic*\n\n"
        "Por favor, ingresa tu *correo electrónico institucional*:\n\n"
        "_(Escribe /cancelar en cualquier momento para abortar)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    return LOGIN_EMAIL


async def login_receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida el correo electrónico para el inicio de sesión."""
    if not update.message or not update.message.text:
        return LOGIN_EMAIL

    email = update.message.text.strip().lower()

    if not re.match(EMAIL_REGEX, email):
        await update.message.reply_text(
            "⚠️ El formato del correo electrónico no es válido.\n"
            "Por favor, escribe un correo válido (ej. `usuario@universidad.edu`):",
            parse_mode=ParseMode.MARKDOWN
        )
        return LOGIN_EMAIL

    context.user_data["login_email"] = email

    await update.message.reply_text(
        f"📧 Correo registrado: `{email}`\n\n"
        f"🔑 Ahora ingresa tu *contraseña*:\n"
        f"_(Por seguridad, puedes borrar tu mensaje después de enviarlo)_",
        parse_mode=ParseMode.MARKDOWN
    )
    return LOGIN_PASSWORD


async def login_receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la contraseña y autentica al usuario contra academic-api."""
    if not update.effective_chat or not update.message or not update.message.text:
        return LOGIN_PASSWORD

    chat_id = update.effective_chat.id
    password = update.message.text.strip()
    email = context.user_data.get("login_email", "")

    if not email:
        await update.message.reply_text(
            "⚠️ Ocurrió un error con el flujo de inicio de sesión. Inicia nuevamente con /login."
        )
        return ConversationHandler.END

    await update.message.reply_text("⏳ Verificando credenciales con Academic...")

    try:
        response = await api_client.login(email=email, password=password)

        # Extraer token y datos del usuario
        token = response.get("access_token") or response.get("token")
        if not token:
            await update.message.reply_text(
                "❌ Error: La respuesta del servidor no incluyó el token de acceso. "
                "Intenta nuevamente más tarde."
            )
            return ConversationHandler.END

        # Extraer información de usuario devuelta
        usuario = response.get("usuario") or response.get("user") or {}
        if not usuario:
            usuario = {"email": email, "nombre": email.split("@")[0].capitalize()}

        auth_storage.set_token(chat_id=chat_id, token=token, user_info=usuario)
        nombre = usuario.get("nombre", "Estudiante")

        await update.message.reply_text(
            f"🎉 *¡Bienvenido de nuevo, {nombre}!* 🎉\n\n"
            f"Has iniciado sesión exitosamente.\n\n"
            f"Ya puedes consultar tus datos con:\n"
            f"📚 /materias — Tus asignaturas inscritas\n"
            f"⏳ /pendientes — Entregas de los próximos 7 días\n"
            f"📋 /tareas — Lista completa de tareas\n"
            f"🤖 /preguntar — Resolver dudas con RAG",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    except ApiAuthError:
        await update.message.reply_text(
            "❌ *Credenciales incorrectas.*\n"
            "El correo o la contraseña no coinciden.\n"
            "Usa /login para intentar nuevamente.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except ApiConnectionError as exc:
        await update.message.reply_text(
            f"📡 *Error de conexión:* {exc.message}\n"
            f"Verifica que el servicio academic-api esté en ejecución.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except ApiClientError as exc:
        await update.message.reply_text(
            f"⚠️ *Error en la autenticación:* {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    finally:
        context.user_data.pop("login_email", None)


# ==========================================
# FLUJO DE REGISTRO
# ==========================================

async def registro_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el registro interactivo de una nueva cuenta."""
    if not update.effective_chat or not update.message:
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    if auth_storage.is_authenticated(chat_id):
        await update.message.reply_text(
            "ℹ️ Ya estás autenticado. Para registrar una cuenta nueva, "
            "cierra la sesión actual con /logout.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    context.user_data.clear()

    await update.message.reply_text(
        "📝 *Registro de Nuevo Estudiante — Academic*\n\n"
        "Creemos tu cuenta universitaria en 3 sencillos pasos.\n\n"
        "Paso 1/3: ¿Cuál es tu *nombre completo*?\n"
        "_(Escribe /cancelar para salir)_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardRemove()
    )
    return REG_NOMBRE


async def registro_receive_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y guarda el nombre completo del estudiante."""
    if not update.message or not update.message.text:
        return REG_NOMBRE

    nombre = update.message.text.strip()
    if len(nombre) < 3:
        await update.message.reply_text(
            "⚠️ Por favor, ingresa un nombre válido (al menos 3 caracteres):"
        )
        return REG_NOMBRE

    context.user_data["reg_nombre"] = nombre

    await update.message.reply_text(
        f"Mucho gusto, *{nombre}*.\n\n"
        f"Paso 2/3: Ingresa tu *correo electrónico universitario*:",
        parse_mode=ParseMode.MARKDOWN
    )
    return REG_EMAIL


async def registro_receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida el correo para el registro."""
    if not update.message or not update.message.text:
        return REG_EMAIL

    email = update.message.text.strip().lower()

    if not re.match(EMAIL_REGEX, email):
        await update.message.reply_text(
            "⚠️ El formato del correo no es válido. Ingresa un correo correcto (ej. `estudiante@universidad.edu`):",
            parse_mode=ParseMode.MARKDOWN
        )
        return REG_EMAIL

    context.user_data["reg_email"] = email

    await update.message.reply_text(
        f"📧 Correo: `{email}`\n\n"
        f"Paso 3/3: Define tu *contraseña* (mínimo 6 caracteres):",
        parse_mode=ParseMode.MARKDOWN
    )
    return REG_PASSWORD


async def registro_receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la contraseña y crea el usuario en academic-api."""
    if not update.effective_chat or not update.message or not update.message.text:
        return REG_PASSWORD

    chat_id = update.effective_chat.id
    password = update.message.text.strip()

    if len(password) < 6:
        await update.message.reply_text(
            "⚠️ La contraseña debe contener al menos 6 caracteres. Intenta de nuevo:"
        )
        return REG_PASSWORD

    nombre = context.user_data.get("reg_nombre", "")
    email = context.user_data.get("reg_email", "")

    await update.message.reply_text("⏳ Registrando tu cuenta en Academic...")

    try:
        reg_response = await api_client.register(
            nombre=nombre,
            email=email,
            password=password
        )

        # Intentar iniciar sesión automáticamente
        token = reg_response.get("access_token")
        usuario = reg_response.get("usuario") or {"nombre": nombre, "email": email}

        if not token:
            login_res = await api_client.login(email=email, password=password)
            token = login_res.get("access_token")
            if "usuario" in login_res:
                usuario = login_res["usuario"]

        if token:
            auth_storage.set_token(chat_id=chat_id, token=token, user_info=usuario)

        await update.message.reply_text(
            f"🎉 *¡Cuenta creada con éxito, {nombre}!* 🎉\n\n"
            f"Tu usuario ya se encuentra registrado y con sesión iniciada.\n\n"
            f"Explora tus asignaturas y tareas con /materias y /pendientes.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    except ApiConflictError:
        await update.message.reply_text(
            f"❌ El correo `{email}` ya se encuentra registrado.\n"
            f"Intenta iniciar sesión con /login o regístrate con otro correo.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except ApiValidationError as exc:
        await update.message.reply_text(
            f"⚠️ Datos no válidos: {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except ApiConnectionError as exc:
        await update.message.reply_text(
            f"📡 *Error de conexión:* {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except ApiClientError as exc:
        await update.message.reply_text(
            f"⚠️ Error al crear la cuenta: {exc.message}",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    finally:
        context.user_data.clear()


# ==========================================
# LOGOUT Y CANCELACIÓN
# ==========================================

async def logout_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cierra la sesión del usuario en este chat de Telegram."""
    if not update.effective_chat or not update.message:
        return

    chat_id = update.effective_chat.id
    if auth_storage.remove_token(chat_id):
        await update.message.reply_text(
            "👋 *Has cerrado sesión correctamente.*\n"
            "Tus credenciales y token han sido retirados de la memoria del bot.\n"
            "Para volver a ingresar, usa /login.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            "ℹ️ No tenías ninguna sesión activa en este chat.\n"
            "Puedes iniciar sesión con /login.",
            parse_mode=ParseMode.MARKDOWN
        )


async def cancel_auth(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación de autenticación en curso."""
    if update.message:
        await update.message.reply_text(
            "🚫 Operación cancelada. Puedes retomar en cualquier momento con /login o /registro.",
            reply_markup=ReplyKeyboardRemove()
        )
    context.user_data.clear()
    return ConversationHandler.END


# ==========================================
# CONSTRUCTORES DE CONVERSATION HANDLERS
# ==========================================

def get_login_conversation_handler() -> ConversationHandler:
    """Construye el ConversationHandler para el flujo de /login."""
    return ConversationHandler(
        entry_points=[CommandHandler("login", login_start)],
        states={
            LOGIN_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_receive_email)
            ],
            LOGIN_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_receive_password)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancel_auth),
            CommandHandler("cancel", cancel_auth),
        ],
        allow_reentry=True,
    )


def get_registro_conversation_handler() -> ConversationHandler:
    """Construye el ConversationHandler para el flujo de /registro."""
    return ConversationHandler(
        entry_points=[CommandHandler("registro", registro_start)],
        states={
            REG_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registro_receive_nombre)
            ],
            REG_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registro_receive_email)
            ],
            REG_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, registro_receive_password)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancel_auth),
            CommandHandler("cancel", cancel_auth),
        ],
        allow_reentry=True,
    )
