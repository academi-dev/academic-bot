"""
Cliente HTTP asíncrono para comunicarse con academic-api.

Gestiona autenticación, asignaturas y tareas universitarias respetando
los estándares del proyecto Academic (códigos HTTP, formato de error estandarizado,
paginación y autenticación JWT).
"""

import logging
from typing import Any, Dict, List, Optional
import httpx

from bot.config import settings

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """Excepción base para errores en llamadas a academic-api."""

    def __init__(self, message: str, code: str = "ERROR_API", status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class ApiConnectionError(ApiClientError):
    """Error cuando el servicio academic-api no está disponible o la conexión falla."""

    def __init__(self, message: str = "No fue posible conectar con el servidor de Academic."):
        super().__init__(message, code="ERROR_CONEXION", status_code=503)


class ApiAuthError(ApiClientError):
    """Error de credenciales inválidas o token expirado."""

    def __init__(self, message: str = "Credenciales incorrectas o sesión expirada."):
        super().__init__(message, code="ERROR_AUTENTICACION", status_code=401)


class ApiNotFoundError(ApiClientError):
    """Error cuando el recurso solicitado no existe."""

    def __init__(self, message: str = "El recurso solicitado no fue encontrado."):
        super().__init__(message, code="NO_ENCONTRADO", status_code=404)


class ApiConflictError(ApiClientError):
    """Error cuando existe un conflicto de datos (ej. correo ya registrado)."""

    def __init__(self, message: str = "Ya existe un registro con esos datos."):
        super().__init__(message, code="CONFLICTO_DATOS", status_code=409)


class ApiValidationError(ApiClientError):
    """Error de validación de datos en la solicitud."""

    def __init__(self, message: str = "Los datos ingresados no son válidos."):
        super().__init__(message, code="ERROR_VALIDACION", status_code=422)


class AcademicApiClient:
    """
    Cliente asíncrono basado en httpx para interactuar con los endpoints de academic-api.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        """
        Inicializa el cliente de academic-api.

        Args:
            base_url: URL base de la API (ej. http://localhost:8000/api/v1).
            timeout: Tiempo máximo de espera para peticiones en segundos.
        """
        self.base_url = (base_url or settings.API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.REQUEST_TIMEOUT

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        """Genera las cabeceras HTTP necesarias para las peticiones."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """Extrae el mensaje descriptivo del cuerpo de error estandarizado."""
        try:
            data = response.json()
            # Formato estándar de Academic: {"error": {"codigo": "...", "mensaje": "..."}}
            if isinstance(data, dict):
                if "error" in data and isinstance(data["error"], dict):
                    return data["error"].get("mensaje", "Error del servidor")
                if "detail" in data:
                    detail = data["detail"]
                    if isinstance(detail, list):
                        # Caso FastAPI ValidationError
                        primer = detail[0] if detail else {}
                        return primer.get("msg", str(detail))
                    return str(detail)
                if "mensaje" in data:
                    return str(data["mensaje"])
        except Exception:
            pass
        return response.text or f"Error HTTP {response.status_code}"

    def _handle_response_errors(self, response: httpx.Response) -> None:
        """Verifica el código HTTP y lanza las excepciones de negocio correspondientes."""
        if response.is_success:
            return

        detail = self._extract_error_detail(response)
        code = response.status_code

        if code in (401, 403):
            raise ApiAuthError(detail)
        if code == 404:
            raise ApiNotFoundError(detail)
        if code == 409:
            raise ApiConflictError(detail)
        if code == 422:
            raise ApiValidationError(detail)
        if code >= 500:
            raise ApiClientError(f"Error interno del servidor académico: {detail}", code="ERROR_SERVIDOR", status_code=code)
        
        raise ApiClientError(detail, status_code=code)

    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Autentica un usuario contra academic-api y obtiene el token JWT.

        Args:
            email: Correo electrónico universitario.
            password: Clave de acceso.

        Returns:
            Diccionario con access_token, token_type y datos del usuario.
        """
        url = f"{self.base_url}/auth/login"
        payload = {"email": email, "password": password}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())
                self._handle_response_errors(response)
                return response.json()
        except httpx.ConnectError as exc:
            logger.error("No se pudo conectar con la API en %s: %s", url, exc)
            raise ApiConnectionError("No fue posible conectar con el servidor académico.") from exc
        except httpx.TimeoutException as exc:
            logger.error("Tiempo de espera agotado al conectar con %s: %s", url, exc)
            raise ApiConnectionError("El servidor tardó demasiado en responder.") from exc

    async def register(self, nombre: str, email: str, password: str) -> Dict[str, Any]:
        """
        Registra una nueva cuenta de usuario en academic-api.

        Args:
            nombre: Nombre completo del estudiante.
            email: Correo universitario institucional.
            password: Clave elegida.

        Returns:
            Diccionario con la confirmación de registro y token o usuario creado.
        """
        url = f"{self.base_url}/auth/registro"
        payload = {"nombre": nombre, "email": email, "password": password}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())
                self._handle_response_errors(response)
                return response.json()
        except httpx.ConnectError as exc:
            logger.error("Fallo de conexión al registrar usuario: %s", exc)
            raise ApiConnectionError("No fue posible conectar con el servidor para el registro.") from exc
        except httpx.TimeoutException as exc:
            raise ApiConnectionError("Tiempo de espera agotado en el registro.") from exc

    async def get_materias(
        self,
        token: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el listado de materias del usuario autenticado.

        Args:
            token: Token JWT de sesión.
            limit: Número máximo de registros a retornar.
            offset: Desplazamiento para paginación.

        Returns:
            Lista de materias.
        """
        url = f"{self.base_url}/materias"
        # academic-api usa los parámetros de paginación en español
        params = {"limite": limit, "desplazamiento": offset}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(token)
                )
                self._handle_response_errors(response)
                data = response.json()

                # Manejar respuesta como lista directa o diccionario paginado
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    if "items" in data and isinstance(data["items"], list):
                        return data["items"]
                    if "data" in data and isinstance(data["data"], list):
                        return data["data"]
                    if "materias" in data and isinstance(data["materias"], list):
                        return data["materias"]
                return []
        except httpx.ConnectError as exc:
            logger.error("Error conectando con /materias: %s", exc)
            raise ApiConnectionError("No se pudo conectar con el servidor para consultar materias.") from exc
        except httpx.TimeoutException as exc:
            raise ApiConnectionError("El servidor tardó demasiado en responder la consulta de materias.") from exc

    async def get_materia(self, token: str, materia_id: str) -> Dict[str, Any]:
        """
        Obtiene el detalle de una materia por su identificador UUID.

        Args:
            token: Token JWT.
            materia_id: UUID de la materia.

        Returns:
            Detalle de la materia.
        """
        url = f"{self.base_url}/materias/{materia_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers(token))
                self._handle_response_errors(response)
                return response.json()
        except httpx.ConnectError as exc:
            raise ApiConnectionError() from exc
        except httpx.TimeoutException as exc:
            raise ApiConnectionError() from exc

    async def get_tareas(
        self,
        token: str,
        materia_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Obtiene el listado de tareas asignadas al usuario.

        Args:
            token: Token JWT.
            materia_id: Filtro opcional por materia.
            estado: Filtro opcional por estado ('pendiente', 'entregada', etc.).
            limit: Límite de paginación.
            offset: Desplazamiento.

        Returns:
            Lista de tareas.
        """
        url = f"{self.base_url}/tareas"
        params: Dict[str, Any] = {"limite": limit, "desplazamiento": offset}
        if materia_id:
            params["materia_id"] = materia_id
        if estado:
            params["estado"] = estado

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    params=params,
                    headers=self._get_headers(token)
                )
                self._handle_response_errors(response)
                data = response.json()

                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    if "items" in data and isinstance(data["items"], list):
                        return data["items"]
                    if "data" in data and isinstance(data["data"], list):
                        return data["data"]
                    if "tareas" in data and isinstance(data["tareas"], list):
                        return data["tareas"]
                return []
        except httpx.ConnectError as exc:
            logger.error("Error conectando con /tareas: %s", exc)
            raise ApiConnectionError("No se pudo conectar con el servidor para consultar tareas.") from exc
        except httpx.TimeoutException as exc:
            raise ApiConnectionError("Tiempo de espera agotado al consultar tareas.") from exc

    async def get_tarea(self, token: str, tarea_id: str) -> Dict[str, Any]:
        """
        Obtiene el detalle de una tarea específica por su UUID.

        Args:
            token: Token JWT.
            tarea_id: UUID de la tarea.

        Returns:
            Detalle de la tarea.
        """
        url = f"{self.base_url}/tareas/{tarea_id}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_headers(token))
                self._handle_response_errors(response)
                return response.json()
        except httpx.ConnectError as exc:
            raise ApiConnectionError() from exc
        except httpx.TimeoutException as exc:
            raise ApiConnectionError() from exc


# Instancia singleton para uso general
api_client = AcademicApiClient()
