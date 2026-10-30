"""Pruebas unitarias para el procesador de comandos de WhatsApp (`WhatsAppCommandProcessor`)."""

from typing import Any, Dict, List, Optional
import pytest

from bot.utils.auth_storage import AuthStorage
from bot.whatsapp.processor import WhatsAppCommandProcessor


class FakeApiClient:
    """Cliente falso en memoria para simular academic-api sin red."""

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        if password == "ClaveCorrecta123":
            return {"access_token": "jwt_whatsapp_token_123", "token_type": "bearer"}
        from bot.services.api_client import ApiAuthError
        raise ApiAuthError("Credenciales inválidas")

    async def register(self, nombre: str, email: str, password: str) -> Dict[str, Any]:
        return {"id": "u-1", "nombre": nombre, "email": email, "rol": "estudiante"}

    async def get_materias(self, token: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return [
            {
                "id": "m-1",
                "nombre": "Estructuras de Datos",
                "codigo": "IS-301",
                "semestre": "2026-2",
                "descripcion": "Árboles AVL y grafos",
            }
        ]

    async def get_tareas(
        self,
        token: str,
        materia_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return [
            {
                "id": "t-1",
                "titulo": "Implementar rotación doble AVL",
                "estado": "pendiente",
                "fecha_entrega": "2026-11-01T23:59:00Z",
                "materia_id": "m-1",
            }
        ]


class FakeRagClient:
    """Cliente falso en memoria para simular academic-rag sin red."""

    async def ask_question(
        self, query: str, token: Optional[str] = None, materia_id: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "respuesta": "La búsqueda binaria tiene complejidad O(log n).",
            "citas": [
                {
                    "documento": "ejemplo_apuntes.pdf",
                    "pagina": 2,
                    "texto": "O(log n): Tiempo logarítmico en listas ordenadas.",
                    "relevancia": 0.96,
                }
            ],
        }


@pytest.fixture
def wa_processor() -> WhatsAppCommandProcessor:
    return WhatsAppCommandProcessor(
        api=FakeApiClient(),  # type: ignore[arg-type]
        rag=FakeRagClient(),  # type: ignore[arg-type]
        storage=AuthStorage(),
    )


@pytest.mark.asyncio
async def test_whatsapp_menu_bienvenida(wa_processor: WhatsAppCommandProcessor) -> None:
    res = await wa_processor.handle_message("573001112233@s.whatsapp.net", "hola")
    assert "Academic Bot — Asistente en WhatsApp" in res["reply"]
    assert "/materias" in res["reply"]
    assert res["reminder"] is None


@pytest.mark.asyncio
async def test_whatsapp_materias_requiere_login(wa_processor: WhatsAppCommandProcessor) -> None:
    res = await wa_processor.handle_message("573001112233@s.whatsapp.net", "/materias")
    assert "Acceso restringido" in res["reply"]


@pytest.mark.asyncio
async def test_whatsapp_login_directo_y_consulta_materias_y_tareas(
    wa_processor: WhatsAppCommandProcessor,
) -> None:
    jid = "573001112233@s.whatsapp.net"
    login_res = await wa_processor.handle_message(jid, "/login jean@ucp.edu.co ClaveCorrecta123")
    assert "Sesión iniciada con éxito en WhatsApp" in login_res["reply"]

    mat_res = await wa_processor.handle_message(jid, "/materias")
    assert "Estructuras de Datos" in mat_res["reply"]
    assert "IS-301" in mat_res["reply"]

    tar_res = await wa_processor.handle_message(jid, "/tareas")
    assert "Implementar rotación doble AVL" in tar_res["reply"]


@pytest.mark.asyncio
async def test_whatsapp_flujo_login_paso_a_paso(
    wa_processor: WhatsAppCommandProcessor,
) -> None:
    jid = "573009998877@s.whatsapp.net"
    r1 = await wa_processor.handle_message(jid, "/login")
    assert "correo electrónico" in r1["reply"]

    r2 = await wa_processor.handle_message(jid, "eyfer@ucp.edu.co")
    assert "contraseña" in r2["reply"]

    r3 = await wa_processor.handle_message(jid, "ClaveCorrecta123")
    assert "Sesión iniciada con éxito en WhatsApp" in r3["reply"]


@pytest.mark.asyncio
async def test_whatsapp_recordar_programa_alerta(
    wa_processor: WhatsAppCommandProcessor,
) -> None:
    jid = "573001112233@s.whatsapp.net"
    res = await wa_processor.handle_message(jid, "/recordar 15m Repasar árboles AVL")
    assert "Recordatorio Programado en WhatsApp" in res["reply"]
    assert res["reminder"] is not None
    assert res["reminder"]["delay_seconds"] == 900
    assert "Repasar árboles AVL" in res["reminder"]["text"]


@pytest.mark.asyncio
async def test_whatsapp_preguntar_rag_con_citas(
    wa_processor: WhatsAppCommandProcessor,
) -> None:
    jid = "573001112233@s.whatsapp.net"
    res = await wa_processor.handle_message(
        jid, "/preguntar ¿Qué complejidad tiene la búsqueda binaria?"
    )
    assert "O(log n)" in res["reply"]
    assert "ejemplo_apuntes.pdf" in res["reply"]
    assert "Pág. 2" in res["reply"]
