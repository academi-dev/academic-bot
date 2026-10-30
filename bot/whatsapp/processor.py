"""Procesador de comandos y conversaciones para WhatsApp en Academic Bot.

Reutiliza los clientes asíncronos (`AcademicApiClient` y `AcademicRagClient`),
el almacén de sesiones (`AuthStorage`) y los formateadores (`formatters.py`)
para brindar exactamente las mismas funciones de Telegram desde WhatsApp.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional

from bot.services.api_client import (
    AcademicApiClient,
    ApiAuthError,
    ApiClientError,
    ApiConflictError,
    ApiConnectionError,
    ApiValidationError,
    api_client,
)
from bot.services.rag_client import (
    AcademicRagClient,
    RagClientError,
    RagConnectionError,
    rag_client,
)
from bot.utils.auth_storage import AuthStorage, auth_storage
from bot.utils.formatters import (
    format_datetime_friendly,
    format_materias,
    format_rag_response,
    format_reminder_notification,
    format_tareas,
    is_due_in_next_days,
    parse_iso_datetime,
    parse_time_offset_or_date,
)

logger = logging.getLogger(__name__)


class WhatsAppCommandProcessor:
    """Despachador conversacional de comandos académicos para WhatsApp."""

    def __init__(
        self,
        api: Optional[AcademicApiClient] = None,
        rag: Optional[AcademicRagClient] = None,
        storage: Optional[AuthStorage] = None,
    ) -> None:
        self.api = api or api_client
        self.rag = rag or rag_client
        self.storage = storage or auth_storage
        # Estado conversacional por remitente (JID o teléfono)
        self._states: Dict[str, Dict[str, Any]] = {}

    def get_welcome_menu(self, sender_id: str) -> str:
        """Construye el mensaje de bienvenida y menú de comandos para WhatsApp."""
        autenticado = self.storage.is_authenticated(sender_id)
        user_info = self.storage.get_user_info(sender_id) or {}
        nombre = user_info.get("nombre") or user_info.get("email") or "Estudiante"

        estado_str = (
            f"🟢 *Sesión activa:* {nombre}"
            if autenticado
            else "🔴 *Sesión no iniciada* (usa `/login` o `/registro`)"
        )

        return (
            "🎓 *Academic Bot — Asistente en WhatsApp*\n\n"
            f"{estado_str}\n\n"
            "📌 *Comandos disponibles:*\n"
            "• `/start` o `/help` — Ver este menú de ayuda\n"
            "• `/registro` — Crear una cuenta de estudiante\n"
            "• `/login <correo> <clave>` — Iniciar sesión (o escribe solo `/login` paso a paso)\n"
            "• `/logout` — Cerrar tu sesión actual\n"
            "• `/materias` — Consultar tus asignaturas inscritas\n"
            "• `/tareas` — Ver todas tus entregas académicas\n"
            "• `/pendientes` — Ver entregas urgentes (próximos 7 días)\n"
            "• `/recordar <tiempo> <tarea>` — Programar alerta (ej: `/recordar 30m Estudiar AVL`)\n"
            "• `/preguntar <duda>` — Consultar tus apuntes PDF con IA y citas\n"
            "• `/cancelar` — Cancelar cualquier operación en curso"
        )

    async def handle_message(self, sender_id: str, raw_text: str) -> Dict[str, Any]:
        """Procesa un mensaje entrante de WhatsApp y retorna la respuesta y acciones opcionales.

        Args:
            sender_id: Identificador JID o número de WhatsApp (ej. '573001234567@s.whatsapp.net').
            raw_text: Texto enviado por el usuario.

        Returns:
            Diccionario con:
                - 'reply': Texto formateado para WhatsApp.
                - 'reminder': Diccionario opcional {'delay_seconds': int, 'text': str} si agendó recordatorio.
        """
        text = (raw_text or "").strip()
        if not text:
            return {"reply": self.get_welcome_menu(sender_id), "reminder": None}

        lower = text.lower()

        # Cancelación global de flujo guiado
        if lower in ("/cancelar", "/cancel", "cancelar"):
            if sender_id in self._states:
                self._states.pop(sender_id, None)
                return {"reply": "🚫 Operación cancelada. Escribe `/help` para ver los comandos.", "reminder": None}
            return {"reply": "ℹ️ No hay ninguna operación en curso.", "reminder": None}

        # Si el usuario está en medio de un flujo conversacional (login, registro, preguntar, recordar)
        if sender_id in self._states and not text.startswith("/"):
            return await self._continue_flow(sender_id, text)

        # Limpiar cualquier estado anterior si envía un nuevo comando explícito
        self._states.pop(sender_id, None)

        if lower in ("/start", "/help", "hola", "menu", "menú", "ayuda"):
            return {"reply": self.get_welcome_menu(sender_id), "reminder": None}

        if lower.startswith("/logout") or lower == "salir":
            removed = self.storage.remove_token(sender_id)
            if removed:
                return {"reply": "👋 *Sesión cerrada correctamente.*\nUsa `/login` cuando desees volver a ingresar.", "reminder": None}
            return {"reply": "ℹ️ No tenías una sesión activa.", "reminder": None}

        if lower.startswith("/login"):
            return await self._handle_login_command(sender_id, text)

        if lower.startswith("/registro"):
            return await self._handle_register_command(sender_id, text)

        if lower.startswith("/materias") or lower == "materias":
            return {"reply": await self._handle_materias(sender_id), "reminder": None}

        if lower.startswith("/tareas") or lower == "tareas":
            return {"reply": await self._handle_tareas(sender_id, solo_pendientes=False), "reminder": None}

        if lower.startswith("/pendientes") or lower == "pendientes":
            return {"reply": await self._handle_tareas(sender_id, solo_pendientes=True), "reminder": None}

        if lower.startswith("/recordar"):
            return self._handle_recordar_command(sender_id, text)

        if lower.startswith("/preguntar"):
            return await self._handle_preguntar_command(sender_id, text)

        # Si no coincide con ningún comando conocido
        return {
            "reply": (
                "🤔 No reconocí ese comando.\n"
                "Escribe `/help` para ver la lista de comandos o usa `/preguntar <tu duda>` para consultar tus apuntes."
            ),
            "reminder": None,
        }

    async def _handle_login_command(self, sender_id: str, text: str) -> Dict[str, Any]:
        parts = text.split(maxsplit=2)
        if len(parts) >= 3:
            email = parts[1].strip()
            password = parts[2].strip()
            return {"reply": await self._execute_login(sender_id, email, password), "reminder": None}

        self._states[sender_id] = {"flow": "login", "step": "email"}
        return {
            "reply": (
                "🔐 *Inicio de Sesión en Academic*\n\n"
                "Por favor, escribe tu *correo electrónico universitario*:\n"
                "_(O envía `/cancelar` para salir)_"
            ),
            "reminder": None,
        }

    async def _execute_login(self, sender_id: str, email: str, password: str) -> str:
        try:
            data = await self.api.login(email=email, password=password)
            token = data.get("access_token") or data.get("token")
            if not token:
                return "⚠️ El servidor no devolvió un token válido."

            self.storage.set_token(sender_id, token, {"email": email})
            return (
                "✅ *¡Sesión iniciada con éxito en WhatsApp!*\n\n"
                f"📧 Cuenta vinculada: `{email}`\n"
                "Ya puedes consultar `/materias`, `/tareas`, `/pendientes` o `/preguntar`."
            )
        except ApiAuthError:
            return "❌ *Credenciales incorrectas.*\nVerifica tu correo y contraseña e intenta de nuevo con `/login`."
        except ApiConnectionError as exc:
            return f"📡 *Error de conexión:* {exc.message}"
        except ApiClientError as exc:
            return f"⚠️ No fue posible iniciar sesión: {exc.message}"

    async def _handle_register_command(self, sender_id: str, text: str) -> Dict[str, Any]:
        # Permite atajo en una línea: /registro Nombre Completo | correo@u.edu | Clave123
        resto = text[len("/registro"):].strip()
        if "|" in resto:
            segmentos = [s.strip() for s in resto.split("|")]
            if len(segmentos) >= 3:
                nombre, email, password = segmentos[0], segmentos[1], segmentos[2]
                return {"reply": await self._execute_register(sender_id, nombre, email, password), "reminder": None}

        self._states[sender_id] = {"flow": "register", "step": "nombre"}
        return {
            "reply": (
                "📝 *Registro de Estudiante en Academic*\n\n"
                "Paso 1 de 3: Escribe tu *nombre completo*:\n"
                "_(O envía `/cancelar` para salir)_"
            ),
            "reminder": None,
        }

    async def _execute_register(self, sender_id: str, nombre: str, email: str, password: str) -> str:
        try:
            await self.api.register(nombre=nombre, email=email, password=password)
            # Iniciar sesión automáticamente tras el registro exitoso
            login_data = await self.api.login(email=email, password=password)
            token = login_data.get("access_token")
            if token:
                self.storage.set_token(sender_id, token, {"nombre": nombre, "email": email})
            return (
                f"🎉 *¡Cuenta creada y vinculada, {nombre}!*\n\n"
                f"📧 Correo: `{email}`\n"
                "Tu sesión ya está activa en WhatsApp. Prueba `/materias` o `/tareas`."
            )
        except ApiConflictError:
            return "⚠️ Ese correo electrónico ya está registrado. Usa `/login` para ingresar."
        except ApiValidationError as exc:
            return f"⚠️ Datos inválidos: {exc.message}"
        except ApiConnectionError as exc:
            return f"📡 *Error de conexión:* {exc.message}"
        except ApiClientError as exc:
            return f"⚠️ Error en el registro: {exc.message}"

    async def _handle_materias(self, sender_id: str) -> str:
        token = self.storage.get_token(sender_id)
        if not token:
            return (
                "🔒 *Acceso restringido*\n\n"
                "Debes iniciar sesión para consultar tus materias.\n"
                "Usa `/login <correo> <clave>` o `/registro`."
            )
        try:
            materias = await self.api.get_materias(token=token)
            return format_materias(materias)
        except ApiAuthError:
            self.storage.remove_token(sender_id)
            return "⚠️ *Tu sesión ha expirado.* Inicia sesión nuevamente con `/login`."
        except ApiConnectionError as exc:
            return f"📡 *Problema de conexión:* {exc.message}"
        except ApiClientError as exc:
            return f"⚠️ No se pudieron obtener tus materias: {exc.message}"

    async def _handle_tareas(self, sender_id: str, solo_pendientes: bool = False) -> str:
        token = self.storage.get_token(sender_id)
        if not token:
            return (
                "🔒 *Acceso restringido*\n\n"
                "Debes iniciar sesión para consultar tus tareas.\n"
                "Usa `/login <correo> <clave>`."
            )
        try:
            tareas = await self.api.get_tareas(token=token)
            if not solo_pendientes:
                return format_tareas(
                    tareas=tareas,
                    title="📋 *Todas tus Tareas:*",
                    empty_message="🎉 ¡Excelente! No tienes tareas registradas en el sistema.",
                )

            pendientes_7_dias: List[Dict[str, Any]] = []
            for t in tareas:
                estado = (t.get("estado") or "").lower()
                if estado in ("entregada", "completada", "calificada"):
                    continue
                fecha_raw = t.get("fecha_entrega", t.get("fecha_limite"))
                if is_due_in_next_days(fecha_raw, days=7):
                    pendientes_7_dias.append(t)

            def _sort_key(item: Dict[str, Any]) -> float:
                dt = parse_iso_datetime(item.get("fecha_entrega", item.get("fecha_limite")))
                return dt.timestamp() if dt else float("inf")

            pendientes_7_dias.sort(key=_sort_key)
            return format_tareas(
                tareas=pendientes_7_dias,
                title="⏳ *Entregas Pendientes (Próximos 7 Días):*",
                empty_message="🎉 *¡Todo al día!* No tienes entregas programadas para los próximos 7 días.",
            )
        except ApiAuthError:
            self.storage.remove_token(sender_id)
            return "⚠️ *Tu sesión ha expirado.* Inicia sesión nuevamente con `/login`."
        except ApiConnectionError as exc:
            return f"📡 *Error de conexión:* {exc.message}"
        except ApiClientError as exc:
            return f"⚠️ Error al consultar tareas: {exc.message}"

    def _handle_recordar_command(self, sender_id: str, text: str) -> Dict[str, Any]:
        parts = text.split(maxsplit=2)
        if len(parts) < 3:
            self._states[sender_id] = {"flow": "recordar", "step": "tiempo"}
            return {
                "reply": (
                    "⏰ *Programar Recordatorio en WhatsApp*\n\n"
                    "También puedes usar el formato rápido:\n"
                    "`/recordar 30m Repasar árboles AVL`\n\n"
                    "O dime en cuánto tiempo quieres que te avise (ej: `10s`, `15m`, `2h`, `1d`):"
                ),
                "reminder": None,
            }

        tiempo_str = parts[1].strip()
        mensaje_tarea = parts[2].strip()
        return self._build_reminder_response(tiempo_str, mensaje_tarea)

    def _build_reminder_response(self, tiempo_str: str, mensaje_tarea: str) -> Dict[str, Any]:
        seconds = parse_time_offset_or_date(tiempo_str)
        if not seconds:
            return {
                "reply": (
                    "⚠️ Formato de tiempo no válido. Usa números seguidos de `s`, `m`, `h` o `d` "
                    "(por ejemplo: `/recordar 20m Estudiar para el parcial`)."
                ),
                "reminder": None,
            }

        delay_seconds = max(1, int(seconds))
        trigger_dt = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        fecha_legible = format_datetime_friendly(trigger_dt)
        notif_text = format_reminder_notification(
            tarea_titulo=mensaje_tarea,
            fecha_entrega=trigger_dt.isoformat(),
        )
        return {
            "reply": (
                "✅ *Recordatorio Programado en WhatsApp*\n\n"
                f"📝 *Motivo:* {mensaje_tarea}\n"
                f"⏳ *Tiempo:* `{tiempo_str}` ({fecha_legible})\n"
                "Te enviaré un mensaje de alerta por WhatsApp cuando se cumpla el tiempo."
            ),
            "reminder": {
                "delay_seconds": delay_seconds,
                "text": notif_text,
            },
        }

    async def _handle_preguntar_command(self, sender_id: str, text: str) -> Dict[str, Any]:
        question = text[len("/preguntar"):].strip()
        if not question:
            self._states[sender_id] = {"flow": "preguntar", "step": "question"}
            return {
                "reply": (
                    "🤖 *Asistente Académico RAG en WhatsApp*\n\n"
                    "Escribe tu pregunta sobre los apuntes o PDFs de clase:\n"
                    "_(O envía `/cancelar` para salir)_"
                ),
                "reminder": None,
            }
        return {"reply": await self._execute_question(sender_id, question), "reminder": None}

    async def _execute_question(self, sender_id: str, question: str) -> str:
        token = self.storage.get_token(sender_id)
        try:
            response = await self.rag.ask_question(query=question, token=token)
            return format_rag_response(response=response, query=question)
        except RagConnectionError as exc:
            return f"📡 *Servicio RAG no disponible:*\n{exc.message}"
        except RagClientError as exc:
            return f"⚠️ *Error en la consulta RAG:* {exc.message}"

    async def _continue_flow(self, sender_id: str, text: str) -> Dict[str, Any]:
        state = self._states.get(sender_id, {})
        flow = state.get("flow")
        step = state.get("step")

        if flow == "login":
            if step == "email":
                if "@" not in text:
                    return {"reply": "⚠️ Ingresa un correo válido (ej. `usuario@ucp.edu.co`):", "reminder": None}
                state["email"] = text
                state["step"] = "password"
                return {"reply": "🔑 Ahora escribe tu *contraseña*:", "reminder": None}
            if step == "password":
                email = state.get("email", "")
                self._states.pop(sender_id, None)
                return {"reply": await self._execute_login(sender_id, email, text), "reminder": None}

        if flow == "register":
            if step == "nombre":
                if len(text) < 2:
                    return {"reply": "⚠️ El nombre debe tener al menos 2 caracteres. Intenta de nuevo:", "reminder": None}
                state["nombre"] = text
                state["step"] = "email"
                return {"reply": "Paso 2 de 3: Escribe tu *correo electrónico institucional*:", "reminder": None}
            if step == "email":
                if "@" not in text:
                    return {"reply": "⚠️ Ingresa un correo electrónico válido:", "reminder": None}
                state["email"] = text
                state["step"] = "password"
                return {"reply": "Paso 3 de 3: Elige una *contraseña* (mínimo 6 caracteres):", "reminder": None}
            if step == "password":
                if len(text) < 6:
                    return {"reply": "⚠️ La contraseña debe tener al menos 6 caracteres:", "reminder": None}
                nombre = state.get("nombre", "")
                email = state.get("email", "")
                self._states.pop(sender_id, None)
                return {"reply": await self._execute_register(sender_id, nombre, email, text), "reminder": None}

        if flow == "preguntar":
            self._states.pop(sender_id, None)
            return {"reply": await self._execute_question(sender_id, text), "reminder": None}

        if flow == "recordar":
            if step == "tiempo":
                seconds = parse_time_offset_or_date(text)
                if not seconds:
                    return {"reply": "⚠️ Tiempo inválido. Usa por ejemplo `10s`, `15m`, `2h` o `1d`:", "reminder": None}
                state["tiempo"] = text
                state["step"] = "mensaje"
                return {"reply": "📝 ¿Qué tarea o mensaje quieres que te recuerde?", "reminder": None}
            if step == "mensaje":
                tiempo = state.get("tiempo", "15m")
                self._states.pop(sender_id, None)
                return self._build_reminder_response(tiempo, text)

        self._states.pop(sender_id, None)
        return {"reply": self.get_welcome_menu(sender_id), "reminder": None}


whatsapp_processor = WhatsAppCommandProcessor()
