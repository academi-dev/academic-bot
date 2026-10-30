"""
Paquete de utilidades para Academic Bot.

Contiene el almacenamiento de sesiones en memoria y los formateadores de Markdown.
"""

from bot.utils.auth_storage import AuthStorage, auth_storage
from bot.utils.formatters import (
    format_datetime_friendly,
    format_materia_detail,
    format_materias,
    format_rag_response,
    format_reminder_notification,
    format_tarea_detail,
    format_tareas,
    is_due_in_next_days,
    parse_iso_datetime,
    parse_time_offset_or_date,
)

__all__ = [
    "AuthStorage",
    "auth_storage",
    "format_datetime_friendly",
    "format_materia_detail",
    "format_materias",
    "format_rag_response",
    "format_reminder_notification",
    "format_tarea_detail",
    "format_tareas",
    "is_due_in_next_days",
    "parse_iso_datetime",
    "parse_time_offset_or_date",
]
