"""
Pruebas unitarias para las utilidades de formateo y almacenamiento de sesiones.
"""

from datetime import datetime, timedelta, timezone
import pytest

from bot.utils.auth_storage import AuthStorage
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


class TestDateParsingAndFriendlyFormatting:
    """Pruebas para parseo de fechas ISO 8601 y formato amigable."""

    def test_parse_iso_datetime_valid(self):
        date_str = "2026-10-30T14:30:00Z"
        dt = parse_iso_datetime(date_str)
        assert dt is not None
        assert dt.year == 2026
        assert dt.month == 10
        assert dt.day == 30
        assert dt.hour == 14
        assert dt.minute == 30
        assert dt.tzinfo == timezone.utc

    def test_parse_iso_datetime_with_offset(self):
        date_str = "2026-10-30T14:30:00+00:00"
        dt = parse_iso_datetime(date_str)
        assert dt is not None
        assert dt.hour == 14

    def test_parse_iso_datetime_invalid(self):
        assert parse_iso_datetime(None) is None
        assert parse_iso_datetime("") is None
        assert parse_iso_datetime("fecha_invalida") is None

    def test_format_datetime_friendly(self):
        dt = datetime(2026, 10, 30, 18, 45, tzinfo=timezone.utc)
        formatted = format_datetime_friendly(dt)
        assert formatted == "30/10/2026 18:45 UTC"

    def test_format_datetime_friendly_none(self):
        assert format_datetime_friendly(None) == "Sin fecha definida"


class TestDueInNextDaysFilter:
    """Pruebas para el filtrado de tareas que vencen en los próximos 7 días."""

    def test_is_due_in_next_days_within_window(self):
        ref = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
        # 3 días después
        future_date = (ref + timedelta(days=3)).isoformat()
        assert is_due_in_next_days(future_date, days=7, reference_dt=ref) is True

    def test_is_due_in_next_days_exact_boundary(self):
        ref = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
        boundary = (ref + timedelta(days=7)).isoformat()
        assert is_due_in_next_days(boundary, days=7, reference_dt=ref) is True

    def test_is_due_in_next_days_beyond_window(self):
        ref = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
        far_future = (ref + timedelta(days=8)).isoformat()
        assert is_due_in_next_days(far_future, days=7, reference_dt=ref) is False

    def test_is_due_in_next_days_past(self):
        ref = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
        past_date = (ref - timedelta(days=1)).isoformat()
        assert is_due_in_next_days(past_date, days=7, reference_dt=ref) is False

    def test_is_due_in_next_days_invalid(self):
        assert is_due_in_next_days(None) is False
        assert is_due_in_next_days("invalido") is False


class TestTimeOffsetParsing:
    """Pruebas para el cálculo de segundos a partir de texto de tiempo."""

    def test_parse_seconds(self):
        assert parse_time_offset_or_date("30s") == 30

    def test_parse_minutes(self):
        assert parse_time_offset_or_date("15m") == 15 * 60

    def test_parse_hours(self):
        assert parse_time_offset_or_date("2h") == 2 * 3600

    def test_parse_days(self):
        assert parse_time_offset_or_date("1d") == 86400

    def test_parse_combined(self):
        assert parse_time_offset_or_date("1h 30m") == 3600 + 1800

    def test_parse_invalid(self):
        assert parse_time_offset_or_date("") is None
        assert parse_time_offset_or_date("hola mundo") is None


class TestMateriasFormatting:
    """Pruebas para el formateo de asignaturas."""

    def test_format_materias_empty(self):
        res = format_materias([])
        assert "No tienes materias matriculadas" in res

    def test_format_materias_with_items(self):
        materias = [
            {
                "codigo": "MAT-101",
                "nombre": "Cálculo Diferencial",
                "profesor": "Ing. Carlos Mendoza",
                "creditos": 4,
                "semestre": "2026-2",
            },
            {
                "codigo": "SIS-202",
                "nombre": "Estructuras de Datos",
                "profesor": "Dra. Laura Gómez",
                "creditos": 3,
            },
        ]
        res = format_materias(materias)
        assert "Cálculo Diferencial" in res
        assert "`MAT-101`" in res
        assert "Ing. Carlos Mendoza" in res
        assert "Estructuras de Datos" in res
        assert "Total de asignaturas: 2" in res

    def test_format_materia_detail(self):
        materia = {
            "codigo": "FIS-101",
            "nombre": "Física Mecánica",
            "profesor": "Dr. Andrés Gómez",
            "descripcion": "Estudio del movimiento y fuerzas.",
            "creditos": 3,
        }
        res = format_materia_detail(materia)
        assert "Física Mecánica" in res
        assert "`FIS-101`" in res
        assert "Dr. Andrés Gómez" in res


class TestTareasFormatting:
    """Pruebas para el formateo de tareas y pendientes."""

    def test_format_tareas_empty(self):
        res = format_tareas([], title="📋 *Tus Tareas:*")
        assert "¡No tienes tareas registradas!" in res

    def test_format_tareas_with_items(self):
        tareas = [
            {
                "titulo": "Taller de Derivadas",
                "materia_nombre": "Cálculo",
                "estado": "pendiente",
                "fecha_entrega": "2026-10-31T23:59:00Z",
                "descripcion": "Resolver ejercicios impares de la sección 3.2.",
            },
            {
                "titulo": "Proyecto Árboles AVL",
                "materia_nombre": "Estructuras",
                "estado": "entregada",
                "fecha_entrega": "2026-11-05T12:00:00Z",
            },
        ]
        res = format_tareas(tareas)
        assert "Taller de Derivadas" in res
        assert "🔴 *Pendiente*" in res
        assert "🟢 *Entregada*" in res
        assert "Total: 2 tarea(s)" in res

    def test_format_tarea_detail(self):
        tarea = {
            "titulo": "Ensayo de Ética",
            "materia_nombre": "Humanidades",
            "estado": "en_progreso",
            "fecha_entrega": "2026-11-01T20:00:00Z",
            "descripcion": "Ensayo sobre inteligencia artificial y ética.",
        }
        res = format_tarea_detail(tarea)
        assert "Ensayo de Ética" in res
        assert "🟡 *En progreso*" in res


class TestRagFormatting:
    """Pruebas para respuestas RAG y citas."""

    def test_format_rag_response_with_citations(self):
        response = {
            "respuesta": "El examen abarca los capítulos 1 al 4 del libro guía.",
            "citas": [
                {
                    "documento": "Silabo_Calculo.pdf",
                    "pagina": 3,
                    "fragmento": "Evaluación 1: Capítulos 1, 2, 3 y 4.",
                    "similitud": 0.94,
                }
            ],
        }
        res = format_rag_response(response, query="¿Qué entra en el parcial?")
        assert "El examen abarca los capítulos" in res
        assert "Silabo_Calculo.pdf" in res
        assert "Pág. 3" in res
        assert "94.0%" in res

    def test_format_rag_response_without_citations(self):
        response = {
            "respuesta": "Para solicitar supletorio debes radicar formulario en secretaría.",
            "citas": [],
        }
        res = format_rag_response(response, query="¿Cómo pido supletorio?")
        assert "Para solicitar supletorio" in res
        assert "conocimientos generales" in res


class TestReminderNotification:
    """Pruebas para mensajes de alerta de recordatorios."""

    def test_format_reminder_notification(self):
        res = format_reminder_notification(
            tarea_titulo="Entrega de Laboratorio 3",
            fecha_entrega="2026-10-30T18:00:00Z"
        )
        assert "¡RECORDATORIO ACADÉMICO!" in res
        assert "Entrega de Laboratorio 3" in res
        assert "30/10/2026 18:00 UTC" in res


class TestAuthStorage:
    """Pruebas para el gestor de sesiones en memoria."""

    def test_set_and_get_token(self):
        store = AuthStorage()
        assert not store.is_authenticated(12345)

        store.set_token(12345, "token_jwt_valido", {"nombre": "Eyfer", "email": "eyfer@test.edu"})
        assert store.is_authenticated(12345)
        assert store.get_token(12345) == "token_jwt_valido"
        user = store.get_user_info(12345)
        assert user is not None
        assert user["nombre"] == "Eyfer"

    def test_remove_token(self):
        store = AuthStorage()
        store.set_token(999, "token_x")
        assert store.remove_token(999) is True
        assert not store.is_authenticated(999)
        assert store.remove_token(999) is False

    def test_clear(self):
        store = AuthStorage()
        store.set_token(1, "t1")
        store.set_token(2, "t2")
        store.clear()
        assert not store.is_authenticated(1)
        assert not store.is_authenticated(2)
