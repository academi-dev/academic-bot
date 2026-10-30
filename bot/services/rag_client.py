"""
Cliente HTTP asíncrono para el servicio de RAG (academic-rag).

Permite consultar preguntas sobre material académico, documentos indexados
y obtener respuestas fundamentadas con citas bibliográficas.
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


class RagClientError(Exception):
    """Excepción base para errores en el servicio academic-rag."""

    def __init__(self, message: str, code: str = "ERROR_RAG", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class RagConnectionError(RagClientError):
    """Error cuando el servicio RAG no está disponible."""

    def __init__(self, message: str = "No fue posible conectar con el servicio inteligente RAG."):
        super().__init__(message, code="ERROR_CONEXION_RAG", status_code=503)


class AcademicRagClient:
    """
    Cliente para interactuar con la API del servicio RAG de Academic.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        """
        Inicializa el cliente RAG.

        Args:
            base_url: URL base del servicio RAG (ej. http://localhost:8001/api/v1).
            timeout: Tiempo máximo de espera (suele ser mayor para inferencia/embeddings).
        """
        self.base_url = (base_url or settings.RAG_BASE_URL).rstrip("/")
        # RAG puede requerir mayor tiempo debido a embeddings y generación
        self.timeout = timeout or max(settings.REQUEST_TIMEOUT, 60.0)

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Construye las cabeceras HTTP."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def ask_question(
        self,
        query: str,
        token: Optional[str] = None,
        materia_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía una consulta al servicio RAG y retorna la respuesta con fuentes y citas.

        Args:
            query: Pregunta en lenguaje natural formulada por el estudiante.
            token: Token JWT opcional del usuario.
            materia_id: UUID opcional de la materia para acotar el contexto documental.

        Returns:
            Diccionario con 'respuesta' y lista de 'citas'.
        """
        # Endpoint de academic-rag: POST /api/v1/preguntar
        # (materia_id se conserva en la firma por compatibilidad; academic-rag aún no filtra por materia)
        url = f"{self.base_url}/preguntar"
        payload: Dict[str, Any] = {"pregunta": query, "top_k": 3}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=self._get_headers(token)
                )

                if not response.is_success:
                    error_msg = response.text or f"Error HTTP {response.status_code}"
                    logger.error("Error en servicio RAG (%s): %s", response.status_code, error_msg)
                    raise RagClientError(
                        f"El servicio de preguntas reportó un inconveniente: {error_msg}",
                        status_code=response.status_code
                    )

                data = response.json()
                # Normalizar respuesta esperada
                return {
                    "respuesta": data.get("respuesta", data.get("answer", "Sin respuesta disponible.")),
                    "citas": data.get("citas", data.get("sources", [])),
                    "materia_id": data.get("materia_id", materia_id)
                }

        except httpx.ConnectError as exc:
            logger.error("No se pudo conectar con el servicio RAG en %s: %s", url, exc)
            raise RagConnectionError("El asistente inteligente RAG no se encuentra disponible en este momento.") from exc
        except httpx.TimeoutException as exc:
            logger.error("Timeout en consulta RAG: %s", exc)
            raise RagConnectionError("El asistente inteligente tardó demasiado en procesar la consulta.") from exc

    async def upload_document(
        self,
        file_bytes: bytes,
        filename: str,
        token: str,
        materia_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sube un documento académico (PDF/texto) para indexación vectorial en ChromaDB.

        Args:
            file_bytes: Contenido binario del archivo.
            filename: Nombre original del archivo.
            token: Token JWT del usuario.
            materia_id: Identificador de la materia a la que pertenece el documento.

        Returns:
            Confirmación de indexación.
        """
        url = f"{self.base_url}/documentos"
        data = {}
        if materia_id:
            data["materia_id"] = materia_id

        files = {"file": (filename, file_bytes, "application/pdf")}
        headers = {"Authorization": f"Bearer {token}"}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, data=data, files=files, headers=headers)
                if not response.is_success:
                    raise RagClientError(f"Error subiendo documento: {response.text}", status_code=response.status_code)
                return response.json()
        except httpx.ConnectError as exc:
            raise RagConnectionError("No fue posible conectar para subir el documento.") from exc
        except httpx.TimeoutException as exc:
            raise RagConnectionError("Tiempo de espera agotado al indexar documento.") from exc

    async def list_documents(
        self,
        token: Optional[str] = None,
        materia_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene los documentos indexados en el sistema RAG.

        Args:
            token: Token JWT.
            materia_id: Filtro opcional por materia.

        Returns:
            Lista de documentos indexados.
        """
        url = f"{self.base_url}/documentos"
        params = {}
        if materia_id:
            params["materia_id"] = materia_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=self._get_headers(token))
                if not response.is_success:
                    return []
                data = response.json()
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("items", data.get("documentos", []))
                return []
        except Exception:
            return []


# Instancia singleton
rag_client = AcademicRagClient()
