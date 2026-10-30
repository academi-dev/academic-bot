"""
Utilidades de formateo para Academic Bot.

Convierte modelos y respuestas de API/RAG en mensajes atractivos para Telegram
utilizando Markdown, emojis y formato de fechas en español.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def parse_iso_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parsea una cadena de fecha en formato ISO 8601 a un objeto datetime en UTC.

    Args:
        date_str: Cadena ISO 8601 (ej. '2026-10-30T14:00:00Z' o '2026-10-30T14:00:00+00:00').

    Returns:
        datetime con timezone UTC o None si el string es inválido o nulo.
    """
    if not date_str:
        return None
    try:
        # Reemplazar Z por +00:00 para compatibilidad con fromisoformat en versiones previas
        clean_str = date_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def format_datetime_friendly(dt: Optional[datetime]) -> str:
    """
    Formatea un datetime a una representación legible en español con hora UTC.

    Args:
        dt: Objeto datetime en UTC.

    Returns:
        Cadena con formato 'DD/MM/AAAA HH:MM UTC' o 'Sin fecha definida'.
    """
    if dt is None:
        return "Sin fecha definida"
    return dt.strftime("%d/%m/%Y %H:%M UTC")


def is_due_in_next_days(
    date_str: Optional[str],
    days: int = 7,
    reference_dt: Optional[datetime] = None
) -> bool:
    """
    Determina si una fecha dada vence dentro de los próximos N días a partir de ahora.

    Args:
        date_str: Cadena de fecha en formato ISO 8601.
        days: Número de días hacia el futuro a considerar (por defecto 7).
        reference_dt: Momento de referencia para comparación (por defecto utcnow).

    Returns:
        True si la fecha está entre la referencia y referencia + N días.
    """
    due_dt = parse_iso_datetime(date_str)
    if due_dt is None:
        return False

    now = reference_dt or datetime.now(timezone.utc)
    limit = now + timedelta(days=days)

    return now <= due_dt <= limit


def parse_time_offset_or_date(text: str) -> Optional[int]:
    """
    Parsea una expresión de tiempo y retorna los segundos faltantes para el evento.

    Formatos admitidos:
    - Expresiones relativas: '30s', '15m', '2h', '1d' (o combinaciones como '1h30m')
    - Fechas fijas: 'AAAA-MM-DD HH:MM' o 'DD/MM/AAAA HH:MM' (asume UTC)

    Args:
        text: Texto ingresado por el usuario.

    Returns:
        Cantidad de segundos (entero positivo) o None si el formato no es válido.
    """
    text = text.strip().lower()
    if not text:
        return None

    # Intentar formato relativo (ej. 10m, 2h, 3d, 45s, 1h30m)
    pattern = r"^(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?$"
    match = re.match(pattern, text)
    if match and any(match.groups()):
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        seconds = int(match.group(4) or 0)
        total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
        return total_seconds if total_seconds > 0 else None

    # Intentar formato de fecha absoluta
    date_formats = [
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]
    now = datetime.now(timezone.utc)
    for fmt in date_formats:
        try:
            parsed = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            delta = (parsed - now).total_seconds()
            if delta > 0:
                return int(delta)
        except ValueError:
            continue

    return None


def format_materias(materias: List[Dict[str, Any]]) -> str:
    """
    Formatea la lista de asignaturas/materias para Telegram.

    Args:
        materias: Lista de diccionarios representando materias.

    Returns:
        Mensaje formateado en Markdown.
    """
    if not materias:
        return (
            "📚 *Tus Materias*\n\n"
            "ℹ️ No tienes materias matriculadas actualmente.\n"
            "Usa la plataforma académica para inscribir asignaturas."
        )

    lines = ["📚 *Tus Materias Matriculadas:*\n"]
    for idx, mat in enumerate(materias, start=1):
        nombre = mat.get("nombre", "Sin nombre")
        codigo = mat.get("codigo", "")
        profesor = mat.get("profesor", mat.get("docente", "No asignado"))
        creditos = mat.get("creditos", None)
        semestre = mat.get("semestre", None)

        header = f"*{idx}. {nombre}*"
        if codigo:
            header += f" (`{codigo}`)"
        lines.append(header)
        lines.append(f"   👤 Profesor: {profesor}")
        
        detalles = []
        if creditos is not None:
            detalles.append(f"Créditos: {creditos}")
        if semestre:
            detalles.append(f"Semestre: {semestre}")
        if detalles:
            lines.append(f"   📌 {' | '.join(detalles)}")
        lines.append("")

    lines.append(f"📊 _Total de asignaturas: {len(materias)}_")
    return "\n".join(lines)


def format_materia_detail(materia: Dict[str, Any]) -> str:
    """
    Formatea el detalle individual de una materia.

    Args:
        materia: Diccionario con la información de la materia.

    Returns:
        Mensaje en Markdown con el detalle.
    """
    nombre = materia.get("nombre", "Sin nombre")
    codigo = materia.get("codigo", "N/A")
    profesor = materia.get("profesor", "No asignado")
    descripcion = materia.get("descripcion", "Sin descripción disponible.")
    creditos = materia.get("creditos", "-")

    return (
        f"📖 *Detalle de Asignatura: {nombre}*\n\n"
        f"🏷️ *Código:* `{codigo}`\n"
        f"👤 *Profesor:* {profesor}\n"
        f"🎯 *Créditos:* {creditos}\n"
        f"📝 *Descripción:* {descripcion}\n"
    )


def _get_status_badge(estado: Optional[str]) -> str:
    """Retorna un emoji y etiqueta según el estado de la tarea."""
    estado_norm = (estado or "").lower().strip()
    if estado_norm in ("completada", "entregada", "calificada", "done"):
        return "🟢 *Entregada*"
    if estado_norm in ("en_progreso", "en progreso", "in_progress"):
        return "🟡 *En progreso*"
    return "🔴 *Pendiente*"


def format_tareas(
    tareas: List[Dict[str, Any]],
    title: str = "📋 *Tus Tareas:*",
    empty_message: str = "🎉 ¡No tienes tareas registradas!"
) -> str:
    """
    Formatea una lista de tareas para visualización en Telegram.

    Args:
        tareas: Lista de diccionarios de tareas.
        title: Título de la sección.
        empty_message: Mensaje cuando la lista esté vacía.

    Returns:
        Mensaje en Markdown.
    """
    if not tareas:
        return f"{title}\n\n{empty_message}"

    lines = [f"{title}\n"]
    for idx, t in enumerate(tareas, start=1):
        titulo = t.get("titulo", t.get("nombre", "Tarea sin título"))
        materia = t.get("materia_nombre", t.get("materia", "General"))
        estado = t.get("estado", "pendiente")
        badge = _get_status_badge(estado)

        fecha_raw = t.get("fecha_entrega", t.get("fecha_limite"))
        dt_entrega = parse_iso_datetime(fecha_raw)
        fecha_txt = format_datetime_friendly(dt_entrega)

        lines.append(f"*{idx}. {titulo}*")
        lines.append(f"   📚 Materia: _{materia}_")
        lines.append(f"   Estado: {badge}")
        lines.append(f"   ⏰ Entrega: {fecha_txt}")

        descripcion = t.get("descripcion")
        if descripcion:
            # Truncar descripción si es muy extensa
            desc_short = descripcion[:80] + ("..." if len(descripcion) > 80 else "")
            lines.append(f"   📝 _{desc_short}_")
        lines.append("")

    lines.append(f"📊 _Total: {len(tareas)} tarea(s)_")
    return "\n".join(lines)


def format_tarea_detail(tarea: Dict[str, Any]) -> str:
    """
    Formatea el detalle completo de una tarea individual.

    Args:
        tarea: Diccionario de la tarea.

    Returns:
        Mensaje en Markdown con la ficha de la tarea.
    """
    titulo = tarea.get("titulo", "Sin título")
    materia = tarea.get("materia_nombre", tarea.get("materia", "General"))
    descripcion = tarea.get("descripcion", "Sin descripción")
    estado = _get_status_badge(tarea.get("estado"))
    fecha_raw = tarea.get("fecha_entrega")
    dt_entrega = parse_iso_datetime(fecha_raw)
    fecha_txt = format_datetime_friendly(dt_entrega)

    return (
        f"📝 *Ficha de Tarea: {titulo}*\n\n"
        f"📚 *Materia:* {materia}\n"
        f"📌 *Estado:* {estado}\n"
        f"⏰ *Fecha límite:* {fecha_txt}\n\n"
        f"📄 *Instrucciones:*\n{descripcion}\n"
    )


def format_rag_response(response: Dict[str, Any], query: str) -> str:
    """
    Formatea la respuesta generada por el servicio RAG con sus citas bibliográficas.

    Args:
        response: Diccionario de respuesta de academic-rag.
        query: Pregunta original formulada por el estudiante.

    Returns:
        Mensaje en Markdown listo para enviar al usuario.
    """
    respuesta = response.get("respuesta", response.get("answer", "No se encontró respuesta."))
    citas = response.get("citas", response.get("sources", []))

    lines = [
        f"🤖 *Asistente Académico (RAG)*\n",
        f"❓ *Tu pregunta:* _{query}_\n",
        f"💡 *Respuesta:*\n{respuesta}\n"
    ]

    if citas:
        lines.append("📚 *Fuentes y Citas Consultadas:*")
        for idx, cita in enumerate(citas, start=1):
            doc = cita.get("documento", cita.get("document", "Documento"))
            pagina = cita.get("pagina", cita.get("page", None))
            # academic-rag devuelve "texto" y "relevancia"; se aceptan alias por compatibilidad
            fragmento = cita.get("texto", cita.get("fragmento", cita.get("text", cita.get("content", ""))))
            similitud = cita.get("relevancia", cita.get("similitud", cita.get("score", None)))

            fuente_str = f"*{idx}. {doc}*"
            if pagina is not None:
                fuente_str += f" (Pág. {pagina})"
            if similitud is not None:
                try:
                    pct = float(similitud) * 100
                    fuente_str += f" — Confianza: `{pct:.1f}%`"
                except (ValueError, TypeError):
                    pass

            lines.append(fuente_str)
            if fragmento:
                snippet = fragmento.strip().replace("\n", " ")
                if len(snippet) > 140:
                    snippet = snippet[:140] + "..."
                lines.append(f"   > \"_{snippet}_\"")
        lines.append("")
    else:
        lines.append("ℹ️ _Respuesta generada con base en conocimientos generales sin documentos indexados específicos._")

    return "\n".join(lines)


def format_reminder_notification(
    tarea_titulo: str,
    fecha_entrega: Optional[str] = None
) -> str:
    """
    Crea el mensaje de alerta enviado cuando vence un recordatorio programado.

    Args:
        tarea_titulo: Nombre o descripción del recordatorio.
        fecha_entrega: Fecha de entrega si aplica.

    Returns:
        Mensaje en Markdown con alta visibilidad.
    """
    lines = [
        "⏰ *¡RECORDATORIO ACADÉMICO!* ⏰\n",
        f"📌 *Asunto:* {tarea_titulo}",
    ]
    if fecha_entrega:
        dt = parse_iso_datetime(fecha_entrega)
        lines.append(f"📅 *Entrega:* {format_datetime_friendly(dt)}")

    lines.append("\n💪 ¡Es momento de avanzar o completar esta actividad!")
    lines.append("Consulta tus pendientes con /pendientes")
    return "\n".join(lines)
